# Sidst opdateret: 2026-08-20 | Version: 2.0.29
from contextlib import asynccontextmanager
from typing import List, Optional
from datetime import datetime, date, timedelta
import logging
import os

import requests

from fastapi import FastAPI, Depends, File, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select

from app.database import init_db, get_session
from app.models import (
    Item,
    ItemCreate,
    Store,
    StoreCreate,
    StoreUpdate,
    ProximityState,
    ProximityCheckLog,
    NotificationLog,
    MissedNotificationReport,
    MissedNotificationReportCreate,
    EmulationSettings,
    StoreDistanceCheck,
    ExpiryItem,
    ExpiryItemCreate,
    VoiceCorrection,
    VoiceCorrectionCreate,
    ExpiryNotificationSettings,
    ExpiryNotificationSettingsUpdate,
    Receipt,
    ReceiptItem,
    ReceiptCreate,
)
from app.overpass import find_nearby_shops
from app.nominatim import find_nearby_shops_nominatim, haversine_m
from app.danish_date import parse_danish_date
from app.receipt_scan import extract_receipt, ReceiptScanError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Indkøbsliste", lifespan=lifespan)


@app.get("/")
def root():
    return {"status": "ok", "app": "indkobsliste"}


@app.post("/items", response_model=Item)
def add_item(item_in: ItemCreate, session: Session = Depends(get_session)):
    """Tilføjer en ny vare til indkøbslisten. Stort forbogstav sættes automatisk."""
    name = item_in.name.strip()
    if name:
        name = name[0].upper() + name[1:]
    item = Item(name=name)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@app.get("/items", response_model=List[Item])
def list_items(include_done: bool = False, session: Session = Depends(get_session)):
    """Henter varer på listen. Som standard vises kun ikke-afkrydsede varer."""
    statement = select(Item)
    if not include_done:
        statement = statement.where(Item.done == False)  # noqa: E712
    statement = statement.order_by(Item.added_at)
    return session.exec(statement).all()


def _get_item_or_404(item_id: int, session: Session) -> Item:
    item = session.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Vare ikke fundet")
    return item


@app.patch("/items/{item_id}/done", response_model=Item)
def mark_done(item_id: int, session: Session = Depends(get_session)):
    """Afkrydser en vare som købt (fjerner den fra standard-listen)."""
    item = _get_item_or_404(item_id, session)
    item.done = True
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@app.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: int, session: Session = Depends(get_session)):
    """Sletter en vare permanent fra listen."""
    item = _get_item_or_404(item_id, session)
    session.delete(item)
    session.commit()


@app.post("/stores", response_model=Store)
def add_store(store_in: StoreCreate, session: Session = Depends(get_session)):
    """Opretter en fast butik manuelt med navn og koordinater."""
    store = Store(
        name=store_in.name.strip(),
        latitude=store_in.latitude,
        longitude=store_in.longitude,
        radius_m=store_in.radius_m,
        shop_type=store_in.shop_type,
        osm_id=store_in.osm_id,
    )
    session.add(store)
    session.commit()
    session.refresh(store)
    return store


@app.get("/stores", response_model=List[Store])
def list_stores(session: Session = Depends(get_session)):
    """Henter alle registrerede butikker."""
    return session.exec(select(Store).order_by(Store.name)).all()


@app.patch("/stores/{store_id}", response_model=Store)
def update_store(store_id: int, update: StoreUpdate, session: Session = Depends(get_session)):
    """Opdaterer en butik - koordinater/radius (GPS-kalibrering), og/eller navn
    (omdøbning, fx til at skelne mellem flere butikker med samme kædenavn).
    Kun de felter der rent faktisk sendes med, bliver ændret."""
    store = session.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Butik ikke fundet")
    if update.name is not None:
        store.name = update.name.strip()
    if update.latitude is not None:
        store.latitude = update.latitude
    if update.longitude is not None:
        store.longitude = update.longitude
    if update.radius_m is not None:
        store.radius_m = update.radius_m
    session.add(store)
    session.commit()
    session.refresh(store)
    return store


@app.delete("/stores/{store_id}", status_code=204)
def delete_store(store_id: int, session: Session = Depends(get_session)):
    """Sletter en butik permanent."""
    store = session.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Butik ikke fundet")
    session.delete(store)
    session.commit()


@app.get("/webhook/store-entered/{store_id}")
def store_entered(store_id: int, session: Session = Depends(get_session)):
    """
    Kaldes af Home Assistant, når du krydser ind i en butiks geofence-zone.
    Returnerer den aktuelle indkøbsliste som en formateret tekst, klar til
    at blive læst højt (TTS) eller sendt som notifikation.
    """
    store = session.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Butik ikke fundet")

    statement = (
        select(Item)
        .where(Item.done == False)  # noqa: E712
        .order_by(Item.added_at)
    )
    items = session.exec(statement).all()

    if not items:
        message = f"Du har ikke noget på listen til {store.name}."
    else:
        names = ", ".join(item.name for item in items)
        message = f"Du er ved {store.name}. Husk: {names}."

    return {
        "store_name": store.name,
        "item_count": len(items),
        "items": [item.name for item in items],
        "message": message,
    }


