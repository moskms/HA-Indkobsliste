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

## 2.0.26
   - Ny knap "🛒 Fjern + køb igen" på hvert Over dato-kort, ved siden af "Fjern" - tilføjer varen til selve indkøbslisten OG fjerner den fra Over dato i samme handling, til når man har brugt det sidste af noget og skal have mere

## 2.0.27
   - Backup/gendan omfatter nu også Indscan bon: bonner og deres varelinjer (navn, pris, mængde, dato, total) tages med i /backup, og gendannes korrekt via /restore - testet med fuld roundtrip (opret bon -> backup -> gendan i tom database -> bekræft data matcher)
   - Backup- og gendan-knapperne i appen viser nu også antal bonner (og varelinjer ved gendannelse)

## 2.0.28
   - Rettet fejl: "Gendan fra fil"-knappen kunne ikke se/vælge den downloadede backup-fil på mobilen. Årsag: accept="application/json" filtrerer for strengt - mange mobile browsere gemmer den downloadede JSON-fil uden præcis den MIME-type, så filvælgeren skjulte den. Udvidet til også at matche på filendelse (.json)

## 2.0.29
   - Rettet fejl: /restore var ikke idempotent - gendannede man samme backup-fil flere gange, blev butikker/varer/bonner duplikeret for hver gendannelse. /restore springer nu automatisk dubletter over (butik: samme osm_id eller navn, vare: samme navn+afkrydsningsstatus, bon: samme butik+dato+total), testet ved at gendanne samme backup 3 gange i træk uden at data blev duplikeret
   - Gendan-feedback i appen viser nu også hvor mange dubletter der blev sprunget over

## 2.0.30
   - Rettet fejl: "Registrerede varer" (Over dato) blev først rød dagen EFTER udløbsdatoen, ikke på selve dagen - rettet til at blive rød på selve udløbsdatoen
   - Ny gul status: varer der er mere end én dag over udløbsdatoen vises nu med gul i stedet for rød
   - Ny bon-oversættelsesordbog til Indscan bon: i bon-arkivet kan hver varelinje nu få tilføjet en manuel oversættelse af den rå, ofte forkortede bon-tekst (fx "3st ROASTBEEF" -> "3 stjernet Roastbeef") - gemmes både på selve varelinjen og i en global ordbog, så fremtidige scanninger af samme rå tekst automatisk foreslår oversættelsen i gennemsynsskærmen
   - Oversættelsesfeltet er bevidst kun synligt på enheder med mus/trackpad (PC), ikke på mobil/touch, da det er beregnet til at blive udfyldt i ro og mag ved et rigtigt tastatur
   - Prishistorik-opslag matcher nu også på oversat navn, ikke kun den rå bon-tekst
   - Backup/gendan omfatter nu også bon-oversættelsesordbogen, inkl. dublet-beskyttelse ved gentagne gendannelser

## 2.0.31
   - Rettet fejl: klik i det nye oversættelsesfelt i bon-arkivet lukkede med det samme selve bonnen igen, fordi klikket boblede op til kortets egen åbn/luk-knap. Alle klik inde i den åbne bon-detalje (oversættelsesfelt, "Slet bon") lukker nu ikke længere boksen

## 2.0.32
   - Ny: "Opdater"-knappen i bon-arkivet (Tidligere bonner) synkroniserer nu automatisk ALLE varelinjer, også på ældre bonner, med den nyeste bon-oversættelsesordbog - retter man oversættelsen for "3st ROASTBEEF" på én bon, slår den nu også igennem på alle andre bonner (uanset butik/dato) med samme rå tekst, uden at man skal rette dem én for én
   - Nyt endpoint POST /receipts/apply-known-translations til dette

