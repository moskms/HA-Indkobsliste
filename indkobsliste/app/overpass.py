"""
Overpass-opslag: finder butikker (dagligvarer m.m.) tæt på en given
GPS-koordinat, til brug for "ny butik her"-knappen i frontend.

Bevidst delt i tre funktioner:
- build_query(): bygger Overpass QL-forespørgslen (ren, testbar)
- parse_response(): omsætter Overpass' rå JSON til vores eget format (ren, testbar)
- find_nearby_shops(): selve netværkskaldet (kræver internetadgang)

De to første kan testes uden internet. Den sidste skal testes i praksis
på en maskine med adgang til overpass-api.de.
"""
from typing import Optional

import logging
import requests

logger = logging.getLogger("indkobsliste.overpass")

# Flere spejlservere, forsøges i rækkefølge - hvis den første er langsom/nede,
# prøver vi den næste i stedet for at fejle helt.
OVERPASS_URLS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]

# Butikstyper vi er interesserede i - kan udvides senere
RELEVANT_SHOP_TYPES = [
    "supermarket",
    "convenience",
    "department_store",
    "general",
    "bakery",
    "butcher",
]


def build_query(lat: float, lon: float, radius_m: int = 100) -> str:
    """Bygger en Overpass QL-forespørgsel der finder shop=X noder/ways
    inden for radius_m meter af (lat, lon)."""
    shop_filter = "|".join(RELEVANT_SHOP_TYPES)
    return f"""
    [out:json][timeout:10];
    (
      node["shop"~"^({shop_filter})$"](around:{radius_m},{lat},{lon});
      way["shop"~"^({shop_filter})$"](around:{radius_m},{lat},{lon});
    );
    out center tags;
    """


def parse_response(data: dict) -> list[dict]:
    """Omsætter Overpass' rå svar til en liste af forslag:
    [{"name": ..., "shop_type": ..., "latitude": ..., "longitude": ..., "osm_id": ...}, ...]

    Springer elementer uden navn over, da de er ubrugelige som forslag i UI'en.
    """
    suggestions = []
    for element in data.get("elements", []):
        tags = element.get("tags", {})
        name = tags.get("name")
        if not name:
            continue

        # Noder har lat/lon direkte, ways har det i "center"
        if element["type"] == "node":
            lat = element.get("lat")
            lon = element.get("lon")
        else:
            center = element.get("center", {})
            lat = center.get("lat")
            lon = center.get("lon")

        if lat is None or lon is None:
            continue

        suggestions.append({
            "name": name,
            "shop_type": tags.get("shop"),
            "latitude": lat,
            "longitude": lon,
            "osm_id": f"{element['type']}/{element['id']}",
        })

    return suggestions


def find_nearby_shops(lat: float, lon: float, radius_m: int = 100) -> list[dict]:
    """Slår op i Overpass API og returnerer forslag til butikker nær koordinaten.
    Kræver internetadgang. Prøver flere spejlservere i rækkefølge, da den
    offentlige infrastruktur kan være ustabil/langsom.
    """
    query = build_query(lat, lon, radius_m)
    headers = {
        # Overpass' brugspolitik kræver en identificerbar User-Agent,
        # ellers afviser den nogle gange forespørgsler med 406.
        "User-Agent": "Indkobsliste/1.0 (personligt hobbyprojekt)",
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate",
    }

    errors = []
    for url in OVERPASS_URLS:
        logger.info("Overpass: prøver %s ...", url)
        try:
            response = requests.post(url, data={"data": query}, headers=headers, timeout=8)
            response.raise_for_status()
            logger.info("Overpass: %s svarede OK", url)
            return parse_response(response.json())
        except Exception as exc:
            logger.warning("Overpass: %s fejlede: %s", url, exc)
            errors.append(f"{url}: {exc}")
            continue

    raise RuntimeError("Alle Overpass-servere fejlede: " + " | ".join(errors))
