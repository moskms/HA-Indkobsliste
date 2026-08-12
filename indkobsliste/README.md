<!-- Sidst opdateret: 2026-08-12 -->
# Indkøbsliste

En dansk indkøbsliste-app bygget som Home Assistant-add-on. Kernen: når du er
fysisk tæt på en af dine faste butikker, og der står noget på din
indkøbsliste, får du automatisk en push-notifikation. Udvidet med en "over
dato"-funktion til varer derhjemme, stemmerettelser og en daglig
udløbspåmindelse.

## Funktioner

### Indkøbsliste
- Tilføj varer med stemmeinput (dansk), automatisk stort forbogstav
- Afkryds/slet varer

### Butikker
- Opret faste butikker manuelt, eller lad appen foreslå butikker automatisk nær din position (Overpass, med Nominatim som fallback)
- GPS-kalibrering: gå rundt i butikken for at få mere præcise koordinater og radius
- Omdøbning (fx til at skelne mellem flere butikker af samme kæde)

### Proximity-notifikationer
- Webhook-endpoint (`/webhook/check-proximity`) til en Home Assistant-automation: sender kun én notifikation pr. ankomst, og kun hvis der er varer på listen
- "Test-tilstand" (emulering): sender en rigtig besked ved hvert kald, til at teste uden at gå ud
- "Tjek nu": bruger enhedens egen GPS til at vise afstand til alle butikker og om der ville blive sendt en besked

### Over dato
- Registrer varer derhjemme med en talt dato, via popup-flow: sig varens navn → indtal dato → godkend eller prøv igen
- Dansk datofortolkning forstår både ordenstal ("tolvte") og grundtal ("tolv"), månedsnavne, og numeriske formater
- Overskredne varer lægges automatisk tilbage på selve indkøbslisten

### Indstillinger
- **Stemmerettelser**: ord talegenkendelsen konsekvent hører forkert (fx "roastbeef" bliver hørt som "roskilde") kan tilføjes som en rettelse, der anvendes automatisk på både indkøbslisten og Over dato
- **Udløbsnotifikation**: daglig påmindelse hvis noget på Over dato-listen udløber snart, med konfigurerbart antal dage før og klokkeslæt (kræver en Home Assistant-automation der kalder `/webhook/check-expiring-soon`)

### Diagnostik og notifikationer
- Log over alle positionstjek fra Home Assistant, og over rent faktisk sendte notifikationer
- "Jeg fik ikke en besked": rapportér øjeblikkeligt din position til senere sammenligning med hvad HA's periodiske tjek så
- Live sammenligning af browserens GPS-position og HA's device_tracker-position

### Backup
- Download alle butikker og varer som en JSON-fil
- Gendan fra en tidligere backup-fil (tilføjer, sletter ikke eksisterende data)

## Brug

Efter start, åbn web-grænsefladen via "OPEN WEB UI"-knappen, eller direkte på:

```
http://<din-ha-adresse>:8000/app/index.html
```

## Home Assistant-opsætning

Udover selve add-on'et kræver visse funktioner en automation og en
`rest_command` i Home Assistants `configuration.yaml`:

- **Proximity-notifikationer**: `rest_command.indkobsliste_check_proximity` + en automation der kalder den periodisk (fx hvert minut) og sender en push-notifikation når `should_notify` er sand
- **Udløbsnotifikation**: `rest_command.indkobsliste_check_expiring_soon` + en automation der kalder `/webhook/check-expiring-soon` periodisk (fx hvert 5. minut) og sender en push-notifikation når `should_notify` er sand

Se `CHANGELOG.md` for detaljer om hvornår hver funktion blev tilføjet.