@app.get("/webhook/nearest-store")
def nearest_store(lat: float, lon: float, max_distance_m: int = 150, session: Session = Depends(get_session)):
    """
    Kaldes af Home Assistant med telefonens aktuelle GPS-position (ikke en
    zone-id). Finder den butik hvis gemte koordinat er tættest på, ved en
    ren afstandsberegning - løser problemet med at butikker der ligger tæt
    på hinanden (under GPS-nøjagtighedens opløsning) giver overlappende zoner.

    max_distance_m er en sikkerhedsgrænse: hvis end ikke den nærmeste butik
    er inden for denne afstand, antager vi du ikke reelt er ved nogen af dem.
    """
    stores = session.exec(select(Store)).all()
    if not stores:
        raise HTTPException(status_code=404, detail="Ingen butikker oprettet endnu")

    nearest = min(stores, key=lambda s: haversine_m(lat, lon, s.latitude, s.longitude))
    distance = haversine_m(lat, lon, nearest.latitude, nearest.longitude)

    if distance > max_distance_m:
        return {
            "store_name": None,
            "distance_m": round(distance),
            "message": "Ikke i nærheden af nogen kendt butik.",
        }

    statement = (
        select(Item)
        .where(Item.done == False)  # noqa: E712
        .order_by(Item.added_at)
    )
    items = session.exec(statement).all()

    if not items:
        message = f"Du har ikke noget på listen til {nearest.name}."
    else:
        names = ", ".join(item.name for item in items)
        message = f"Du er ved {nearest.name}. Husk: {names}."

    return {
        "store_name": nearest.name,
        "distance_m": round(distance),
        "item_count": len(items),
        "items": [item.name for item in items],
        "message": message,
    }


def _log_proximity_check(
    session: Session,
    lat: float,
    lon: float,
    nearest_store_name: Optional[str],
    distance_m: Optional[int],
    should_notify: bool,
) -> None:
    """Logger et proximity-tjek til diagnostik."""
    log_entry = ProximityCheckLog(
        lat=lat,
        lon=lon,
        nearest_store_name=nearest_store_name,
        distance_m=distance_m,
        should_notify=should_notify,
    )
    session.add(log_entry)
    session.commit()


def _log_notification(
    session: Session,
    lat: float,
    lon: float,
    store: Store,
    distance_m: int,
    threshold_m: int,
    message: str,
    emulated: bool = False,
) -> None:
    """Logger en RENT FAKTISK udløst notifikation (should_notify=True), til
    senere fejlsøgning af falske positiver."""
    log_entry = NotificationLog(
        lat=lat,
        lon=lon,
        store_id=store.id,
        store_name=store.name,
        store_latitude=store.latitude,
        store_longitude=store.longitude,
        distance_m=distance_m,
        threshold_m=threshold_m,
        message=message,
        emulated=emulated,
    )
    session.add(log_entry)
    session.commit()


def _find_nearest_store(session: Session, lat: float, lon: float):
    """Finder nærmeste butik og afstanden til den, eller (None, None) hvis
    ingen butikker er oprettet endnu."""
    stores = session.exec(select(Store)).all()
    if not stores:
        return None, None
    nearest = min(stores, key=lambda s: haversine_m(lat, lon, s.latitude, s.longitude))
    distance = haversine_m(lat, lon, nearest.latitude, nearest.longitude)
    return nearest, distance


def _get_emulation_settings(session: Session) -> EmulationSettings:
    """Henter (eller opretter) den ene, faste emuleringstilstand-række."""
    settings = session.get(EmulationSettings, 1)
    if settings is None:
        settings = EmulationSettings(id=1, enabled=False)
        session.add(settings)
        session.commit()
        session.refresh(settings)
    return settings


def _get_proximity_state(session: Session) -> ProximityState:
    """Henter (eller opretter) den ene, faste tilstandsrække."""
    state = session.get(ProximityState, 1)
    if state is None:
        state = ProximityState(id=1, last_notified_store_id=None)
        session.add(state)
        session.commit()
        session.refresh(state)
    return state


