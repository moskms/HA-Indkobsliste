# Sidst opdateret: 2026-07-11 | Version: 2.0.7
from contextlib import asynccontextmanager
from typing import List, Optional
from datetime import datetime
import logging
import os

import requests

from fastapi import FastAPI, Depends, HTTPException
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
)
from app.overpass import find_nearby_shops
from app.nominatim import find_nearby_shops_nominatim, haversine_m

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
    """Logger et proximity-tjek til diagnostik, og beholder kun de seneste 200 rækker."""
    log_entry = ProximityCheckLog(
        lat=lat,
        lon=lon,
        nearest_store_name=nearest_store_name,
        distance_m=distance_m,
        should_notify=should_notify,
    )
    session.add(log_entry)
    session.commit()

    # Ryd op: behold kun de seneste 200 rækker, så tabellen ikke vokser uendeligt
    all_logs = session.exec(
        select(ProximityCheckLog).order_by(ProximityCheckLog.checked_at.desc())
    ).all()
    for old_entry in all_logs[200:]:
        session.delete(old_entry)
    if len(all_logs) > 200:
        session.commit()


def _log_notification(
    session: Session,
    lat: float,
    lon: float,
    store: Store,
    distance_m: int,
    threshold_m: int,
    message: str,
) -> None:
    """Logger en RENT FAKTISK udløst notifikation (should_notify=True), til
    senere fejlsøgning af falske positiver. Beholder kun de seneste 500 rækker."""
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
    )
    session.add(log_entry)
    session.commit()

    all_logs = session.exec(
        select(NotificationLog).order_by(NotificationLog.notified_at.desc())
    ).all()
    for old_entry in all_logs[500:]:
        session.delete(old_entry)
    if len(all_logs) > 500:
        session.commit()


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

    if not stores:
        return {"should_notify": False, "store_name": None, "message": "Ingen butikker oprettet endnu."}

    nearest = min(stores, key=lambda s: haversine_m(lat, lon, s.latitude, s.longitude))
    distance = haversine_m(lat, lon, nearest.latitude, nearest.longitude)

    if distance > threshold_m:
        # Uden for rækkevidde af enhver butik - nulstil hukommelsen, så
        # næste besøg (i denne eller en anden butik) giver besked igen.
        if state.last_notified_store_id is not None:
            state.last_notified_store_id = None
            state.updated_at = datetime.utcnow()
            session.add(state)
            session.commit()
        _log_proximity_check(session, lat, lon, nearest.name, round(distance), False)
        return {
            "should_notify": False,
            "store_name": None,
            "distance_m": round(distance),
            "message": "Ikke i nærheden af nogen kendt butik.",
        }

    # Inden for rækkevidde af 'nearest' - kun ny besked hvis det er en anden
    # butik end sidst, eller hvis vi ikke har advaret om nogen for nylig.
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

    # Kun rent faktisk notifikationsværdigt hvis det er en ny ankomst OG der
    # står noget på listen - ingen grund til at forstyrre med en besked om
    # at listen er tom.
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
    som position for en given device_tracker-enhed. Bruges til at
    sammenligne "hvad telefonens browser selv ser" (vist i header'en)
    med "hvad HA rent faktisk har liggende" - hvis de to afviger
    markant, bekræfter det at HA's baggrunds-lokationsopdatering halter.

    Kræver 'homeassistant_api: true' i config.yaml, som automatisk giver
    denne container adgang via SUPERVISOR_TOKEN miljøvariablen.

    Svarer altid med HTTP 200, selv ved fejl - fejldetaljer ligger i stedet
    i "success"/"error"-felterne. Det er bevidst: Cloudflare erstatter
    automatisk 4xx/5xx-svar med sin egen generiske fejlside, hvilket ville
    skjule vores faktiske, brugbare fejlbesked.
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
    """
    Viser de seneste proximity-tjek, til fejlsøgning direkte i appen.
    Gør det muligt at se om Home Assistant rent faktisk kalder
    /webhook/check-proximity regelmæssigt, og hvilke koordinater den
    sender - uden at skulle grave i HA's egne logs.
    """
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
    """
    Viser de seneste RENT FAKTISK udløste notifikationer (should_notify=True),
    med telefonens position og den butik der udløste beskeden. Modsat
    /diagnostics/proximity-log (som roterer efter 200/30 rækker og drukner i
    "ikke i nærheden"-tjek), dækker denne langt længere tid tilbage - god til
    at undersøge falske positiver bagudrettet.
    """
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


@app.get("/backup")
def create_backup(session: Session = Depends(get_session)):
    """
    Eksporterer alle butikker og varer som JSON. Brug denne FØR risikable
    ændringer (versionsopgraderinger, geninstallation af appen, HA-opdateringer),
    så data altid kan gendannes, uanset hvad der går galt på HA-siden.
    """
    stores = session.exec(select(Store)).all()
    items = session.exec(select(Item)).all()

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
    }


@app.post("/restore")
def restore_backup(backup: dict, session: Session = Depends(get_session)):
    """
    Gendanner butikker og varer fra en JSON-backup (fra /backup).
    Tilføjer til eksisterende data - sletter IKKE noget i forvejen,
    så det er sikkert at bruge selvom der allerede er lidt data.
    """
    stores_added = 0
    items_added = 0

    for store_data in backup.get("stores", []):
        store = Store(
            name=store_data["name"],
            latitude=store_data["latitude"],
            longitude=store_data["longitude"],
            radius_m=store_data.get("radius_m", 50),
            osm_id=store_data.get("osm_id"),
        )
        session.add(store)
        stores_added += 1

    for item_data in backup.get("items", []):
        item = Item(name=item_data["name"], done=item_data.get("done", False))
        session.add(item)
        items_added += 1

    session.commit()

    return {
        "success": True,
        "stores_restored": stores_added,
        "items_restored": items_added,
    }


# Serverer den simple frontend-side. Tilgås via /app/index.html
app.mount("/app", StaticFiles(directory="frontend", html=True), name="frontend")
