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

## 2.0.14
   - - - - - - 

## 2.0.15
   - Manglende emulings knap

## 2.0.16
   - tilføjer en knap, der henter telefonens/browserens egen GPS-position og sender den direkte til check-proximity-endpointet
   
## 2.0.17
   - Findes ikke

## 2.0.18
   - Oprettelse af log fil når Tjek nu knappen bruges
   
## 2.0.19
   - Ny "Over dato"-funktion: indtal vare + dato, automatisk dansk datofortolkning, overskredne varer lægges automatisk tilbage på indkøbslisten

## 2.0.20
   - "Over dato"-flowet bruger nu rigtige popups i stedet for tekstfeedback: "Sig varens navn" -> "Indtal dato" -> godkend/prøv igen
   - "Prøv igen" genstarter hele optagelsen (navn + dato) uden at skulle skrive noget manuelt
   - Dansk datofortolkning forstår nu også grundtal ("tolv") og ikke kun ordenstal ("tolvte") - gælder alle tal fra 1-31

## 2.0.21
   - Rettet fejl: "Prøv igen" i Over dato-flowet kunne hænge fast for evigt, hvis telefonens talegenkendelse fejlede stille ved for hurtig genstart. Tilføjet pause, timeout og onend-håndtering, så flowet altid afsluttes med enten resultat eller en tydelig fejl-popup
   - Rettet fejl: datoer hvor talegenkendelsen slår måned+år sammen uden mellemrum (fx "30 826" i stedet for "30 8 26") bliver nu fortolket korrekt

## 2.0.22
   - Ny "⚙️ Indstillinger"-fane
   - Stemmerettelser: ord talegenkendelsen konsekvent hører forkert (fx "roastbeef" -> "roskilde") kan nu tilføjes som en rettelse, der anvendes automatisk på både indkøbslisten og Over dato
   - Ny daglig udløbsnotifikation: nyt endpoint /webhook/check-expiring-soon (til en ny HA-automation) advarer når varer på Over dato-listen udløber inden for et konfigurerbart antal dage, på et konfigurerbart klokkeslæt - styres fra Indstillinger-fanen

## 2.0.23
   - Ny "🧾 Indscan bon"-fane: tag et billede af en kassebon, Claude (vision) genkender butik/dato/varer/priser og returnerer det som struktureret tekst - selve billedet gemmes ALDRIG, hverken permanent eller midlertidigt
   - Gennemsyns-skærm før noget gemmes: ret butik/dato/varelinjer/total manuelt, uanset om de kom fra en scanning eller blev tastet fuldt manuelt (samme "godkend før gem"-princip som Over dato-flowet)
   - Ved fejl (ingen forbindelse, ugyldig API-nøgle, Claude nede) beholdes billedet i telefonens hukommelse, så "Prøv igen" ikke kræver et nyt foto - eller vælg "Indtast manuelt i stedet"
   - Nyt: arkiv over tidligere bonner (GET /receipts), og prishistorik-opslag pr. vare på tværs af alle bonner (GET /receipts/price-history/lookup)
   - Ny add-on-option ANTHROPIC_API_KEY (Konfiguration-fanen i HA) - kræves for at scanningen virker, sættes aldrig i kode/git
   - Billedet skaleres og komprimeres i browseren (maks 1600px, JPEG) før upload, for hurtigere upload og billigere Claude-kald

## 2.0.24
   - "Scan bon" åbner nu en in-app kameravisning (i stedet for telefonens egen kamera-app) med en lys/torch-knap - nyttigt til ældre, falmede termopapir-bonner, hvor Claude ellers kan fejlaflæse små, udviskede cifre (bekræftet: dato blev læst forkert på en ældre bon, men helt korrekt på en frisk-printet bon)
   - Falder automatisk tilbage til telefonens egen kamera-app, hvis in-app kameraet/lyset ikke understøttes (fx iOS Safari)

## 2.0.25
   - Rullet 2.0.24 tilbage igen: den in-app kameravisning gav markant dårligere, uskarpe billeder (ingen autofokus/billedstabilisering) sammenlignet med telefonens egen kamera-app, og scanninger blev derfor upålidelige (for mange/forkerte varelinjer)
   - "Scan bon" åbner igen telefonens egen kamera-app direkte - den har i forvejen sin egen lys/blitz-knap indbygget, ingen kode nødvendig for det