@app.get("/webhook/check-proximity")
def check_proximity(
    lat: float,
    lon: float,
    threshold_m: int = 50,
    session: Session = Depends(get_session),
):
    """
    Kaldes løbende (fx hvert minut) af Home Assistant med telefonens aktuelle
    position - uafhængigt af HA-zoner. Finder nærmeste butik, og afgør om der
    er tale om en NY ankomst (should_notify=True), eller om der allerede er
    advaret om denne butik (should_notify=False), så gentagne kald ikke
    spammer med samme besked mens man står stille i butikken.

    Nulstiller automatisk "husket" tilstand når man bevæger sig væk igen,
    så man kan blive advaret igen ved næste besøg.
    """
    stores = session.exec(select(Store)).all()
    state = _get_proximity_state(session)
    emulation = _get_emulation_settings(session)

    if not stores:
        return {"should_notify": False, "store_name": None, "message": "Ingen butikker oprettet endnu."}

    nearest = min(stores, key=lambda s: haversine_m(lat, lon, s.latitude, s.longitude))
    distance = haversine_m(lat, lon, nearest.latitude, nearest.longitude)

    if emulation.enabled:
        items = session.exec(
            select(Item).where(Item.done == False).order_by(Item.added_at)  # noqa: E712
        ).all()
        if not items:
            message = f"[TEST] Du har ikke noget på listen til {nearest.name}."
            should_notify = False
        else:
            names = ", ".join(item.name for item in items)
            message = f"[TEST] Du er ved {nearest.name}. Husk: {names}."
            should_notify = True

        if should_notify:
            _log_notification(
                session, lat, lon, nearest, round(distance), threshold_m, message, emulated=True
            )
        _log_proximity_check(session, lat, lon, nearest.name, round(distance), should_notify)

        return {
            "should_notify": should_notify,
            "store_name": nearest.name,
            "distance_m": round(distance),
            "item_count": len(items),
            "items": [item.name for item in items],
            "message": message,
        }

    if distance > threshold_m:
        if state.last_notified_store_id is not None:
            state.last_notified_store_id = None
            state.updated_at = datetime.utcnow()
            session.add(state)
            session.commit()
        _log_proximity_check(session, lat, lon, nearest.name, round(distance), False)
        return {
            "should_notify": False,
            "store_name": nearest.name,
            "distance_m": round(distance),
            "message": f"Ikke i nærheden af {nearest.name} endnu ({round(distance)} m væk, grænse: {threshold_m} m).",
        }

    is_new_arrival = state.last_notified_store_id != nearest.id

    if is_new_arrival:
        state.last_notified_store_id = nearest.id
        state.updated_at = datetime.utcnow()
        session.add(state)
        session.commit()

    items = session.exec(
        select(Item).where(Item.done == False).order_by(Item.added_at)  # noqa: E712
    ).all()

    if not items:
        message = f"Du har ikke noget på listen til {nearest.name}."
    else:
        names = ", ".join(item.name for item in items)
        message = f"Du er ved {nearest.name}. Husk: {names}."

    should_notify = is_new_arrival and len(items) > 0

    if should_notify:
        _log_notification(
            session, lat, lon, nearest, round(distance), threshold_m, message
        )

    _log_proximity_check(session, lat, lon, nearest.name, round(distance), should_notify)

    return {
        "should_notify": should_notify,
        "store_name": nearest.name,
        "distance_m": round(distance),
        "item_count": len(items),
        "items": [item.name for item in items],
        "message": message,
    }


@app.get("/stores/nearby")
def stores_nearby(lat: float, lon: float, radius_m: int = 100):
    """
    Slår op efter butikker nær den angivne koordinat.
    Bruges af 'ny butik her'-knappen: brugeren sender sin nuværende GPS-position,
    og får en liste af forslag at vælge imellem (eller taste navn manuelt hvis intet passer).

    Prøver først Overpass (bredere dækning, alle butikstyper), og falder
    tilbage til Nominatim (kendte danske kæder, mere stabil drift) hvis
    Overpass fejler eller er utilgængelig.
    """
    try:
        suggestions = find_nearby_shops(lat, lon, radius_m)
        return {"suggestions": suggestions, "source": "overpass"}
    except Exception as overpass_exc:
        try:
            suggestions = find_nearby_shops_nominatim(lat, lon, radius_m)
            return {"suggestions": suggestions, "source": "nominatim_fallback"}
        except Exception as nominatim_exc:
            raise HTTPException(
                status_code=502,
                detail=(
                    f"Kunne ikke slå butikker op. Overpass: {overpass_exc} | "
                    f"Nominatim: {nominatim_exc}"
                ),
            )


@app.get("/diagnostics/ha-position")
def ha_position(entity_id: str = "device_tracker.samsung_s23_ultra"):
    """
    Spørger Home Assistants EGEN API om hvad den lige nu har registreret
    som position for en given device_tracker-enhed.

    Svarer altid med HTTP 200, selv ved fejl - fejldetaljer ligger i stedet
    i "success"/"error"-felterne. Det er bevidst: Cloudflare erstatter
    automatisk 4xx/5xx-svar med sin egen generiske fejlside.
    """
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return {
            "success": False,
            "error": "SUPERVISOR_TOKEN mangler - er 'homeassistant_api: true' sat i config.yaml, og er appen genstartet siden?",
        }

    url = f"http://supervisor/core/api/states/{entity_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
    except Exception as exc:
        return {"success": False, "error": f"Kunne ikke kontakte Home Assistant API: {exc}"}

    data = response.json()
    attributes = data.get("attributes", {})

    return {
        "success": True,
        "entity_id": entity_id,
        "state": data.get("state"),
        "latitude": attributes.get("latitude"),
        "longitude": attributes.get("longitude"),
        "gps_accuracy": attributes.get("gps_accuracy"),
        "last_changed": data.get("last_changed"),
        "last_updated": data.get("last_updated"),
    }


@app.get("/diagnostics/proximity-log")
def proximity_log(limit: int = 30, session: Session = Depends(get_session)):
    """Viser de seneste proximity-tjek, til fejlsøgning direkte i appen."""
    logs = session.exec(
        select(ProximityCheckLog)
        .order_by(ProximityCheckLog.checked_at.desc())
        .limit(limit)
    ).all()
    return {
        "count": len(logs),
        "entries": [
            {
                "checked_at": log.checked_at.isoformat(),
                "lat": log.lat,
                "lon": log.lon,
                "nearest_store_name": log.nearest_store_name,
                "distance_m": log.distance_m,
                "should_notify": log.should_notify,
            }
            for log in logs
        ],
    }


