# Sidst opdateret: 2026-07-04
from contextlib import asynccontextmanager
from typing import List, Optional
from datetime import datetime
import logging

from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select

from app.database import init_db, get_session
from app.models import Item, ItemCreate, Store, StoreCreate, StoreUpdate, ProximityState, ProximityCheckLog
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
    """Opdaterer en butiks koordinater og radius, fx efter GPS-kalibrering."""
    store = session.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Butik ikke fundet")
    store.latitude = update.latitude
    store.longitude = update.longitude
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

    _log_proximity_check(session, lat, lon, nearest.name, round(distance), is_new_arrival)

    return {
        "should_notify": is_new_arrival,
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


# Serverer den simple frontend-side. Tilgås via /app/index.html
app.mount("/app", StaticFiles(directory="frontend", html=True), name="frontend")
