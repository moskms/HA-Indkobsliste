# HA Indkøbsliste - Fuld projektstatus (v2.0.19)

*Til brug i en ny samtale - indsæt hele dette dokument som første besked,
sammen med hvad du gerne vil arbejde videre med.*

## Hvad projektet er

En dansk indkøbsliste-app til Morten, bygget som et Home Assistant-add-on.
Kernen: når Morten er fysisk tæt på en af sine faste butikker OG der står
noget på hans indkøbsliste, får han automatisk en push-notifikation.
Sidenhen udvidet med en "over dato"-funktion til varer derhjemme.

## Hvor koden er

- **Lokal klon:** `P:\HA-Indkobsliste\` (VS Code)
- **GitHub:** `https://github.com/moskms/HA-Indkobsliste` (public repo)
- **Struktur:**
  ```
  HA-Indkobsliste/
  ├── repository.yaml
  ├── README.md
  └── indkobsliste/
      ├── config.yaml       # version står her - VIGTIGST at holde synkroniseret
      ├── Dockerfile
      ├── run.sh
      ├── requirements.txt  # fastapi, uvicorn, sqlmodel, requests
      ├── CHANGELOG.md
      ├── app/
      │   ├── main.py         # FastAPI - alle endpoints
      │   ├── models.py       # SQLModel-tabeller
      │   ├── database.py     # DB-opsætning + automatisk kolonne-migration
      │   ├── overpass.py     # Automatisk butiksopslag (primær kilde)
      │   ├── nominatim.py    # Automatisk butiksopslag (fallback)
      │   └── danish_date.py  # Dansk talt-dato-fortolker (NYT i v2.0.19)
      └── frontend/
          └── index.html      # Hele frontend, ét fil, hamburgermenu
  ```

## Kør på

- HA OS mini-PC, IP `192.168.0.173`
- Ekstern adgang: `https://indkobsliste.skerra.dk` (Cloudflare Tunnel)
- **Nuværende version: 2.0.19** - BEKRÆFT altid selv i `config.yaml`, kan være hævet siden

## Arbejdsgang for enhver ændring (følg præcis denne rækkefølge)

1. Rediger kode lokalt
2. Hæv version ét enkelt trin i `config.yaml` (ALDRIG store spring, fx 2.0.31 - ødelægger
   Supervisors versionssammenligning, som er numerisk pr. segment)
3. Opdater SAMME versionstal to steder mere: `<div id="menu-version">v2.0.20</div>` i
   `index.html`, og filhoved-kommentaren øverst i hver ændret fil:
   `# Sidst opdateret: DATO | Version: 2.0.20`
4. Tilføj sektion øverst i `CHANGELOG.md`
5. `git add . && git commit -m "..." && git push`
6. HA: Settings → Apps → App Store → (⋮) → Check for updates → installer
7. Test bagefter - se testmetoder nedenfor

## Sådan tester du uden at gå ud af huset

- `https://indkobsliste.skerra.dk/diagnostics/proximity-log?limit=30` - rå log over
  ALLE HA-positionstjek (også "ikke i nærheden")
- `https://indkobsliste.skerra.dk/diagnostics/notification-log?limit=50` - kun de
  RENT FAKTISK udløste notifikationer, med telefon- og butiks-position, dækker
  langt længere tid tilbage end proximity-log