@app.get("/diagnostics/notification-log")
def notification_log(limit: int = 50, session: Session = Depends(get_session)):
    """Viser de seneste RENT FAKTISK udløste notifikationer."""
    logs = session.exec(
        select(NotificationLog)
        .order_by(NotificationLog.notified_at.desc())
        .limit(limit)
    ).all()
    return {
        "count": len(logs),
        "entries": [
            {
                "notified_at": log.notified_at.isoformat(),
                "phone_lat": log.lat,
                "phone_lon": log.lon,
                "store_id": log.store_id,
                "store_name": log.store_name,
                "store_latitude": log.store_latitude,
                "store_longitude": log.store_longitude,
                "distance_m": log.distance_m,
                "threshold_m": log.threshold_m,
                "message": log.message,
            }
            for log in logs
        ],
    }


@app.post("/diagnostics/report-missing-notification")
def report_missing_notification(
    report_in: MissedNotificationReportCreate, session: Session = Depends(get_session)
):
    """Kaldes fra appen, når du selv opdager at en forventet besked IKKE kom."""
    nearest, distance = _find_nearest_store(session, report_in.lat, report_in.lon)

    item_count = len(
        session.exec(select(Item).where(Item.done == False)).all()  # noqa: E712
    )

    report = MissedNotificationReport(
        lat=report_in.lat,
        lon=report_in.lon,
        nearest_store_name=nearest.name if nearest else None,
        distance_m=round(distance) if distance is not None else None,
        item_count=item_count,
        note=report_in.note,
    )
    session.add(report)
    session.commit()
    session.refresh(report)

    return {
        "success": True,
        "reported_at": report.reported_at.isoformat(),
        "nearest_store_name": report.nearest_store_name,
        "distance_m": report.distance_m,
        "item_count": report.item_count,
    }


@app.get("/diagnostics/missing-notification-log")
def missing_notification_log(limit: int = 50, session: Session = Depends(get_session)):
    """Viser tidligere rapporterede 'jeg fik ikke en besked'-hændelser."""
    logs = session.exec(
        select(MissedNotificationReport)
        .order_by(MissedNotificationReport.reported_at.desc())
        .limit(limit)
    ).all()
    return {
        "count": len(logs),
        "entries": [
            {
                "reported_at": log.reported_at.isoformat(),
                "lat": log.lat,
                "lon": log.lon,
                "nearest_store_name": log.nearest_store_name,
                "distance_m": log.distance_m,
                "item_count": log.item_count,
                "note": log.note,
            }
            for log in logs
        ],
    }


@app.get("/diagnostics/emulation-mode")
def get_emulation_mode(session: Session = Depends(get_session)):
    """Viser om test-tilstanden (emulering) er slået til eller fra."""
    settings = _get_emulation_settings(session)
    return {"enabled": settings.enabled, "updated_at": settings.updated_at.isoformat()}


@app.post("/diagnostics/emulation-mode")
def set_emulation_mode(enabled: bool, session: Session = Depends(get_session)):
    """Slår test-tilstanden til/fra."""
    settings = _get_emulation_settings(session)
    settings.enabled = enabled
    settings.updated_at = datetime.utcnow()
    session.add(settings)
    session.commit()
    session.refresh(settings)
    return {"enabled": settings.enabled, "updated_at": settings.updated_at.isoformat()}


@app.post("/diagnostics/log-all-store-distances")
def log_all_store_distances(lat: float, lon: float, session: Session = Depends(get_session)):
    """Beregner og logger afstanden fra (lat, lon) til HVER ENESTE oprettede butik."""
    stores = session.exec(select(Store)).all()
    if not stores:
        return {"count": 0, "entries": []}

    checked_at = datetime.utcnow()
    results = []
    for store in stores:
        distance = round(haversine_m(lat, lon, store.latitude, store.longitude))
        log_entry = StoreDistanceCheck(
            checked_at=checked_at,
            lat=lat,
            lon=lon,
            store_id=store.id,
            store_name=store.name,
            distance_m=distance,
        )
        session.add(log_entry)
        results.append({
            "store_id": store.id,
            "store_name": store.name,
            "store_latitude": store.latitude,
            "store_longitude": store.longitude,
            "distance_m": distance,
        })
    session.commit()

    results.sort(key=lambda r: r["distance_m"])
    return {
        "checked_at": checked_at.isoformat(),
        "lat": lat,
        "lon": lon,
        "count": len(results),
        "entries": results,
    }


@app.get("/diagnostics/store-distance-log")
def store_distance_log(limit: int = 100, session: Session = Depends(get_session)):
    """Viser tidligere loggede afstandstjek til alle butikker, nyeste først."""
    logs = session.exec(
        select(StoreDistanceCheck)
        .order_by(StoreDistanceCheck.checked_at.desc(), StoreDistanceCheck.distance_m.asc())
        .limit(limit)
    ).all()
    return {
        "count": len(logs),
        "entries": [
            {
                "checked_at": log.checked_at.isoformat(),
                "lat": log.lat,
                "lon": log.lon,
                "store_name": log.store_name,
                "distance_m": log.distance_m,
            }
            for log in logs
        ],
    }


