<!-- Sidst opdateret: 2026-09-07 (v2.0.43) -->
# Instruktioner til Claude: installation af "Indkøbsliste" add-on'et

Denne fil henvender sig til en AI-agent (Claude) der er blevet bedt om at
installere eller opsætte dette Home Assistant add-on for en bruger - IKKE
til et menneske, der læser koden. Er du en person, se i stedet
[README.md](README.md), som har den samme information skrevet som almindelig
dokumentation.

Formålet med denne fil er at gøre installationen fejlfri, uanset hvilken
konkret Home Assistant-opsætning brugeren har. De fleste fejl i denne slags
installation skyldes ikke selve add-on'et, men forkerte antagelser om
brugerens miljø (installationstype, arkitektur, eksisterende YAML-nøgler,
faktiske entity-navne) - læs derfor hele denne fil FØR du foretager dig
noget, og følg rækkefølgen nedenfor.

## Grundregel: gæt aldrig, bekræft altid

Alt der er specifikt for brugerens installation - entity-navne
(`device_tracker.*`, `notify.*`), om der allerede findes en `rest_command:`
eller `automation:`-nøgle i deres `configuration.yaml`, om Supervisor er
tilgængelig, hvilken arkitektur deres system kører - skal du få bekræftet
fra selve installationen (via Developer Tools, filsystemet, eller ved at
spørge brugeren direkte), ALDRIG antaget eller opfundet. En automation der
peger på en entity, der ikke findes, fejler stille og er svær at
fejlfinde bagefter.

## Trin 0: Bekræft at add-on-metoden overhovedet kan bruges

Dette er et Home Assistant **add-on**, hvilket kun kan installeres på
installationer der har **Supervisor** (Settings → Add-ons findes i
sidemenuen):

- **Home Assistant OS (HAOS)** - fungerer, Supervisor er indbygget.
- **Home Assistant Supervised** (kørende på egen Linux/Debian) - fungerer,
  har Supervisor.
- **Home Assistant Container** (rå Docker, ingen Supervisor) - **kan IKKE
  installere add-ons overhovedet**. Der findes intet Add-on Store-menupunkt.
- **Home Assistant Core** (Python venv/pip-installation) - samme
  begrænsning som Container.

Tjek dette FØR du går videre - fx ved at spørge brugeren, eller ved at
kigge efter "Add-ons" i deres sidemenu/instans. Rammer du Container eller
Core, findes der ingen understøttet vej til at installere dette add-on:
fortæl brugeren det tydeligt i stedet for at forsøge en workaround (fx at
køre `app/`-koden manuelt i en løsrevet Docker-container) - det er en helt
anden opsætning end det dette repo er bygget til, og ikke noget der er
testet eller dokumenteret her.

Tjek også arkitektur (Settings → System → Hardware, eller spørg brugeren):
kun **aarch64** og **amd64** er understøttet (se `indkobsliste/config.yaml`
→ `arch:`). Andre arkitekturer (fx armhf/armv7) fejler med en stille
afvisning i Add-on Store, ikke en tydelig fejlbesked.

## Trin 1: Installer selve add-on'et

1. Settings → Add-ons → Add-on Store → ⋮ (menuen øverst til højre) →
   Repositories.
2. Tilføj repo-URL'en: `https://github.com/moskms/HA-Indkobsliste`.
3. Find "Indkøbsliste" i listen over tilgængelige add-ons (kan kræve et
   sideskift/opdatering af Add-on Store-siden) og installer den.
4. Start add-on'et.
5. Bekræft at frontenden svarer: `http://<brugerens-ha-adresse>:8000/app`
   (typisk `http://homeassistant.local:8000/app` eller en lokal IP).

Hvis brugeren allerede har add-on'et installeret og dette er en
**opgradering**: bed dem tage en backup via appens egen "Backup"-fane
(download JSON-filen) FØR du fortsætter - se de "Vigtige faldgruber" i
README.md om hvorfor.

## Trin 2: Anthropic API-nøgle (kun hvis "Indscan bon" skal bruges)

"Indscan bon" (kvitteringsscanning via Claude vision) er valgfri - resten
af appen virker uden. Spørg brugeren om de vil bruge denne funktion, FØR du
beder om en nøgle.