- `https://indkobsliste.skerra.dk/diagnostics/ha-position` - HA's device_tracker lige nu
- I appen, "🔧 Diagnostik"-fanen:
  - **Test-tilstand (emulering)-knap**: TIL = sender en RIGTIG besked fra den rigtige
    liste ved HVERT automations-kald, uanset faktisk afstand - bekræfter om telefonen
    modtager notifikationer, uden at gå ud. HUSK at slå fra igen efter test.
  - **"Tjek nu"-knap**: bruger ENHEDENS EGEN GPS (ikke HA's), viser om der ville
    sendes besked, og afstand til ALLE butikker (ikke kun nærmeste)
  - Header viser LIVE to positioner side om side: blå (browserens GPS) vs.
    gul (HA's device_tracker) - central til at diagnosticere sporingsproblemer
- I appen, "📋 Notifikationer"-fanen:
  - **"Jeg fik ikke en besked"-knap**: rapporterer øjeblikkeligt din nuværende position
    og nærmeste butik, til senere sammenligning med hvad HA's periodiske tjek så på
    samme tidspunkt
  - Log over tidligere rapporter, og log over faktisk sendte notifikationer

## Kritiske tekniske faldgruber - læs FØR du fejlsøger noget

1. **Versionstal sammenlignes numerisk pr. segment.** `1.0.31` > `1.0.4`. Enkeltvise trin altid.
2. **`arch:` i config.yaml må KUN indeholde `aarch64` og `amd64`** - udfasede
   (`i386`, `armhf`, `armv7`) får Supervisor til stille at afvise appen.
3. **Cloudflare erstatter automatisk ALLE 4xx/5xx-svar** med sin egen fejlside.
   Derfor svarer `/diagnostics/*`-endpoints ALTID 200, med `success`/`error` i JSON-body.
4. **`homeassistant_api: true`** kræver FULD app-genstart (Stop→Start), ikke kun opdatering.
5. **Usynlige tegn (BOM) i config.yaml** giver kryptiske YAML-fejl ("did not find
   expected key") ikke synlige i editoren. Genskab filen fra bunden hvis det sker.
6. **Lokal `addons/`-mappe og GitHub-repo er to adskilte identiteter for Supervisor.**
   Vi bruger UDELUKKENDE GitHub-sporet.
7. **App-data (SQLite-databasen) kan gå tabt ved geninstallation.** Backup-fane findes
   (`/backup`, `/restore`) - mind brugeren om at tage backup før risikable HA-ændringer.
8. **SQLite tilføjer ALDRIG nye kolonner til eksisterende tabeller automatisk.**
   `database.py` har `_add_missing_columns()`-migration der kører ved hver opstart -
   tilføjer nye modelfelter/tabeller automatisk uden datatab. Virker allerede for
   `ExpiryItem` m.fl.
9. **HA's `notify.mobile_app_XXX`-servicenavn matcher IKKE altid telefonens pæne navn.**
   Mortens Samsung S23 Ultra bruger `notify.mobile_app_sm_s918b` (internt modelnummer).
   Tjek ALTID det faktiske navn via Developer Tools → Actions → søg "notify".
10. **`ProximityState` "husker" en besked som sendt i det øjeblik should_notify=true** -
    uafhængigt af om HA's automation rent faktisk lykkes med at sende den. Hvis
    automationen fejler nedstrøms, tror systemet stadig det har advaret. LØST: der
    findes/fandtes en nulstillingsmekanisme - bekræft den stadig er der i main.py,
    hvis notifikationer "sidder fast".
11. **Butikker med samme kædenavn tæt på hinanden** kan forveksles - løst med adresse
    i navnet + omdøb-funktion.
12. **Min (Claudes) sandbox nulstilles ind imellem** og mister filer fra tidligere i
    samtalen. Antag ALDRIG jeg stadig har adgang til filer fra langt tidligere i en
    session - bed om friske kopier af main.py/models.py/index.html hvis noget virker
    forkert eller mangler.
13. **Dansk dato-fortolkning (`danish_date.py`)**: understøtter ordenstal ("niende i
    syvende seksogtyve"), månedsnavne, og numeriske formater (09/07/26). 15/15 tests
    bestået ved seneste bygning. Hvis parsing fejler, falder UI'en tilbage til manuel
    ÅÅÅÅ-MM-DD-indtastning via prompt().

## Kernefunktionalitet (alt implementeret og testet, medmindre andet fremgår)

- **Indkøbsliste**: stemme/tekst-tilføjelse, stort forbogstav automatisk, afkryds/slet
- **Butikker**: manuel/automatisk oprettelse (Overpass primær, Nominatim fallback),
  GPS-kalibrering (gå rundt, indsaml punkter, beregn centrum+radius), omdøbning, sletning
- **Proximity-system**: `/webhook/check-proximity` er det RIGTIGE endpoint HA's
  automation bruger (kører hvert minut). Stateful (kun ny besked ved ny ankomst),
  kun hvis der er varer på listen. `/webhook/store-entered` og `/webhook/nearest-store`
  er ældre, ikke længere aktivt brugte mellemtrin.
- **Diagnostik-infrastruktur** (bygget efterhånden som notifikations-fejl blev
  fundet): proximity-log, notification-log, missing-notification-reports,
  emulation/test-mode, store-distance-check, live HA-vs-browser-position-sammenligning
- **Backup/Gendan**: JSON-eksport/import af butikker+varer
- **Over dato** (NYT i v2.0.19): registrer varer derhjemme med talt dato (to-trins
  stemmeflow: navn, så dato), automatisk dansk datofortolkning, overskredne varer
  lægges automatisk tilbage på indkøbslisten, vises rødt/hvidt i egen fane

## HA-siden (uden for repoet, men vigtigt at kende)

- Automation i `automations/indkobsliste_proximity.yaml` (IKKE automations.yaml -
  intet ID, redigeres kun via fil)
- Kører `time_pattern minutes: "/1"`
- `rest_command.indkobsliste_check_proximity` i `configuration.yaml`, peger på
  `http://localhost:8000/webhook/check-proximity`
- Device tracker: `device_tracker.samsung_s23_ultra`
- Notify service: `notify.mobile_app_sm_s918b`

## Historik i store træk (kronologisk, forkortet)

1. Bygget fra bunden: FastAPI-backend, SQLite, PWA-frontend
2. Stemmeinput, butiksoprettelse (manuel + automatisk GPS-opslag)
3. Pakket som HA add-on, hostet på eget GitHub-repo (efter besvær med lokal vs.
   GitHub-baserede add-ons, arkitektur-udfasning, BOM-fejl)
4. Cloudflare Tunnel til ekstern HTTPS-adgang (`indkobsliste.skerra.dk`)
5. GPS-kalibreringsfunktion (gå rundt i butik, saml punkter)
6. Nærmeste-butik-algoritme (løser problem med tætliggende butikker af samme kæde)
7. Home Assistant-automation + notifikation - lang fejlsøgningsrejse:
   telefonens baggrundslokation virkede ikke pålideligt (Samsung batterioptimering),
   forkert notify-service-navn, ProximityState der "huskede" fejlagtigt sendte beskeder
8. Omfattende diagnostik-værktøjer bygget undervejs for at kunne fejlsøge uden fysisk
   at skulle stå ved en butik (emulation mode, tjek nu, notification log, missing
   report, HA-position-sammenligning)
9. Backup/gendan-funktion (efter datatab ved en geninstallation)
10. Database-auto-migration (efter "no such column"-fejl ved nye modelfelter)
11. Over dato-funktion med dansk talt-dato-fortolkning (v2.0.19, seneste tilføjelse)

## Din arbejdsstil i dette projekt (vigtigt)

- Test ALTID ændringer selv (kør serveren lokalt, curl) før du leverer kode
- Brug én sammenhængende bash-session pr. testforløb (server dør mellem separate
  tool-kald i visse miljøer)
- Lever ALTID hele, komplette filer klar til at erstatte - aldrig kodestykker
  brugeren selv skal splejse ind, MEDMINDRE du reelt ikke har adgang til den
  fulde eksisterende fil (så beder du om den i stedet for at gætte)
- Forklar tydeligt og trin-for-trin på dansk. Brugeren er teknisk kompetent
  (Python/webudvikling) men lærer HA's interne systemer undervejs
- Giv altid en samlet zip ved siden af enkeltfiler, når flere filer er ændret