@app.get("/backup")
def create_backup(session: Session = Depends(get_session)):
    """Eksporterer alle butikker, varer og bonner (Indscan bon) som JSON.
    Bonner eksporteres med deres varelinjer nestet under hver bon, da
    ReceiptItem.receipt_id peger på et database-genereret id, som IKKE er
    stabilt på tværs af en gendannelse (se restore_backup)."""
    stores = session.exec(select(Store)).all()
    items = session.exec(select(Item)).all()
    receipts = session.exec(select(Receipt).order_by(Receipt.created_at)).all()

    receipts_export = []
    for r in receipts:
        receipt_items = session.exec(
            select(ReceiptItem).where(ReceiptItem.receipt_id == r.id).order_by(ReceiptItem.id)
        ).all()
        receipts_export.append({
            "store_name": r.store_name,
            "purchase_date": r.purchase_date.isoformat() if r.purchase_date else None,
            "total": r.total,
            "created_at": r.created_at.isoformat(),
            "raw_model_output": r.raw_model_output,
            "items": [
                {"name": ri.name, "price": ri.price, "quantity": ri.quantity}
                for ri in receipt_items
            ],
        })

    return {
        "backup_created_at": datetime.utcnow().isoformat(),
        "stores": [
            {
                "name": s.name,
                "latitude": s.latitude,
                "longitude": s.longitude,
                "radius_m": s.radius_m,
                "osm_id": s.osm_id,
            }
            for s in stores
        ],
        "items": [
            {"name": i.name, "done": i.done}
            for i in items
        ],
        "receipts": receipts_export,
    }


@app.post("/restore")
def restore_backup(backup: dict, session: Session = Depends(get_session)):
    """Gendanner butikker, varer og bonner (Indscan bon) fra en JSON-backup
    (fra /backup). Tilføjer - sletter ikke eksisterende data.

    IDEMPOTENT: springer over alt der allerede findes, så det er sikkert at
    gendanne samme backup-fil flere gange i træk (fx efter en fejl, eller
    ved en forglemmelse) uden at ende med de samme butikker/varer/bonner
    gentaget for hver gendannelse. Dublet-tjek er "godt nok" (navn/felter),
    ikke kryptografisk - se de enkelte nøgler nedenfor."""
    stores_added = 0
    stores_skipped = 0
    items_added = 0
    items_skipped = 0
    receipts_added = 0
    receipts_skipped = 0
    receipt_items_added = 0

    # --- Butikker: dublet hvis samme osm_id, ELLER samme navn (case-insensitivt) ---
    existing_stores = session.exec(select(Store)).all()
    known_store_names = {s.name.strip().lower() for s in existing_stores}
    known_store_osm_ids = {s.osm_id for s in existing_stores if s.osm_id}

    for store_data in backup.get("stores", []):
        name = store_data["name"]
        osm_id = store_data.get("osm_id")
        is_duplicate = (
            (osm_id and osm_id in known_store_osm_ids)
            or name.strip().lower() in known_store_names
        )
        if is_duplicate:
            stores_skipped += 1
            continue
        store = Store(
            name=name,
            latitude=store_data["latitude"],
            longitude=store_data["longitude"],
            radius_m=store_data.get("radius_m", 50),
            osm_id=osm_id,
        )
        session.add(store)
        known_store_names.add(name.strip().lower())
        if osm_id:
            known_store_osm_ids.add(osm_id)
        stores_added += 1

    # --- Varer: dublet hvis samme navn (case-insensitivt) OG samme afkrydsningsstatus ---
    existing_items = session.exec(select(Item)).all()
    known_item_keys = {(i.name.strip().lower(), i.done) for i in existing_items}

    for item_data in backup.get("items", []):
        name = item_data["name"]
        done = item_data.get("done", False)
        key = (name.strip().lower(), done)
        if key in known_item_keys:
            items_skipped += 1
            continue
        item = Item(name=name, done=done)
        session.add(item)
        known_item_keys.add(key)
        items_added += 1

    # --- Bonner: dublet hvis samme butiksnavn + købsdato + total ---
    existing_receipts = session.exec(select(Receipt)).all()
    known_receipt_keys = {
        (r.store_name.strip().lower(), r.purchase_date, r.total)
        for r in existing_receipts
    }

    for receipt_data in backup.get("receipts", []):
        store_name = receipt_data.get("store_name") or "Ukendt butik"
        purchase_date_str = receipt_data.get("purchase_date")
        purchase_date = date.fromisoformat(purchase_date_str) if purchase_date_str else None
        total = receipt_data.get("total")
        key = (store_name.strip().lower(), purchase_date, total)
        if key in known_receipt_keys:
            receipts_skipped += 1
            continue

        receipt = Receipt(
            store_name=store_name,
            purchase_date=purchase_date,
            total=total,
            raw_model_output=receipt_data.get("raw_model_output"),
        )
        created_at_str = receipt_data.get("created_at")
        if created_at_str:
            try:
                receipt.created_at = datetime.fromisoformat(created_at_str)
            except ValueError:
                pass  # behold default (nu), i stedet for at fejle hele gendannelsen
        session.add(receipt)
        # flush (ikke commit) tildeler receipt.id med det samme, uden at
        # afslutte transaktionen - så ReceiptItem kan sætte sin foreign key,
        # og hele gendannelsen forbliver én atomisk handling
        session.flush()
        known_receipt_keys.add(key)
        receipts_added += 1

        for item_in in receipt_data.get("items", []):
            name = (item_in.get("name") or "").strip()
            if not name:
                continue
            session.add(ReceiptItem(
                receipt_id=receipt.id,
                name=name,
                price=item_in.get("price", 0),
                quantity=item_in.get("quantity", 1),
            ))
            receipt_items_added += 1

    session.commit()

    return {
        "success": True,
        "stores_restored": stores_added,
        "stores_skipped_duplicate": stores_skipped,
        "items_restored": items_added,
        "items_skipped_duplicate": items_skipped,
        "receipts_restored": receipts_added,
        "receipts_skipped_duplicate": receipts_skipped,
        "receipt_items_restored": receipt_items_added,
    }