## 2.0.33
   - Ny "Rabat i alt" over "Slet bon" i bon-arkivet - viser den samlede rabat på bonnen (forskellen mellem summen af varelinjerne og bonnens total), også på allerede indscannede bonner. Bekræftet mod en rigtig Føtex-bon: 298,40 kr i varelinjer minus 34,85 kr i rabat = 263,55 kr total, nøjagtigt som bonnen selv viser
   - Rettet grundlæggende fejl i Indscan bon: bonner med rabat pr. vare (fx "RABAT 6,95-" lige under en vare, meget almindeligt hos Føtex m.fl.) blev tidligere gemt med LISTEPRISEN i stedet for hvad der faktisk blev betalt, fordi Claude blev bedt om at se bort fra rabatlinjer i stedet for at bruge dem. Claude bruger nu rabatlinjen til at regne varens linjepris ned til det faktisk betalte beløb, og gemmer selve rabatbeløbet i et nyt felt (discount) - vises som en lille rød note under varen i bon-arkivet
   - Backup/gendan udvidet til også at omfatte discount-feltet pr. varelinje

## 2.0.34
   - Bon-arkivets varelinjer viser nu rabat på samme måde som selve papirbonnen: listepris ud for varens navn, en "{antal} x {stk-pris}"-linje hvis der er købt mere end 1, og en separat RABAT-linje med sit eget beløb - i stedet for kun at vise nettoprisen som ét tal
   - "Rabat i alt" er omdøbt til "Rabat total", og der vises nu også en "Total"-linje (bonnens faktiske total) lige under - samme bund-opstilling som selve bonnen
   - Rettet regnefejl i "Rabat total": beregningen brugte tidligere kun nettoprisen, hvilket ville vise 0 kr i rabat for korrekt indscannede bonner (fordi rabatten allerede var trukket fra prisen) - regner nu ud fra listeprisen (nettopris + rabat) i stedet

## 2.0.35
   - Redesignet gennemsynsskærmen (Indscan bon, både efter en scanning og ved manuel indtastning): varenavn til venstre og pris til højre, i stedet for tre smalle bokse i en række der var svære at overskue
   - Ny redigerbar RABAT-linje pr. varelinje (som på selve bonnen), og et "Oversæt ... til..."-felt (kun på desktop, samme som i bon-arkivet) - forudfyldt hvis ordbogen allerede kender teksten
   - Ny "Rabat total" og "Beregnet total" nederst, der opdateres live mens du retter priser/rabat - med en "Brug denne total"-knap til at kopiere den ind i selve Total-feltet
   - Claudes forslag til oversættelse og evt. fundne rabatbeløb fra scanningen bliver nu rent faktisk vist i gennemsynsskærmen (blev tidligere modtaget fra serveren, men droppet af frontenden uden at blive brugt)

## 2.0.36
   - Rettet grundlæggende designfejl i Indscan bon: Claude blev bedt om selv at regne rabatten fra prisen (fx 98,00 - 23,00 = 75,00), hvilket i praksis gav regnefejl på enkelte varelinjer (bekræftet: én linje endte forkert som 70,00 kr i stedet for 75,00 kr). Claude laver nu INGEN udregning overhovedet - "price" er nu udelukkende varens listepris PRÆCIS som den står trykt (fx 98,00), og "discount" er rabatbeløbet PRÆCIS som det står trykt (fx 23,00). Al regning (nettopris, rabat total) foretages nu af selve appen, ikke af Claude - markant mere pålideligt, da transskription er en langt enklere opgave end transskription+udregning
   - Bon-arkiv, gennemsynsskærm og prishistorik-opslag er opdateret til den nye betydning af "price" (listepris i stedet for nettopris)

## 2.0.37
   - Ny automatisk kontrol i gennemsynsskærmen: "Beregnet total" (summen af varelinjerne minus rabat) sammenlignes nu live med selve Total-feltet - stemmer de ikke overens, vises en tydelig advarsel med hvor meget der mangler/er for meget, så en fejllæst pris opdages FØR bonnen gemmes, i stedet for først at blive opdaget bagefter i arkivet

## 2.0.38
   - Gennemsynsskærmens varelinjer er redesignet til at genbruge PRÆCIS samme skrift/opsætning som bon-arkivet: varenavn til venstre/pris til højre uden kant om felterne, "{antal} x {stk-pris}" og en "Rabat -X kr"-linje - og begge dele vises nu KUN når de reelt afviger fra standard (antal 1, ingen rabat), ligesom i arkivet
   - Fjernet "✕ Fjern linje"-knappen fra hver varelinje - et tomt varenavn springes stadig automatisk over ved gem, så en linje kan stadig fjernes ved at rydde navnefeltet

