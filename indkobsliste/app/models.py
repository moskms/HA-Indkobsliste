# Sidst opdateret: 2026-07-19 | Version: 2.0.19
"""
Databasemodeller for indkøbsliste-appen.
"""
from datetime import datetime, date
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
    radius_m: int = Field(default=50)
    osm_id: Optional[str] = Field(default=None)
    shop_type: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ItemCreate(BaseModel):
    name: str


class StoreCreate(BaseModel):
    name: str
    latitude: float
    longitude: float
    radius_m: int = 50
    shop_type: Optional[str] = None
    osm_id: Optional[str] = None


class StoreUpdate(BaseModel):
    name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius_m: Optional[int] = None


class ProximityState(SQLModel, table=True):
    id: Optional[int] = Field(default=1, primary_key=True)
    last_notified_store_id: Optional[int] = Field(default=None)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ProximityCheckLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    checked_at: datetime = Field(default_factory=datetime.utcnow)
    lat: float
    lon: float
    nearest_store_name: Optional[str] = Field(default=None)
    distance_m: Optional[int] = Field(default=None)
    should_notify: bool = Field(default=False)


class NotificationLog(SQLModel, table=True):
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
    id: Optional[int] = Field(default=None, primary_key=True)
    reported_at: datetime = Field(default_factory=datetime.utcnow)
    lat: float
    lon: float
    nearest_store_name: Optional[str] = Field(default=None)
    distance_m: Optional[int] = Field(default=None)
    item_count: int = Field(default=0)
    note: Optional[str] = Field(default=None)


class MissedNotificationReportCreate(BaseModel):
    lat: float
    lon: float
    note: Optional[str] = None


class EmulationSettings(SQLModel, table=True):
    id: Optional[int] = Field(default=1, primary_key=True)
    enabled: bool = Field(default=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class StoreDistanceCheck(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    checked_at: datetime
    lat: float
    lon: float
    store_id: int
    store_name: str
    distance_m: int


class ExpiryItem(SQLModel, table=True):
    """
    En vare derhjemme med en holdbarhedsdato (IKKE en vare der skal købes -
    det er selve Item-tabellen). Bruges til at holde styr på hvad der er
    gået over dato, og lægger automatisk varen tilbage på selve indkøbslisten
    når datoen overskrides (styret af added_to_shopping_list, så det kun
    sker én gang pr. vare).
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    expiry_date: date
    added_at: datetime = Field(default_factory=datetime.utcnow)
    added_to_shopping_list: bool = Field(default=False)


class ExpiryItemCreate(BaseModel):
    """Input-schema til POST /expiry-items."""
    name: str
    expiry_date: date