# ===== Over dato: varer derhjemme med en holdbarhedsdato =====

@app.post("/parse-date")
def parse_date_endpoint(text: str):
    """
    Fortolker en talt/skrevet dansk dato-tekst (fx "niende i syvende
    seksogtyve") til en rigtig dato. Bruges af "Over dato"-knappen, mellem
    at datoen tales ind og den vises til bekræftelse.
    """
    result = parse_danish_date(text)
    return {"input": text, "parsed_date": result.isoformat() if result else None}


@app.post("/expiry-items", response_model=ExpiryItem)
def add_expiry_item(item_in: ExpiryItemCreate, session: Session = Depends(get_session)):
    """Registrerer en vare derhjemme med en holdbarhedsdato."""
    name = item_in.name.strip()
    if name:
        name = name[0].upper() + name[1:]
    item = ExpiryItem(name=name, expiry_date=item_in.expiry_date)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@app.get("/expiry-items")
def list_expiry_items(session: Session = Depends(get_session)):
    """
    Henter alle 'over dato'-varer. Tjekker samtidig om nogen er blevet
    overskredet siden sidst, og lægger dem i så fald automatisk tilbage på
    selve indkøbslisten (kun én gang pr. vare, styret af
    added_to_shopping_list).
    """
    today = date.today()
    all_items = session.exec(select(ExpiryItem).order_by(ExpiryItem.expiry_date)).all()

    for item in all_items:
        if item.expiry_date < today and not item.added_to_shopping_list:
            shopping_name = item.name
            if shopping_name:
                shopping_name = shopping_name[0].upper() + shopping_name[1:]
            session.add(Item(name=shopping_name))
            item.added_to_shopping_list = True
            session.add(item)
    session.commit()

    all_items = session.exec(select(ExpiryItem).order_by(ExpiryItem.expiry_date)).all()

    return {
        "count": len(all_items),
        "entries": [
            {
                "id": i.id,
                "name": i.name,
                "expiry_date": i.expiry_date.isoformat(),
                "is_expired": i.expiry_date < today,
                "added_to_shopping_list": i.added_to_shopping_list,
            }
            for i in all_items
        ],
    }


