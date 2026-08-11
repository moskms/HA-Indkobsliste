# Sidst opdateret: 2026-08-11 | Version: 2.0.20
"""
Fortolker talte danske datoer til rigtige datoer, fx:
- "niende i syvende seksogtyve" -> 2026-07-09
- "ni i syv seksogtyve" -> 2026-07-09 (grundtal i stedet for ordenstal)
- "9 juli 2026" -> 2026-07-09
- "09/07/26" -> 2026-07-09

Bygget til at understøtte flere måder at sige/skrive en dato på, da
talegenkendelse ikke altid giver samme format to gange. Dag og måned kan
siges enten som ordenstal ("tolvte") eller grundtal ("tolv") - Morten siger
i praksis ofte grundtal, så begge accepteres overalt.
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

# Grundtal 1-99 samlet i én opslagstabel, så både dag/måned og år kan
# fortolkes fra grundtal ("tolv") og ikke kun ordenstal ("tolvte").
CARDINALS: dict = {}
CARDINALS.update({word: value for word, value in UNITS.items() if value > 0})  # 1-9
CARDINALS.update(TEENS)  # 10-19
CARDINALS.update(TENS)  # 20, 30, 40 ... 90 (rene tiere)
for _tens_word, _tens_val in TENS.items():
    for _unit_word, _unit_val in UNITS.items():
        if _unit_val == 0:
            continue
        CARDINALS[f"{_unit_word}og{_tens_word}"] = _tens_val + _unit_val  # fx "enogtyve" -> 21

STOPWORDS = {"i", "den", "det", "d.", "på"}


def _parse_cardinal(tokens: list[str], start: int) -> tuple[Optional[int], int]:
    """Prøver at læse et grundtal fra tokens[start:], fx ['seksogtyve'] -> 26,
    eller ['seks', 'og', 'tyve'] -> 26 (hvis talegenkendelsen har splittet
    det sammensatte ord op). Returnerer (tal, antal_tokens_brugt) eller (None, 0)."""
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

    if tok in CARDINALS:
        return CARDINALS[tok], 1

    return None, 0


def _parse_number(tokens: list[str], start: int) -> tuple[Optional[int], int]:
    """Læser et tal fra tokens[start:] til brug for dag/måned - accepterer
    både ordenstal ("tolvte") og grundtal ("tolv"), da Morten i praksis
    bruger begge i flæng. Prøver ordenstal først (mest utvetydigt), derefter
    grundtal (inkl. splittet form som "en og tyve").
    Returnerer (tal, antal_tokens_brugt) eller (None, 0)."""
    if start >= len(tokens):
        return None, 0
    if tokens[start] in ORDINALS:
        return ORDINALS[tokens[start]], 1
    return _parse_cardinal(tokens, start)


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

    # --- Dag --- (ordenstal "niende"/"tolvte" eller grundtal "ni"/"tolv")
    idx = 0
    day, consumed = _parse_number(tokens, idx)
    if day is None:
        return None
    idx += consumed

    if idx >= len(tokens):
        return None

    # --- Måned ---
    month = None
    if tokens[idx] in MONTH_NAMES:
        month = MONTH_NAMES[tokens[idx]]
        idx += 1
    else:
        month_val, consumed = _parse_number(tokens, idx)
        if month_val is not None and 1 <= month_val <= 12:
            month = month_val
            idx += consumed
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
