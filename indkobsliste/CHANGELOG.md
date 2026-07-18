# Changelog

## 1.0.2
- Tilføjet hamburgermenu med separate visninger for "Indkøbsliste" og "Butikker"
- Butikker vises nu som kort med navn, koordinater og radius, i stedet for én komma-separeret linje

## 1.0.1
- Automatisk stort forbogstav på varenavne (fx "tomater" → "Tomater")
- Klik på en vare i listen afkrydser/fjerner den (markerer som lagt i kurven)

## 1.0.0
- Første udgave: indkøbsliste med stemmeinput, manuel og automatisk (GPS/Overpass/Nominatim) butiksoprettelse, samt webhook-endpoint til Home Assistant-automationer

## 1.0.3
   - GPS-kalibrering: gå rundt i en butik for at få mere præcise koordinater og radius

## 1.0.4
   - Tilføjet "Fjern butik"-knap med bekræftelse

## 1.0.5
   - Nyt endpoint /webhook/nearest-store: finder nærmeste butik via afstandsberegning i stedet for overlappende zoner   

## 1.0.6
   - Nyt endpoint /webhook/check-proximity: løbende positionstjek uden faste zoner, med indbygget "husk sidste advarsel" så du ikke spammes med gentagne beskeder

## 1.0.7
   - Nye eller opdaterende filer får nu Timestamp

## 1.0.72
   - Live afstandsvisning til hver butik under "Butikker"

## 1.0.73
   - Rettet fejl: /stores/nearby var utilsigtet holdt op med at virke
   - Ny "Diagnostik"-fane: viser seneste positionstjek fra Home Assistant direkte i appen

## 1.0.74
   - Placering vises nu på forsiden hvor langt fra Hjem

## 1.0.75
   - Ny: viser HA's egen device_tracker-position i header, til direkte sammenligning med telefonens live GPS

## 1.0.77
   - Rettet: diagnostik-endpoint svarer nu altid 200, så Cloudflare ikke overskriver vores fejlbeskeder med sin egen fejlside

## 2.0.00
   - Ny versions numre

## 2.0.1
   - Ny "Backup"-fane: download/gendan alle butikker og varer som JSON-fil

## 2.0.2
   - Opsætning af besked når der er noget på listen

## 2.0.3
   - Versions nummer vises nu   

## 2.0.4
   - Automatiske forslag inkluderer nu adresse, og gemmer navn med gadenavn (undgår forveksling af kæder)
   - Butikstype gemmes nu i databasen
   - Ny funktion: tryk på en butiks navn for at omdøbe den

## 2.0.5
   - Rettet kritisk fejl: manglende 'shop_type'-kolonne på eksisterende database
   - Ny automatisk database-migration: fremtidige nye felter tilføjes nu automatisk uden datatab

## 2.0.6
   - Ret forkert versionsnummer i menu, tilføj version til alle filhoveder
   
## 2.0.7
   - Oprettelse af logfil til diag

## 2.0.8
   - Logfil kan ses fra menuen

## 2.0.9
   - Knap til mistede/maglende besker i Menuen

## 2.0.10
   - Flyttede Til ny butik til toppen af listen

   
## 2.0.11
   - Ny "Nulstil sidst notificeret"-knap i Diagnostik, til at rette op på fastlåst tilstand efter fejlede beskeder

## 2.0.12
   - Opdatering af hele systemet pga. forkert version nummer

## 2.0.13
   - Oprettelse af emulerings knap for notifikationer
