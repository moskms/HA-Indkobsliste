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

## 1.0.8
   - Rettet fejl: /stores/nearby var utilsigtet holdt op med at virke
   - Ny "Diagnostik"-fane: viser seneste positionstjek fra Home Assistant direkte i appen
