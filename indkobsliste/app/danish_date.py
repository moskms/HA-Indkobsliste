# Sidst opdateret: 2026-07-10 | Version: 2.0.12
"""
Fortolker talte danske datoer til rigtige datoer, fx:
- "niende i syvende seksogtyve" -> 2026-07-09
- "9 juli 2026" -> 2026-07-09
- "09/07/26" -> 2026-07-09

Bygget til at understøtte flere måder at sige/skrive en dato på, da
talegenkendelse ikke altid giver samme format to gange.
"""
import re
from datetime import date
from typing import Optional

# Ordenstal 1.-31. (bruges til både dag og evt. måned udtrykt som ordenstal)
ORDINALS = {
    "første": 1, "anden": 2, "tredje": 3, "fjerde": 4, "femte": 5,
    "sjette": 6, "syvende": 7, "ottende": 8, "niende": 9, "tiende": 10,
    "ellevte": 11, "tolvte": 12, "trettende": 13, "fjortende": 14, "femtende": 15,
    "sekstende": 16, "syttende": 17, "attende": 18, "nittende": 19, "tyvende": 20,
    "enogtyvende": 21, "toogtyvende": 22, "treogtyvende": 23, "fireogtyvende": 24,
    "femogtyvende": 25, "seksogtyvende": 26, "syvogtyvende": 27, "otteogtyvende": 28,
    "niogtyvende": 29, "tredivte": 30, "enogtredivte": 31,
}

MONTH_NAMES = {
    "januar": 1, "februar": 2, "marts": 3, "april": 4, "maj": 5, "juni": 6,
    "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11, "december": 12,
}

# Grundtal til årstal, fx "seksogtyve" -> 26
UNITS = {
    "nul": 0, "en": 1, "et": 1, "to": 2, "tre": 3, "fire": 4, "fem": 5,
    "seks": 6, "syv": 7, "otte": 8, "ni": 9,
}
TEENS = {
    "ti": 10, "elleve": 11, "tolv": 12, "tretten": 13, "fjorten": 14,
    "femten": 15, "seksten": 16, "sytten": 17, "atten": 18, "nitten": 19,
}
TENS = {
    "tyve": 20, "tredive": 30, "fyrre": 40, "halvtreds": 50,
    "tres": 60, "halvfjerds": 70, "firs": 80, "halvfems": 90,
}

STOPWORDS = {"i", "den", "det", "d.", "på"}


def _parse_cardinal(tokens: list[str], start: int) -> tuple[Optional[int], int]:
    """Prøver at læse et grundtal (til årstal) fra tokens[start:], fx
    ['seksogtyve'] -> 26, eller ['seks', 'og', 'tyve'] -> 26 (hvis
    talegenkendelsen har splittet det sammensatte ord op).
    Returnerer (tal, antal_tokens_brugt) eller (None, 0)."""
    if start >= len(tokens):
        return None, 0
    tok = tokens[start]

    # Rene cifre, fx "26" eller "2026"
    if tok.isdigit():
        return int(tok), 1

    # Splittet op af talegenkendelsen, fx "seks", "og", "tyve" - tjekkes FØRST,
    # ellers ville "seks" alene blive fortolket som 6 i stedet for 26.
    if (
        start + 2 < len(tokens)
        and tokens[start] in UNITS
        and tokens[start + 1] == "og"
        and tokens[start + 2] in TENS
    ):
        return UNITS[tokens[start]] + TENS[tokens[start + 2]], 3

    # Sammensat ord i ét, fx "seksogtyve"
    if tok in TENS:
        return TENS[tok], 1
    if tok in TEENS:
        return TEENS[tok], 1
    if tok in UNITS:
        return UNITS[tok], 1
    for tens_word, tens_val in TENS.items():
        for unit_word, unit_val in UNITS.items():
            combined = f"{unit_word}og{tens_word}"
            if tok == combined:
                return tens_val + unit_val, 1

    return None, 0


def _resolve_year(value: int) -> int:
    """Omsætter et 2-cifret år til 20XX (fx 26 -> 2026)."""
    if value < 100:
        return 2000 + value
    return value


def parse_danish_date(text: str) -> Optional[date]:
    """
    Fortolker en talt/skrevet dansk dato-sætning til en date, eller None
    hvis den ikke kan genkendes. Understøtter:
    - Ordenstal + ordenstal/månedsnavn + årstal: "niende i syvende seksogtyve"
    - Ciffer + månedsnavn + årstal: "9 juli 2026"
    - Rent numerisk med skilletegn: "09/07/26", "9-7-2026", "09.07.2026"
    """
    if not text or not text.strip():
        return None

    text = text.strip().lower()

    # 1. Forsøg ren numerisk form først (mest utvetydig, hvis genkendt sådan)
    match = re.search(r"(\d{1,2})[./\-](\d{1,2})[./\-](\d{2,4})", text)
    if match:
        day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
        year = _resolve_year(year)
        try:
            return date(year, month, day)
        except ValueError:
            return None

    # 2. Tokeniser og fjern fyldord
    raw_tokens = re.findall(r"[a-zæøå0-9]+", text)
    tokens = [t for t in raw_tokens if t not in STOPWORDS]
    if not tokens:
        return None

    # --- Dag ---
    day = None
    idx = 0
    if tokens[idx].isdigit():
        day = int(tokens[idx])
        idx += 1
    elif tokens[idx] in ORDINALS:
        day = ORDINALS[tokens[idx]]
        idx += 1
    else:
        return None

    if idx >= len(tokens):
        return None

    # --- Måned ---
    month = None
    if tokens[idx].isdigit():
        month = int(tokens[idx])
        idx += 1
    elif tokens[idx] in MONTH_NAMES:
        month = MONTH_NAMES[tokens[idx]]
        idx += 1
    elif tokens[idx] in ORDINALS and ORDINALS[tokens[idx]] <= 12:
        month = ORDINALS[tokens[idx]]
        idx += 1
    else:
        return None

    if idx >= len(tokens):
        return None

    # --- År ---
    year, consumed = _parse_cardinal(tokens, idx)
    if year is None:
        return None
    year = _resolve_year(year)

    try:
        return date(year, month, day)
    except ValueError:
        return None