@app.delete("/expiry-items/{item_id}", status_code=204)
def delete_expiry_item(item_id: int, session: Session = Depends(get_session)):
    """Sletter en 'over dato'-vare permanent."""
    item = session.get(ExpiryItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Vare ikke fundet")
    session.delete(item)
    session.commit()


# ===== Stemmerettelser: talegenkendelsen hører nogle ord konsekvent forkert =====
# (fx "roastbeef" -> "roskilde"). Anvendes klient-side (i frontend) på
# transskriberet tekst FØR den vises/gemmes, både på selve indkøbslisten og
# i "Over dato"-flowet.

@app.get("/voice-corrections")
def list_voice_corrections(session: Session = Depends(get_session)):
    """Henter alle gemte rettelser, til at bygge rettelses-cachen i frontend."""
    corrections = session.exec(
        select(VoiceCorrection).order_by(VoiceCorrection.wrong_text)
    ).all()
    return {
        "count": len(corrections),
        "entries": [
            {"id": c.id, "wrong_text": c.wrong_text, "correct_text": c.correct_text}
            for c in corrections
        ],
    }


@app.post("/voice-corrections", response_model=VoiceCorrection)
def add_voice_correction(
    correction_in: VoiceCorrectionCreate, session: Session = Depends(get_session)
):
    """Opretter en ny rettelse. wrong_text gemmes altid i små bogstaver,
    så opslag i frontend kan være case-insensitivt uden ekstra logik."""
    wrong = correction_in.wrong_text.strip().lower()
    correct = correction_in.correct_text.strip()
    if not wrong or not correct:
        raise HTTPException(status_code=400, detail="Begge felter skal udfyldes")
    correction = VoiceCorrection(wrong_text=wrong, correct_text=correct)
    session.add(correction)
    session.commit()
    session.refresh(correction)
    return correction


@app.delete("/voice-corrections/{correction_id}", status_code=204)
def delete_voice_correction(correction_id: int, session: Session = Depends(get_session)):
    """Sletter en rettelse permanent."""
    correction = session.get(VoiceCorrection, correction_id)
    if correction is None:
        raise HTTPException(status_code=404, detail="Rettelse ikke fundet")
    session.delete(correction)
    session.commit()


# ===== Udløbsnotifikation: daglig påmindelse om varer der snart går over dato =====

def _get_expiry_notification_settings(session: Session) -> ExpiryNotificationSettings:
    """Henter (eller opretter) den ene, faste indstillingsrække."""
    settings = session.get(ExpiryNotificationSettings, 1)
    if settings is None:
        settings = ExpiryNotificationSettings(id=1)
        session.add(settings)
        session.commit()
        session.refresh(settings)
    return settings


def _serialize_expiry_notification_settings(s: ExpiryNotificationSettings) -> dict:
    return {
        "enabled": s.enabled,
        "days_before": s.days_before,
        "notify_time": s.notify_time,
        "last_notified_date": s.last_notified_date.isoformat() if s.last_notified_date else None,
    }


@app.get("/settings/expiry-notification")
def get_expiry_notification_settings(session: Session = Depends(get_session)):
    """Henter de nuværende indstillinger for udløbsnotifikationen."""
    return _serialize_expiry_notification_settings(_get_expiry_notification_settings(session))


@app.patch("/settings/expiry-notification")
def update_expiry_notification_settings(
    update: ExpiryNotificationSettingsUpdate, session: Session = Depends(get_session)
):
    """Opdaterer indstillingerne. Kun de felter der rent faktisk sendes med,
    bliver ændret."""
    settings = _get_expiry_notification_settings(session)
    if update.enabled is not None:
        settings.enabled = update.enabled
    if update.days_before is not None:
        if update.days_before < 0:
            raise HTTPException(status_code=400, detail="days_before skal være 0 eller derover")
        settings.days_before = update.days_before
    if update.notify_time is not None:
        settings.notify_time = update.notify_time
    settings.updated_at = datetime.utcnow()
    session.add(settings)
    session.commit()
    session.refresh(settings)
    return _serialize_expiry_notification_settings(settings)


@app.get("/webhook/check-expiring-soon")
def check_expiring_soon(session: Session = Depends(get_session)):
    """
    Kaldes periodisk (fx hvert 5. minut) af en Home Assistant-automation.
    Sender IKKE selv en push-notifikation - returnerer blot should_notify +
    en besked, som automationen derefter sender via notify-servicen (samme
    mønster som /webhook/check-proximity, hvor Python-appen aldrig selv
    kalder HA's notify-API).

    Bruger last_notified_date til kun at give ÉN notifikation pr. dag,
    uanset hvor ofte automationen rent faktisk kalder dette endpoint - og
    "nu >= notify_time" (i stedet for eksakt match) så det stadig virker
    selvom automationen kun tjekker hvert 5./15. minut.
    """
    settings = _get_expiry_notification_settings(session)
    today = date.today()
    now_str = datetime.now().strftime("%H:%M")

    if not settings.enabled:
        return {"should_notify": False, "message": "Udløbsnotifikation er slået fra."}

    if settings.last_notified_date == today:
        return {"should_notify": False, "message": "Allerede sendt i dag."}

    if now_str < settings.notify_time:
        return {
            "should_notify": False,
            "message": f"Endnu ikke tid ({now_str} < {settings.notify_time}).",
        }

    threshold_date = today + timedelta(days=settings.days_before)
    items = session.exec(
        select(ExpiryItem)
        .where(ExpiryItem.expiry_date >= today)
        .where(ExpiryItem.expiry_date <= threshold_date)
        .order_by(ExpiryItem.expiry_date)
    ).all()

    # Marker dagen som tjekket uanset udfald, så vi ikke bliver ved med at
    # tjekke resten af dagen (og evt. rammer en race hvis automationen
    # kalder meget hyppigt).
    settings.last_notified_date = today
    settings.updated_at = datetime.utcnow()
    session.add(settings)
    session.commit()

    if not items:
        return {"should_notify": False, "message": "Ingen varer udløber snart."}

    names = ", ".join(f"{i.name} ({i.expiry_date.strftime('%d/%m')})" for i in items)
    message = f"Snart over dato: {names}."

    return {
        "should_notify": True,
        "item_count": len(items),
        "items": [i.name for i in items],
        "message": message,
    }


# ===== Indscan bon: scan en kassebon med kameraet, Claude udleder butik/
# varer/pris. Selve billedet gemmes ALDRIG - hverken permanent eller
# midlertidigt - kun det udledte resultat, og kun efter brugeren har set
# og evt. rettet det (samme "gennemsyn før gem"-princip som stemmeflowet i
# "Over dato"). Se app/receipt_scan.py for selve Claude-integrationen. =====

_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


@app.post("/receipts/scan")
async def scan_receipt(file: UploadFile = File(...)):
    """
    Tager imod et bon-billede, sender det til Claude, og returnerer det
    UDLEDTE resultat - gemmer INTET i databasen her. Frontend viser
    resultatet til gennemsyn/rettelse, og gemmer først via POST /receipts,
    når brugeren aktivt godkender.

    Svarer altid HTTP 200, med success/error i JSON-body i stedet for en
    4xx/5xx-statuskode - samme mønster som /diagnostics/*-endpoints, og af
    samme grund: Cloudflare Tunnel erstatter automatisk fejl-statuskoder med
    sin egen generiske fejlside, hvilket ville skjule selve fejlbeskeden for
    brugeren (og dermed umuliggøre "prøv igen" vs. "indtast manuelt"-valget,
    som er selve pointen med denne fejlhåndtering).
    """
    if file.content_type not in _ALLOWED_IMAGE_TYPES:
        return {
            "success": False,
            "error": f"Filtypen '{file.content_type}' understøttes ikke - brug et almindeligt billedformat.",
        }

    image_bytes = await file.read()
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    try:
        result = extract_receipt(image_bytes, file.content_type, api_key)
    except ReceiptScanError as exc:
        return {"success": False, "error": str(exc)}
    except Exception as exc:  # uventet fejl - vis den stadig, i stedet for at fejle stille
        logging.getLogger("indkobsliste.main").exception("Uventet fejl i scan_receipt")
        return {"success": False, "error": f"Uventet fejl: {exc}"}

    return {"success": True, **result}


@app.post("/receipts", response_model=Receipt)
def save_receipt(receipt_in: ReceiptCreate, session: Session = Depends(get_session)):
    """Gemmer det ENDELIGE, godkendte resultat - uanset om det stammer fra en
    Claude-scanning (evt. rettet af brugeren først) eller er tastet fuldt
    manuelt (fx hvis scanningen fejlede). raw_model_output er kun sat i det
    første tilfælde, til fejlsøgning."""
    receipt = Receipt(
        store_name=receipt_in.store_name.strip() or "Ukendt butik",
        purchase_date=receipt_in.purchase_date,
        total=receipt_in.total,
        raw_model_output=receipt_in.raw_model_output,
    )
    session.add(receipt)
    session.commit()
    session.refresh(receipt)

    for item_in in receipt_in.items:
        name = item_in.name.strip()
        if not name:
            continue
        session.add(ReceiptItem(
            receipt_id=receipt.id,
            name=name,
            price=item_in.price,
            quantity=item_in.quantity,
        ))
    session.commit()
    session.refresh(receipt)
    return receipt


def _get_receipt_or_404(receipt_id: int, session: Session) -> Receipt:
    receipt = session.get(Receipt, receipt_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="Bon ikke fundet")
    return receipt


@app.get("/receipts")
def list_receipts(limit: int = 100, session: Session = Depends(get_session)):
    """Arkiv-liste, nyeste først. Kun sammendrag (uden varelinjer) - se
    GET /receipts/{id} for detaljer om én bestemt bon."""
    receipts = session.exec(
        select(Receipt).order_by(Receipt.created_at.desc()).limit(limit)
    ).all()
    entries = []
    for r in receipts:
        item_count = len(
            session.exec(select(ReceiptItem).where(ReceiptItem.receipt_id == r.id)).all()
        )
        entries.append({
            "id": r.id,
            "store_name": r.store_name,
            "purchase_date": r.purchase_date.isoformat() if r.purchase_date else None,
            "total": r.total,
            "item_count": item_count,
            "created_at": r.created_at.isoformat(),
        })
    return {"count": len(entries), "entries": entries}


@app.get("/receipts/{receipt_id}")
def get_receipt(receipt_id: int, session: Session = Depends(get_session)):
    """Én bons fulde detaljer, inkl. alle varelinjer."""
    receipt = _get_receipt_or_404(receipt_id, session)
    items = session.exec(
        select(ReceiptItem).where(ReceiptItem.receipt_id == receipt_id).order_by(ReceiptItem.id)
    ).all()
    return {
        "id": receipt.id,
        "store_name": receipt.store_name,
        "purchase_date": receipt.purchase_date.isoformat() if receipt.purchase_date else None,
        "total": receipt.total,
        "created_at": receipt.created_at.isoformat(),
        "items": [
            {"id": i.id, "name": i.name, "price": i.price, "quantity": i.quantity}
            for i in items
        ],
    }


@app.delete("/receipts/{receipt_id}", status_code=204)
def delete_receipt(receipt_id: int, session: Session = Depends(get_session)):
    """Sletter en bon og alle dens varelinjer permanent."""
    receipt = _get_receipt_or_404(receipt_id, session)
    items = session.exec(select(ReceiptItem).where(ReceiptItem.receipt_id == receipt_id)).all()
    for item in items:
        session.delete(item)
    session.delete(receipt)
    session.commit()


@app.get("/receipts/price-history/lookup")
def receipt_price_history(item_name: str, session: Session = Depends(get_session)):
    """
    Prisudvikling for én vare over tid, på tværs af alle scannede/indtastede
    bonner - til at se om en vare er blevet dyrere, eller sammenligne butikker.

    Matcher ustrengt (case-insensitive, delvis substreng), da samme vare
    sjældent hedder præcis det samme fra bon til bon (fx "Øko Mælk 1L" vs.
    "Mælk øko 1l"). Sorteret ældst-til-nyest, så frontend kan tegne den
    direkte som en tidslinje.
    """
    needle = item_name.strip().lower()
    if not needle:
        return {"item_name": item_name, "count": 0, "entries": []}

    all_items = session.exec(select(ReceiptItem)).all()
    matches = [i for i in all_items if needle in i.name.lower()]

    entries = []
    for match in matches:
        receipt = session.get(Receipt, match.receipt_id)
        if receipt is None:
            continue
        entries.append({
            "receipt_id": receipt.id,
            "date": (receipt.purchase_date or receipt.created_at.date()).isoformat(),
            "store_name": receipt.store_name,
            "item_name": match.name,
            "price": match.price,
            "quantity": match.quantity,
        })

    entries.sort(key=lambda e: e["date"])
    return {"item_name": item_name, "count": len(entries), "entries": entries}


# Serverer den simple frontend-side. Tilgås via /app/index.html
app.mount("/app", StaticFiles(directory="frontend", html=True), name="frontend")
