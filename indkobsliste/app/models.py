"""
Sidst opdateret: 2026-07-04

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


class StoreUpdate(BaseModel):
    """Input-schema til PATCH /stores/{id} - bruges til at kalibrere koordinater/radius,
    fx efter at have indsamlet GPS-punkter mens man gik rundt i butikken."""
    latitude: float
    longitude: float
    radius_m: int


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
