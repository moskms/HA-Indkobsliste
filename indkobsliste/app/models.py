"""
Sidst opdateret: 2026-07-18 | Version: 2.0.15

Databasemodeller for indkøbsliste-appen.

To tabeller i denne omgang:
- Item: varer på indkøbslisten
- Store: faste butikker med koordinater (bruges senere til geofencing)
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from sqlmodel import SQLModel, Field


class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    added_at: datetime = Field(default_factory=datetime.utcnow)
    done: bool = Field(default=False)


class Store(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    latitude: float
    longitude: float
    radius_m: int = Field(default=50)  # geofence-radius i meter
    osm_id: Optional[str] = Field(default=None)  # hvis fundet via Overpass
    shop_type: Optional[str] = Field(default=None)  # fx 'supermarket', 'bakery' - fra OSM
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ItemCreate(BaseModel):
    """Input-schema til POST /items - kun navnet er nødvendigt."""
    name: str


class StoreCreate(BaseModel):
    """Input-schema til POST /stores - manuel oprettelse af en fast butik."""
    name: str
    latitude: float
    longitude: float
    radius_m: int = 50
    shop_type: Optional[str] = None
    osm_id: Optional[str] = None


class StoreUpdate(BaseModel):
    """Input-schema til PATCH /stores/{id} - bruges enten til GPS-kalibrering
    (koordinater/radius), eller til at omdøbe en butik, så flere butikker med
    samme kædenavn (fx 'Netto') kan skelnes fra hinanden."""
    name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius_m: Optional[int] = None


class ProximityState(SQLModel, table=True):
    """
    Enkelt-række-tabel der husker hvilken butik der sidst er blevet
    notificeret om, så løbende positionstjek (fx hvert minut) ikke
    sender samme besked igen og igen, mens man stadig er i nærheden.
    Nulstilles når man bevæger sig væk fra alle butikker igen.
    """
    id: Optional[int] = Field(default=1, primary_key=True)
    last_notified_store_id: Optional[int] = Field(default=None)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ProximityCheckLog(SQLModel, table=True):
    """
    Logger hvert kald til /webhook/check-proximity, til diagnostik.
    Gør det muligt at se direkte i appen om Home Assistant rent faktisk
    kalder endpointet regelmæssigt, og hvilke koordinater den sender -
    uden at skulle grave i HA's egne logs/historik.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    checked_at: datetime = Field(default_factory=datetime.utcnow)
    lat: float
    lon: float
    nearest_store_name: Optional[str] = Field(default=None)
    distance_m: Optional[int] = Field(default=None)
    should_notify: bool = Field(default=False)


class NotificationLog(SQLModel, table=True):
    """
    Logger hver gang en proximity-notifikation RENT FAKTISK udløses
    (should_notify=True i /webhook/check-proximity). Modsat ProximityCheckLog
    (som logger ALLE kald, inkl. "ikke i nærheden"), indeholder denne kun de
    events hvor en besked reelt blev sendt til telefonen - så historikken
    dækker langt længere tid tilbage (ingen 30-rækkers begrænsning i praksis),
    og gør det muligt bagudrettet at se præcis hvilken position telefonen
    havde, og hvilken butik/afstand der udløste en given besked.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    notified_at: datetime = Field(default_factory=datetime.utcnow)
    lat: float
    lon: float
    store_id: int
    store_name: str
    store_latitude: float
    store_longitude: float
    distance_m: int
    threshold_m: int
    message: str
    emulated: bool = Field(default=False)


class MissedNotificationReport(SQLModel, table=True):
    """
    Brugerens EGEN rapport om at en forventet notifikation IKKE blev modtaget
    - oprettes manuelt via en knap i appen, mens man står ved/på vej til en
    butik og ved at der er varer på listen. Gemmer telefonens position samt
    den nærmeste butik/afstand PÅ RAPPORTERINGSTIDSPUNKTET, beregnet med
    samme logik som /webhook/check-proximity - så rapporten bagefter kan
    sammenholdes med hvad HA's periodiske kald reelt så på samme tidspunkt.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    reported_at: datetime = Field(default_factory=datetime.utcnow)
    lat: float
    lon: float
    nearest_store_name: Optional[str] = Field(default=None)
    distance_m: Optional[int] = Field(default=None)
    item_count: int = Field(default=0)
    note: Optional[str] = Field(default=None)


class MissedNotificationReportCreate(BaseModel):
    """Input-schema til POST /diagnostics/report-missing-notification."""
    lat: float
    lon: float
    note: Optional[str] = None


class EmulationSettings(SQLModel, table=True):
    """
    Enkelt-række-tabel der styrer TEST-TILSTANDEN i Diagnostik-fanen.
    Når enabled=True, tvinger /webhook/check-proximity should_notify=True
    for nærmeste butik (med den RIGTIGE besked fra den rigtige liste),
    uanset faktisk afstand - så man kan bekræfte at telefonen modtager
    notifikationer, og hvornår, uden selv at skulle stå i en butik.
    HUSK at slå den fra igen efter test, ellers sender den ved hvert kald.
    """
    id: Optional[int] = Field(default=1, primary_key=True)
    enabled: bool = Field(default=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