Hvis ja: brugeren skal selv oprette/hente sin egen nøgle på
[console.anthropic.com](https://console.anthropic.com) og give dig den, ELLER selv
indtaste den direkte i Home Assistant. **Indtast aldrig en API-nøgle på
brugerens vegne uden at de eksplicit har givet dig den til formålet** -
sæt den under Settings → Add-ons → Indkøbsliste → **Configuration**-fanen
(ikke Info-fanen), feltet "Anthropic api key", og genstart add-on'et
(Info-fanen → Stop → Start) så konfigurationen bliver læst ind.

## Trin 3: `configuration.yaml` - rest_command

Formålet er at give Home Assistant to nye REST-kald, som automations i
trin 4 bruger. **Før du tilføjer noget**: læs brugerens eksisterende
`configuration.yaml` igennem, og tjek om der allerede findes en
`rest_command:`-nøgle. YAML tillader kun ÉN forekomst af samme
topnøgle i samme fil - findes den allerede, TILFØJ dine to nye kald som
undernøgler i det EKSISTERENDE block, opret IKKE et nyt, separat
`rest_command:`-block (det vil enten fejle eller stille overskrive det
eksisterende, afhængig af YAML-parseren).

```yaml
rest_command:
  indkobsliste_check_proximity:
    url: "http://localhost:8000/webhook/check-proximity?lat={{ lat }}&lon={{ lon }}&threshold_m=50"
    method: GET

  indkobsliste_check_expiring_soon:
    url: "http://localhost:8000/webhook/check-expiring-soon"
    method: GET
```

`indkobsliste_check_expiring_soon` er kun nødvendig hvis brugeren vil have
den daglige "snart over dato"-notifikation (se trin 4b) - ellers kan den
udelades.

## Trin 4: Automations

### 4a. Nærheds-notifikation (kernefunktionen)

Denne automation kræver to entity-navne der er UNIKKE for brugerens egen
installation - **find dem for brugerens faktiske instans, gæt aldrig**:

- `device_tracker.*` - findes typisk automatisk når brugeren har
  installeret Home Assistant Companion App og delt lokation. Bekræft det
  faktiske navn via Developer Tools → States, filtreret på "device_tracker".
- `notify.*` - servicenavnet matcher IKKE altid telefonens "pæne"
  modelnavn (fx `notify.mobile_app_sm_s918b`, ikke
  `notify.samsung_galaxy_s24`). Bekræft via Developer Tools → Actions, søg
  "notify", og brug det navn HA rent faktisk lister.

Er Companion App ikke installeret/lokation ikke delt endnu, kan disse
entities slet ikke findes - bed i så fald brugeren installere appen og
aktivere lokationsdeling (høj nøjagtighed, batterioptimering slået fra for
appen, lokationstilladelse "Altid") FØR du opretter denne automation.

Opret automationen (fx som `automations/indkobsliste_proximity.yaml`,
**husk `- ` foran `alias:`** hvis filen ligger under
`!include_dir_merge_list` - se advarslen i README.md's "Vigtige
faldgruber" om hvorfor dette er kritisk):

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

Udskift `device_tracker.DIN_TELEFON` og `notify.DIT_NOTIFY_SERVICE` med de
BEKRÆFTEDE navne fra ovenfor - ikke pladsholderne.

### 4b. Udløbsnotifikation (valgfri, kun hvis brugeren vil bruge "Over dato")

```yaml
- id: "indkobsliste_expiry_notify"
  alias: Indkøbsliste - udløbsnotifikation
  triggers:
    - minutes: /5
      trigger: time_pattern
  conditions: []
  actions:
    - action: rest_command.indkobsliste_check_expiring_soon
      response_variable: expiry_check
    - condition: template
      value_template: "{{ expiry_check.content.should_notify }}"
    - action: notify.DIT_NOTIFY_SERVICE
      data:
        title: Over dato snart
        message: "{{ expiry_check.content.message }}"
```

Selve klokkeslættet og antal dage før udløb sættes i appens eget
Indstillinger-fane, ikke i automationen - automationen må gerne tjekke
oftere end der reelt sendes noget, endpointet holder selv styr på højst
én besked pr. dag.

Samme regel som i trin 3 gælder her: findes der allerede en
`automation:`-topnøgle i `configuration.yaml` (i stedet for opdelte filer
under `automations:`/`automation !include_dir_merge_list`), tilføj IKKE et
nyt, konkurrerende block.

## Trin 5: Verificér

Antag ikke installationen virker, fordi trinene blev udført uden fejl -
bekræft aktivt:

1. Genindlæs/genstart Home Assistant så den nye YAML bliver læst ind
   (Developer Tools → YAML → "Check configuration" først, for at fange
   syntaksfejl før en fuld genstart).
2. Settings → Automations - bekræft at de nye automations findes og er
   aktiveret (ikke deaktiveret som standard).
3. Automationen har et `id:`-felt (se YAML ovenfor) - uden det kan
   **Traces**-fanen (Settings → Automations → automationen → Traces) ikke
   bruges til fejlsøgning, og du får bare en fejl om manglende ID.
4. Test evt. et manuelt kald til `rest_command.indkobsliste_check_proximity`
   via Developer Tools → Actions, og se om `response_variable`-indholdet
   ser fornuftigt ud.
5. Bekræft at appens frontend (`http://<ha-adresse>:8000/app`) rent
   faktisk loader, og at "Indscan bon"-fanen viser en fejlbesked om
   manglende API-nøgle FREM FOR at crashe, hvis nøglen ikke er sat endnu.

## Andre gotchas (se README.md for den fulde liste)

- Cloudflare Tunnel (hvis brugt til ekstern adgang) overskriver automatisk
  4xx/5xx-svar med sin egen fejlside - dette er allerede håndteret i
  add-on'ets egne endpoints (de svarer altid HTTP 200 med success/error i
  JSON-body), så det kræver ingen handling fra dig, men er værd at vide
  hvis noget ser ud til at fejle "stille".
- Versionsnumre i `config.yaml` sammenlignes numerisk pr. segment
  (`2.0.31` > `2.0.4`) - relevant hvis du selv skal bumpe en version, ikke
  ved en almindelig installation.
- Home Assistant 2024.8/2024.10 omdøbte automation-nøgler (`service:` →
  `action:`, `platform:` → `trigger:`). YAML'en i denne fil bruger den nye
  syntaks - virker på nyere HA-versioner. Er brugerens HA ældre, kan den
  gamle syntaks være nødvendig i stedet.

Se README.md's "Vigtige faldgruber" for den fulde, løbende opdaterede liste.
