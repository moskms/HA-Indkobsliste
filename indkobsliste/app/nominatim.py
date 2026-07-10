"""
Sidst opdateret: 2026-07-09 | Version: 2.0.5

Nominatim-fallback til butiksopslag, brugt når Overpass fejler/er utilgængelig.

Nominatim er en anden gratis OSM-baseret webtjeneste (adressesøgning),
med to vigtige begrænsninger vi skal respektere (deres brugspolitik):
- Maks. 1 forespørgsel i sekundet
- Skal identificere sig med en rigtig User-Agent

Da Nominatim ikke kan "find alle butikker af type X nær punkt Y" på samme
måde som Overpass, søger vi i stedet efter en liste af kendte danske
dagligvarekæder, begrænset til et område (viewbox) omkring koordinaten,
og filtrerer/sorterer selv på faktisk afstand bagefter.
"""
import time
import math
import logging
from typing import Optional

import requests

logger = logging.getLogger("indkobsliste.nominatim")

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

HEADERS = {
    # Nominatims brugspolitik kræver en rigtig, identificerbar User-Agent.
    "User-Agent": "Indkobsliste/1.0 (personligt hobbyprojekt)",
}

# Kendte danske dagligvarekæder - udvid gerne listen efter behov
DANISH_CHAINS = [
    "Netto", "Føtex", "Rema 1000", "Irma", "SuperBrugsen",
    "Dagli'Brugsen", "Kvickly", "Fakta", "Lidl", "Aldi",
    "Spar", "Min Købmand", "Meny",
]


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Beregner afstanden i meter mellem to GPS-koordinater."""
    R = 6371000  # jordens radius i meter
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def build_viewbox(lat: float, lon: float, radius_m: int) -> str:
    """Bygger en Nominatim-viewbox (left,top,right,bottom) omkring koordinaten.
    Bruger en simpel gradomregning (tilstrækkeligt præcis for vores formål)."""
    # ca. 111320 meter pr. breddegrad
    delta_lat = radius_m / 111320
    delta_lon = radius_m / (111320 * math.cos(math.radians(lat)) or 1)
    left = lon - delta_lon
    right = lon + delta_lon
    top = lat + delta_lat
    bottom = lat - delta_lat
    return f"{left},{top},{right},{bottom}"


def parse_nominatim_results(raw_results: list[dict]) -> list[dict]:
    """Omsætter Nominatims rå svar til vores fælles forslagsformat.
    'address' udtrækkes som andet led i display_name (typisk gadenavn),
    til at skelne mellem flere butikker med samme kædenavn."""
    suggestions = []
    for r in raw_results:
        try:
            lat = float(r["lat"])
            lon = float(r["lon"])
        except (KeyError, ValueError, TypeError):
            continue
        parts = r.get("display_name", "").split(",")
        name = parts[0].strip()
        address = parts[1].strip() if len(parts) > 1 else None
        suggestions.append({
            "name": name,
            "shop_type": r.get("type"),
            "address": address,
            "latitude": lat,
            "longitude": lon,
            "osm_id": f"{r.get('osm_type')}/{r.get('osm_id')}",
        })
    return suggestions


def find_nearby_shops_nominatim(lat: float, lon: float, radius_m: int = 100) -> list[dict]:
    """Søger efter kendte danske kædenavne nær koordinaten via Nominatim,
    filtrerer til dem der reelt er inden for radius_m, og sorterer efter afstand.
    Respekterer Nominatims krav om maks. 1 kald/sekund.
    """
    viewbox = build_viewbox(lat, lon, radius_m)
    all_results = []
    seen_osm_ids = set()
    errors = []
    consecutive_failures = 0

    for chain in DANISH_CHAINS:
        logger.info("Nominatim: søger efter '%s' ...", chain)
        params = {
            "q": chain,
            "format": "json",
            "viewbox": viewbox,
            "bounded": 1,
            "limit": 5,
        }
        try:
            response = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=6)
            response.raise_for_status()
            consecutive_failures = 0
        except Exception as exc:
            logger.warning("Nominatim: '%s' fejlede: %s", chain, exc)
            errors.append(f"{chain}: {exc}")
            consecutive_failures += 1
            if consecutive_failures >= 3:
                # Tre fejl i træk tyder på at tjenesten er nede generelt,
                # ikke at der bare ikke findes en butik af den type. Stop
                # tidligt i stedet for at spilde tid på resten af kæderne.
                raise RuntimeError(
                    f"Nominatim ser ud til at være utilgængelig ({consecutive_failures} "
                    f"fejl i træk): " + " | ".join(errors)
                )
            time.sleep(1)
            continue

        for suggestion in parse_nominatim_results(response.json()):
            if suggestion["osm_id"] in seen_osm_ids:
                continue
            distance = haversine_m(lat, lon, suggestion["latitude"], suggestion["longitude"])
            if distance <= radius_m:
                suggestion["distance_m"] = round(distance)
                all_results.append(suggestion)
                seen_osm_ids.add(suggestion["osm_id"])

        time.sleep(1)  # overhold Nominatims 1 kald/sekund-grænse

    all_results.sort(key=lambda s: s["distance_m"])
    return all_results
