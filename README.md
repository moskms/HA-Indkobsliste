# HA Indkøbsliste

Dansk indkøbsliste-app med stemmeinput og automatisk butiksgenkendelse via GPS.
Kører som et Home Assistant add-on, bygget i Python (FastAPI + SQLModel) med en
simpel HTML/JS-frontend.

Ideen er enkel: du tilføjer varer til listen hjemmefra (eller med stemmen, på
farten), og når du senere nærmer dig en af dine faste butikker, sender Home
Assistant automatisk en notifikation til telefonen med det, du mangler at
købe – uden at du selv skal huske at åbne en app.

## Hvad kan den?

- **Indkøbsliste** – tilføj varer via stemme eller tekst, kryds af/slet, stort
  forbogstav sættes automatisk
- **Butikker** – opret manuelt, eller automatisk ud fra din nuværende GPS-position
  (opslag via Overpass, med Nominatim som fallback). Understøtter GPS-kalibrering:
  gå en runde om butikken, indsaml punkter, og appen beregner selv centrum og
  radius. Butikker kan omdøbes, så to butikker med samme kædenavn (fx to
  "Netto") ikke forveksles
- **Automatisk nærheds-notifikation** – Home Assistant spørger appen hvert
  minut om du er tæt på en kendt butik. Appen husker selv hvornår du sidst er
  blevet advaret, så du ikke får samme besked igen og igen, mens du står
  stille i butikken
- **Diagnostik** – se de seneste positionstjek og udløste notifikationer
  direkte i appen, uden at skulle grave i Home Assistants egne logs
- **Backup/gendan** – download og upload en JSON-backup af alle butikker og
  varer, fx før en versionsopgradering

## Arkitektur

| Del | Teknologi |
|---|---|
| Backend | FastAPI + SQLite (SQLModel) |
| Frontend | Én statisk HTML/JS-fil, tabs til Indkøbsliste/Butikker/Diagnostik/Backup |
| Hosting | Home Assistant add-on, installeret via dette GitHub-repo |
| Ekstern adgang | Cloudflare Tunnel |

Filstruktur i korte træk:

```
repository.yaml        ← gør repoet installerbart som add-on repo i HA
indkobsliste/
  config.yaml          ← add-on-metadata og version
  app/
    main.py            ← FastAPI-endpoints
    models.py          ← databasemodeller (SQLModel)
    database.py         ← init/migration af SQLite
    overpass.py         ← butiksopslag via OpenStreetMap Overpass
    nominatim.py         ← fallback-opslag + afstandsberegning
  frontend/
    index.html          ← hele frontenden
```

---

## Installation

### 1. Home Assistant (selve add-on'et)

1. Gå til **Settings → Add-ons → Add-on Store**
2. Klik ⋮ (menuen øverst til højre) → **Repositories**
3. Tilføj dette repos URL (fx `https://github.com/moskms/HA-Indkobsliste`)
4. Find "Indkøbsliste" i listen over tilgængelige add-ons, og installer
5. Start add-on'et, og bekræft at du kan tilgå frontenden lokalt via
   `http://<din-ha-adresse>:8000/app`

**Valgfrit – ekstern adgang uden for hjemmenetværket:**
Sæt en Cloudflare Tunnel op, der peger på samme port som add-on'et lytter på
(standard `8000`). Så kan du tilgå listen fra en vilkårlig URL, uafhængigt af
om du er hjemme på wifi eller ej.

### 2. Home Assistant-siden (automation + rest_command)

Tilføj følgende i `configuration.yaml`:

```yaml
rest_command:
  indkobsliste_check_proximity:
    url: "http://localhost:8000/webhook/check-proximity?lat={{ lat }}&lon={{ lon }}&threshold_m=50"
    method: GET
```

Opret derefter en automation (fx `automations/indkobsliste_proximity.yaml`,
**husk `- ` foran `alias:`** hvis den ligger i sin egen fil under
`!include_dir_merge_list`):

