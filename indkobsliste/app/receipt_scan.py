"""
Sidst opdateret: 2026-09-03 | Version: 2.0.43

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
                    "Hver enkelt varelinje på bonnen der HAR sit eget trykte "
                    "beløb ud for sig. Udelad selve pant-linjer og ALLE "
                    "opsummerings-/betalingslinjer nederst på bonnen - disse "
                    "er ALDRIG varer, uanset hvilket beløb der står ud for "
                    "dem: linjer der starter med eller indeholder 'MOMS', "
                    "'HERAF', 'IALT', 'TOTAL', 'AT BETALE', 'BETALINGSKORT', "
                    "'KONTANT', 'BYTTEPENGE' eller lignende. Eksempel på en "
                    "fejl der er set i praksis: en linje 'HERAF 25% MOMS "
                    "IALT   27,98' blev fejlagtigt oprettet som sin egen vare "
                    "med price=27.98 - det er en momsopgørelse, IKKE en vare, "
                    "og skal aldrig med i 'items'. Rabatlinjer ('RABAT', "
                    "'TILBUD' e.l. med et beløb og typisk et efterfølgende "
                    "'-') skal IKKE med som deres egen varelinje, men "
                    "transskriberes ind i 'discount' på varen de hører til - "
                    "se feltets beskrivelse, inkl. reglen om FLERE "
                    "RABAT-linjer efter samme vare. Hvis en tekstlinje IKKE "
                    "har noget selvstændigt beløb trykt ud for sig (fx en "
                    "fortsættelse af et langt varenavn på næste linje, en "
                    "butiks-/kampagnetekst, eller en linje du er i tvivl om "
                    "hører til), skal den IKKE oprettes som sin egen vare, og "
                    "dens 'navn' må ALDRIG kombineres med et beløb der reelt "
                    "hører til en anden linje - lån aldrig et beløb fra en "
                    "nabolinje. Er en varelinjes navn skrevet på to linjer på "
                    "bonnen (kun ét beløb for hele varen), er det ÉN vare, "
                    "ikke to - opret ALDRIG flere kopier af samme vare. REGN "
                    "ALDRIG selv videre på tallene (ingen addition, "
                    "subtraktion, multiplikation eller division) - hvert tal "
                    "(price, quantity, discount) skal læses enkeltvis, "
                    "uafhængigt af de andre tal på linjen, direkte fra det "
                    "der faktisk står trykt - UNDTAGEN reglen om at LÆGGE "
                    "FLERE RABAT-beløb sammen for samme vare, se 'discount'."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Varens navn, som det står på bonnen."},
                        "price": {
                            "type": "number",
                            "description": (
                                "Det SELVSTÆNDIGE totalbeløb PRÆCIS SOM DET "
                                "STÅR TRYKT ud for varelinjen (før evt. "
                                "rabat) - læs dette tal direkte, transskriber "
                                "det ikke ud fra en udregning. Hvis bonnen "
                                "ALSO viser en linje som '2 x 49,00' for "
                                "samme vare, skal du IKKE gange 2 med 49,00 "
                                "for at få price, og heller ikke dividere "
                                "price med antal for at gætte stykprisen - "
                                "begge tal (stykpris og totalpris) skal "
                                "aflæses hver for sig, direkte fra det der er "
                                "trykt. Eksempel: linjen viser '2 x 49,00' og "
                                "totalen '98,00' -> price = 98.00 (det trykte "
                                "totalbeløb, ikke 2×49 udregnet af dig - hvis "
                                "de to tal ikke stemmer overens fordi et af "
                                "dem er svært at læse, så brug det totalbeløb "
                                "der faktisk står trykt ud for varelinjen, "
                                "ikke et udregnet tal)."
                            ),
                        },
                        "quantity": {
                            "type": "number",
                            "description": (
                                "Antal/mængde PRÆCIS SOM DET STÅR TRYKT (fx "
                                "'2' fra '2 x 49,00'), ellers 1. Kun til "
                                "visning - brug det ALDRIG til selv at "
                                "udregne 'price'."
                            ),
                        },
                        "discount": {
                            "type": "number",
                            "description": (
                                "Beløbet PRÆCIS SOM DET STÅR TRYKT på en "
                                "'RABAT'/'TILBUD'-linje lige under varen "
                                "(positivt tal, uden minus - fx 6.95 hvis der "
                                "står 'RABAT 6,95-'). Transskriber tallet, "
                                "regn ikke noget ud fra det. Udelad feltet "
                                "helt hvis varen ikke har nogen rabatlinje. "
                                "VIGTIG UNDTAGELSE, set i praksis på en rigtig "
                                "bon: hvis der står FLERE 'RABAT'-linjer lige "
                                "efter HINANDEN, umiddelbart under samme vare "
                                "(før næste varenavn begynder) - fx tre "
                                "linjer 'RABAT  6,95-' i træk under ÉN vare - "
                                "hører de ALLE til den samme, ene vare. LÆG "
                                "dem sammen til ÉT samlet discount-beløb for "
                                "den ene vare (fx 6,95+6,95+6,95 = 20.85), og "
                                "opret varen ÉN gang, ikke tre. Opret ALDRIG "
                                "flere kopier af varen (én pr. RABAT-linje) - "
                                "det er den samme vare med flere rabatter, "
                                "ikke flere varer."
                            ),
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
    "Hvis et felt ikke kan læses pålideligt, udelad det i stedet for at gætte. "
    "Mange danske bonner (fx Føtex) viser en 'RABAT'-linje direkte under en "
    "vare, med et beløb efterfulgt af '-' (fx 'RABAT 6,95-') - dette er IKKE "
    "en selvstændig varelinje, men hører til varen lige ovenover. VIGTIGT: "
    "du skal ALDRIG selv regne rabatten fra prisen eller lave anden "
    "udregning - transskriber udelukkende de tal der faktisk står trykt på "
    "bonnen, hver for sig ('price' = linjens egen trykte pris, 'discount' = "
    "rabatlinjens eget trykte beløb). Appen regner selv videre på tallene "
    "bagefter. "
    "TO FLERE VIGTIGE REGLER, bekræftet nødvendige af rigtige fejlscanninger: "
    "(1) Gang eller divider ALDRIG selv tal sammen for at udfylde et felt - "
    "hvis en vare viser både en stykpris-linje ('2 x 49,00') og en samlet "
    "pris ('98,00'), skal 'price' være det trykte totalbeløb aflæst direkte, "
    "IKKE 2×49 udregnet af dig, og 'quantity' må aldrig bruges til at "
    "udregne 'price'. Hvert tal på bonnen skal læses for sig selv, uafhængigt "
    "af de andre tal på samme linje. (2) Opret kun en vare hvis der faktisk "
    "står et selvstændigt beløb ud for linjen på bonnen - en tekstlinje uden "
    "sit eget beløb (fx fortsættelse af et langt varenavn, eller en "
    "informationstekst) må ALDRIG få tildelt et beløb der reelt hører til en "
    "anden vare, og skal i stedet enten udelades eller lægges sammen med "
    "varenavnet ovenover som ÉN vare. "
    "TO YDERLIGERE REGLER, bekræftet nødvendige af en rigtig fejlscanning: "
    "(3) Nederst på bonnen står ofte betalings-/opsummeringslinjer som "
    "'HERAF 25% MOMS IALT', 'AT BETALE', 'BETALINGSKORT', 'KONTANT' eller "
    "'BYTTEPENGE' - disse har et beløb ud for sig ligesom en vare, men er "
    "IKKE varer og må ALDRIG med i 'items', uanset hvor oplagt det ser ud "
    "til at have et 'eget' beløb. (4) Nogle bonner viser flere "
    "'RABAT'-linjer i træk under ÉN vare (fx tre '6,95-'-linjer efter "
    "samme vare) - det er STADIG kun én vare, ikke tre. Læg de flere "
    "rabatbeløb sammen til ét samlet discount-tal for den ene vare, og "
    "opret IKKE en kopi af varen for hver RABAT-linje."
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


def extract_receipt(images: list[tuple[bytes, str]], api_key: str) -> dict:
    """Sender ét eller flere bon-billeder til Claude og returnerer:
    {"store_name": str, "purchase_date": str|None, "items": [...], "total": float|None,
     "raw_model_output": str}

    `images` er en liste af (image_bytes, media_type) - normalt kun ét billede,
    men ved lange bonner kan brugeren tage flere billeder (fx top og bund) af
    SAMME bon via "+"-knappen i frontend; alle billeder sendes da samlet i én
    besked, så Claude kan sammenstille varelinjerne fra dem til ÉN bon i
    stedet for at behandle dem som separate bonner.

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
    if not images:
        raise ReceiptScanError("Intet billede modtaget - prøv igen.")

    client = Anthropic(api_key=api_key)

    image_blocks = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": base64.b64encode(image_bytes).decode("ascii"),
            },
        }
        for image_bytes, media_type in images
    ]
    if len(images) > 1:
        instruction_text = (
            f"Disse {len(images)} billeder viser SAMME kassebon, fotograferet i "
            "flere dele (fx top og bund af en lang bon) - ikke flere separate "
            "bonner. Udtræk butik, dato, varelinjer og total som var det ét "
            "sammenhængende billede. Optræder en varelinje kun én gang i alt "
            "på tværs af billederne (fx fordi to billeder overlapper lidt), "
            "skal den også kun med én gang i resultatet - ikke duplikeret."
        )
    else:
        instruction_text = "Udtræk butik, dato, varelinjer og total fra denne bon."

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=_SYSTEM_PROMPT,
            tools=[_EXTRACT_TOOL],
            tool_choice={"type": "tool", "name": "extract_receipt"},
            messages=[
                {
                    "role": "user",
                    "content": [
                        *image_blocks,
                        {
                            "type": "text",
                            "text": instruction_text,
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
                "discount": (
                    float(item["discount"])
                    if item.get("discount") is not None
                    else None
                ),
            }
            for item in result.get("items", [])
            if str(item.get("name", "")).strip()
        ],
        "total": result.get("total"),
        "raw_model_output": json.dumps(result, ensure_ascii=False),
    }
