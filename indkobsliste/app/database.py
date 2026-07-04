"""
Database-opsætning. Bruger SQLite-fil, som gemmes lokalt.
Senere (HA add-on) peger denne sti ind i add-on'ets persistente /data mappe.
"""
import os
from sqlmodel import SQLModel, create_engine, Session

DB_PATH = os.environ.get("INDKOBSLISTE_DB", "indkobsliste.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# check_same_thread=False, fordi FastAPI kan tilgå fra forskellige threads
engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})


def init_db() -> None:
    """Opretter tabeller hvis de ikke findes."""
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