```yaml
- id: "indkobsliste_proximity_check"
  alias: Indkøbsliste - tjek nærhed til butikker
  description: Tjekker hvert minut om du er tæt på en kendt butik
  mode: single
  triggers:
    - minutes: /1
      trigger: time_pattern
  conditions: []
  actions:
    - action: rest_command.indkobsliste_check_proximity
      data:
        lat: "{{ state_attr('device_tracker.DIN_TELEFON', 'latitude') }}"
        lon: "{{ state_attr('device_tracker.DIN_TELEFON', 'longitude') }}"
      continue_on_error: true
      response_variable: proximity_response
    - if:
        - condition: template
          value_template: "{{ proximity_response is defined and proximity_response['status'] == 200 and proximity_response['content']['should_notify'] }}"
      then:
        - action: notify.DIT_NOTIFY_SERVICE
          data:
            title: Indkøbsliste
            message: "{{ proximity_response['content']['message'] }}"
```

Udskift `device_tracker.DIN_TELEFON` og `notify.DIT_NOTIFY_SERVICE` med dine
egne entity-navne (se punkt 3 nedenfor for hvordan du finder det rigtige
notify-navn).

### 3. Telefonen

1. Installer **Home Assistant Companion App** (Android/iOS) og log ind på din
   HA-instans – det er det, der leverer både GPS-position
   (`device_tracker`-enheden) og selve notifikations-servicen
2. **Find det korrekte notify-servicenavn**: Developer Tools → Actions → søg
   "notify" – brug det navn, HA rent faktisk lister (det matcher ikke altid
   telefonens "pæne" navn, fx `notify.mobile_app_sm_s918b` i stedet for det
   forventede modelnavn)
3. Slå lokationsdeling til med **høj nøjagtighed**, sæt appen på undtagelseslisten
   for batterioptimering, og giv lokationstilladelse **"Altid"** – ellers bliver
   baggrundspositionen upålidelig
4. Åbn appens URL (Cloudflare Tunnel-adressen, eller din lokale HA-adresse +
   `/app`) i telefonens browser, og læg den evt. som genvej på hjemmeskærmen

---

## Status – hvad er opnået

- [x] Fuld indkøbsliste med stemme-/tekstinput
- [x] Butiksoprettelse manuelt og automatisk via GPS (Overpass + Nominatim-fallback)
- [x] GPS-kalibrering af butiksradius
- [x] Stateful nærheds-webhook, der undgår gentagne notifikationer
- [x] Diagnostik-fane med positionstjek og HA-position-sammenligning
- [x] Backup/gendan-funktion
- [x] Robust automation-opsætning (overlever fejlede kald uden at crashe)
- [x] Notifikationslog til at spore falske positiver bagudrettet
- [x] Cloudflare Tunnel-deployment til ekstern adgang
- [x] Automatisk SQLite-migration ved nye modelfelter (ingen manuel migration nødvendig)

## Status – hvad mangler

- [ ] Vare-til-butikstype-matching (vis hvilken vare der typisk fås hvor –
      `shop_type` gemmes allerede på hver butik, klar til dette)
- [ ] TTS (højtlæst besked) i stedet for/i tillæg til tekst-notifikation
- [ ] Individuel `threshold_m` pr. butik i stedet for én fælles værdi for alle
- [ ] Undersøge og rette falske positiver ved butikker der ligger tæt på
      hinanden (fx to butikker med overlappende kalibreret radius)

---

## Vigtige faldgruber (læs før du ændrer noget)

- Versionsnumre i `config.yaml` sammenlignes **numerisk pr. segment**
  (`1.0.31` > `1.0.4`) – brug altid enkeltvise trin
- Kun `aarch64`/`amd64` som arkitektur i `config.yaml` – udfasede arkitekturer
  giver en stille afvisning uden tydelig fejl
- Cloudflare overskriver automatisk 4xx/5xx-svar – diagnostik-endpoints svarer
  derfor altid 200, med success/error i JSON-body
- Tag altid en `/backup` **før** en versionsopgradering – app-data kan gå tabt
  ved geninstallation
- Tjek altid det faktiske notify-servicenavn via Developer Tools, stol ikke på
  et gæt ud fra telefonens modelnavn

## Licens

Privat hobbyprojekt – ingen formel licens angivet endnu.
