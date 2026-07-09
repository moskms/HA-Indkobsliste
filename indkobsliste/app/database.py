"""
Sidst opdateret: 2026-07-09

Database-opsætning. Bruger SQLite-fil, som gemmes lokalt.
Senere (HA add-on) peger denne sti ind i add-on'ets persistente /data mappe.
"""
import os
import logging
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import text, inspect

logger = logging.getLogger("indkobsliste.database")

DB_PATH = os.environ.get("INDKOBSLISTE_DB", "indkobsliste.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# check_same_thread=False, fordi FastAPI kan tilgå fra forskellige threads
engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})


def init_db() -> None:
    """Opretter tabeller hvis de ikke findes, og tilføjer automatisk manglende
    kolonner til EKSISTERENDE tabeller. SQLite's create_all() opretter kun helt
    nye tabeller - den opdaterer aldrig en tabel der allerede findes, selvom
    modellen i koden har fået nye felter. Uden denne migration ville enhver
    fremtidig ny kolonne kræve en manuel SQL-rettelse eller datatab."""
    SQLModel.metadata.create_all(engine)
    _add_missing_columns()


def _add_missing_columns() -> None:
    """Sammenligner hver models forventede kolonner med hvad der reelt findes
    i databasen, og tilføjer eventuelle manglende kolonner via ALTER TABLE."""
    inspector = inspect(engine)

    # SQLAlchemy-typenavn -> SQLite-kolonnetype til ALTER TABLE
    TYPE_MAP = {
        "VARCHAR": "VARCHAR",
        "TEXT": "TEXT",
        "INTEGER": "INTEGER",
        "FLOAT": "FLOAT",
        "BOOLEAN": "BOOLEAN",
        "DATETIME": "DATETIME",
    }

    with engine.connect() as conn:
        for table_name, table in SQLModel.metadata.tables.items():
            if not inspector.has_table(table_name):
                continue  # helt ny tabel - create_all() har allerede oprettet den korrekt

            existing_columns = {col["name"] for col in inspector.get_columns(table_name)}
            for column in table.columns:
                if column.name in existing_columns:
                    continue
                sql_type = TYPE_MAP.get(str(column.type), "TEXT")
                logger.warning(
                    "Tilføjer manglende kolonne '%s.%s' (%s) til eksisterende database",
                    table_name, column.name, sql_type,
                )
                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column.name} {sql_type}"))
        conn.commit()


def get_session():
    with Session(engine) as session:
        yield session
