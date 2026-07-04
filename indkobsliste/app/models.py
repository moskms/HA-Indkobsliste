"""
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
