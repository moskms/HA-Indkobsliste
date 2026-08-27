# Sidst opdateret: 2026-08-27 | Version: 2.0.30
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


class VoiceCorrection(SQLModel, table=True):
    """
    Rettelsesliste for ord talegenkendelsen typisk hører forkert (fx
    "roastbeef" -> "roskilde"). wrong_text gemmes altid små bogstaver, så
    opslag ved brug kan være case-insensitivt uden ekstra logik.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    wrong_text: str
    correct_text: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class VoiceCorrectionCreate(BaseModel):
    wrong_text: str
    correct_text: str


class ExpiryNotificationSettings(SQLModel, table=True):
    """
    Én fast række (id=1) med indstillinger for den daglige "snart over
    dato"-notifikation. last_notified_date forhindrer flere notifikationer
    samme dag, uanset hvor ofte HA-automationen kalder tjek-endpointet.
    """
    id: Optional[int] = Field(default=1, primary_key=True)
    enabled: bool = Field(default=True)
    days_before: int = Field(default=2)
    notify_time: str = Field(default="09:00")  # "HH:MM"
    last_notified_date: Optional[date] = Field(default=None)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ExpiryNotificationSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    days_before: Optional[int] = None
    notify_time: Optional[str] = None


# ===== Indscan bon: bonner scannes med kameraet og udledes til struktureret
# tekst via Claude - selve billedet gemmes ALDRIG, hverken permanent eller
# midlertidigt (se app/receipt_scan.py og main.py's /receipts/scan). =====

class Receipt(SQLModel, table=True):
    """Én scannet/manuelt indtastet bon. `raw_model_output` gemmer Claudes
    ubearbejdede JSON-svar (til fejlsøgning hvis noget ser forkert ud efter
    godkendelse) - stadig ren tekst, aldrig billedet selv."""
    id: Optional[int] = Field(default=None, primary_key=True)
    store_name: str
    purchase_date: Optional[date] = Field(default=None)
    total: Optional[float] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    raw_model_output: Optional[str] = Field(default=None)


class ReceiptItem(SQLModel, table=True):
    """`name` er altid den rå tekst som Claude læste af bonen (eller blev
    tastet manuelt) - urørt, så vi altid kan se hvad der faktisk stod.
    `translated_name`, hvis sat, er brugerens egen oversættelse til
    menneskelæselig tekst (fx "3st ROASTBEEF" -> "3 stjernet Roastbeef") og
    bruges i stedet for `name`, når den findes - se ReceiptItemTranslation."""
    id: Optional[int] = Field(default=None, primary_key=True)
    receipt_id: int = Field(foreign_key="receipt.id")
    name: str
    translated_name: Optional[str] = Field(default=None)
    price: float
    quantity: float = Field(default=1)


class ReceiptItemInput(BaseModel):
    """Input-schema for én varelinje ved POST /receipts - bruges både til
    Claudes forslag (som brugeren kan rette i gennemsyns-skærmen) og til
    fuldt manuel indtastning. translated_name er valgfri - sættes hvis en
    kendt oversættelse blev fundet/bekræftet allerede ved scanning."""
    name: str
    translated_name: Optional[str] = None
    price: float
    quantity: float = 1


class ReceiptCreate(BaseModel):
    """Input-schema til POST /receipts - det ENDELIGE, godkendte (evt.
    rettede) resultat, uanset om det kom fra en Claude-scanning eller blev
    tastet manuelt. raw_model_output er kun sat, hvis det rent faktisk kom
    fra en scanning."""
    store_name: str
    purchase_date: Optional[date] = None
    total: Optional[float] = None
    items: list[ReceiptItemInput] = []
    raw_model_output: Optional[str] = None


class ReceiptItemTranslation(SQLModel, table=True):
    """Ordbog: rå bon-tekst -> menneskelæselig oversættelse, tastet af
    brugeren i bon-arkivet (kun synligt på desktop). Samme princip som
    VoiceCorrection, blot for scannet bon-tekst i stedet for tale.
    raw_text gemmes altid små bogstaver (case-insensitivt opslag), så
    "3st ROASTBEEF" og "3st roastbeef" matcher samme rettelse."""
    id: Optional[int] = Field(default=None, primary_key=True)
    raw_text: str = Field(unique=True)
    correct_text: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ReceiptItemTranslationUpdate(BaseModel):
    """Input-schema til at gemme/opdatere en oversættelse for én varelinje.
    raw_text sendes med, så vi ved hvilken rå tekst oversættelsen gælder for
    - selve varelinjen (identificeret ved item_id) får samtidig sat
    translated_name, så den gemte bon også viser den pæne tekst med det
    samme, ikke kun fremtidige scanninger."""
    correct_text: str
