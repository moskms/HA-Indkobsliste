"""
Sidst opdateret: 2026-08-18 | Version: 2.0.23

Indscan bon: sender et billede af en kassebon til Claude (vision) og får en
struktureret udtrækning tilbage (butik, dato, varelinjer, total) - i stedet
for at gemme billedet, som brugeren udtrykkeligt IKKE ønsker.

Bevidst en separat, ren funktion (samme mønster som overpass.py/nominatim.py):
selve netværkskaldet (extract_receipt) er det eneste der kræver internet og
en gyldig API-nøgle; parse_tool_result() kan i princippet testes uden.

Billedet holdes ALDRIG på disk her eller i main.py's kaldende endpoint - det
læses direkte fra det uploadede request-body ind i hukommelsen, sendes videre
til Claude, og kasseres når funktionen returnerer.
"""
from __future__ import annotations

import base64
import json
import logging
from typing import Optional

from anthropic import Anthropic, APIConnectionError, APIStatusError, APITimeoutError

logger = logging.getLogger("indkobsliste.receipt_scan")

MODEL = "claude-haiku-4-5-20251001"

# Tvinger et struktureret svar via tool-use, i stedet for at bede Claude
# "svare i JSON" i almindelig tekst og selv skulle parse/gætte på formatet
# bagefter - markant mere robust.
_EXTRACT_TOOL = {
    "name": "extract_receipt",
    "description": (
        "Registrerer det strukturerede indhold af en dansk kassebon/kvittering "
        "ud fra billedet."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "store_name": {
                "type": "string",
                "description": "Butikkens navn som det står på bonnen, fx 'Netto' eller 'Rema 1000'.",
            },
            "purchase_date": {
                "type": "string",
                "description": (
                    "Købsdato i format ÅÅÅÅ-MM-DD, hvis den kan læses på bonnen. "
                    "Udelad feltet helt hvis datoen ikke er synlig/læselig."
                ),
            },
            "items": {
                "type": "array",
                "description": (
                    "Hver enkelt varelinje på bonnen. Udelad rabatlinjer, pant "
                    "der trækkes fra, og opsummeringslinjer (moms, total) - de "
                    "skal ikke med som en 'vare'."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Varens navn, som det står på bonnen."},
                        "price": {
                            "type": "number",
                            "description": "Prisen for denne linje i DKK, som den faktisk står (efter evt. tilbud).",
                        },
                        "quantity": {
                            "type": "number",
                            "description": "Antal/mængde hvis angivet på bonnen, ellers 1.",
                        },
                    },
                    "required": ["name", "price"],
                },
            },
            "total": {
                "type": "number",
                "description": "Det samlede totalbeløb på bonnen i DKK, hvis det er synligt.",
            },
        },
        "required": ["store_name", "items"],
    },
}

_SYSTEM_PROMPT = (
    "Du udtrækker struktureret data fra billeder af danske kassebon/kvitteringer "
    "til en indkøbsapp. Vær præcis - gæt ikke på tal du ikke tydeligt kan læse. "
    "Hvis et felt ikke kan læses pålideligt, udelad det i stedet for at gætte."
)


class ReceiptScanError(Exception):
    """Rejst når bon-scanningen fejler af en hvilken som helst årsag (ingen
    forbindelse, ugyldig/manglende API-nøgle, Claude svarede uventet). Klar,
    dansk fejlbesked - main.py sender den videre til frontend uden at gætte
    på hvad der gik galt."""


def _parse_tool_result(response) -> dict:
    """Finder extract_receipt-tool-kaldet i Claudes svar og returnerer dets
    input som en almindelig dict. Rejser ReceiptScanError hvis Claude af en
    eller anden grund ikke brugte værktøjet (bør ikke ske med tool_choice
    tvunget, men vi stoler ikke blindt på det)."""
    for block in response.content:
        if block.type == "tool_use" and block.name == "extract_receipt":
            return block.input
    raise ReceiptScanError("Claude returnerede ikke et struktureret resultat - prøv igen.")


def extract_receipt(image_bytes: bytes, media_type: str, api_key: str) -> dict:
    """Sender bon-billedet til Claude og returnerer:
    {"store_name": str, "purchase_date": str|None, "items": [...], "total": float|None,
     "raw_model_output": str}

    Kræver internetadgang og en gyldig Anthropic API-nøgle (sat som add-on-
    option ANTHROPIC_API_KEY - se config.yaml). Rejser ReceiptScanError med en
    brugervenlig, dansk besked ved enhver fejl (ingen forbindelse, ugyldig
    nøgle, timeout, uventet svar) - main.py oversætter denne direkte til det
    svar frontend viser, så brugeren kan vælge "prøv igen" eller "indtast
    manuelt" (se README/PROJEKT_SUMMERING for den etablerede fallback-stil).
    """
    if not api_key:
        raise ReceiptScanError(
            "Ingen Anthropic API-nøgle er sat op. Tilføj ANTHROPIC_API_KEY under "
            "add-on'ets Konfiguration-fane i Home Assistant, og genstart add-on'et."
        )

    client = Anthropic(api_key=api_key)
    image_b64 = base64.b64encode(image_bytes).decode("ascii")

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=_SYSTEM_PROMPT,
            tools=[_EXTRACT_TOOL],
            tool_choice={"type": "tool", "name": "extract_receipt"},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": "Udtræk butik, dato, varelinjer og total fra denne bon.",
                        },
                    ],
                }
            ],
        )
    except APITimeoutError as exc:
        logger.warning("Claude-kald timeout: %s", exc)
        raise ReceiptScanError("Claude svarede ikke i tide (timeout) - prøv igen.") from exc
    except APIConnectionError as exc:
        logger.warning("Claude-kald: ingen forbindelse: %s", exc)
        raise ReceiptScanError("Kunne ikke oprette forbindelse til Claude - tjek internetforbindelsen.") from exc
    except APIStatusError as exc:
        logger.warning("Claude-kald fejlede med status %s: %s", exc.status_code, exc)
        if exc.status_code == 401:
            raise ReceiptScanError(
                "Anthropic API-nøglen blev afvist (ugyldig). Tjek ANTHROPIC_API_KEY "
                "under add-on'ets Konfiguration-fane."
            ) from exc
        if exc.status_code == 429:
            raise ReceiptScanError("For mange kald til Claude lige nu (rate limit) - vent lidt og prøv igen.") from exc
        raise ReceiptScanError(f"Claude svarede med en fejl ({exc.status_code}) - prøv igen.") from exc
    except Exception as exc:  # uventet transport-/protokolfejl
        logger.warning("Claude-kald: uventet fejl: %s", exc)
        raise ReceiptScanError(f"Uventet fejl ved bon-scanning: {exc}") from exc

    result = _parse_tool_result(response)

    return {
        "store_name": result.get("store_name", "").strip() or "Ukendt butik",
        "purchase_date": result.get("purchase_date") or None,
        "items": [
            {
                "name": str(item.get("name", "")).strip(),
                "price": float(item.get("price", 0)),
                "quantity": float(item.get("quantity", 1) or 1),
            }
            for item in result.get("items", [])
            if str(item.get("name", "")).strip()
        ],
        "total": result.get("total"),
        "raw_model_output": json.dumps(result, ensure_ascii=False),
    }
