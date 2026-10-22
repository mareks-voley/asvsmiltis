# Piezīmes pārbaudes aģentam (asvsmiltis.com)

Šo failu lasa un papildina rīta pārbaudes aģents. Augšā ir pastāvīgās zināšanas, apakšā labojumu žurnāls (jaunākais augšā, ne vairāk par 30 ierakstiem).

## Kā lapa tiek atjaunināta
1. **05:15 Rīgā (02:15 UTC)**: GitHub Actions `.github/workflows/rita-atjauninajums.yml` palaiž `update.py` (VolleyballLife → data.json) un `check.py`. Neatkarīgs no Claude.
2. **05:47 Rīgā**: Claude ieplānotais uzdevums "Latvietes ASV smiltīs — rīta atjaunināšana" (trig_01A6xWequNJZiz4icYpaFate). Lasa skolu lapas ar WebFetch, papildina data.json, sūta ziņu īpašniekam.
3. **06:37 Rīgā**: Claude pārbaudes aģents (šis). Pārbauda, labo, uzlabo procesu, ziņo.

## Zināmās īpatnības
- VolleyballLife API (`https://api-v8.volleyballlife.com`) atbild tikai ar pilnu pārlūka User-Agent (piem. `Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36`). Ar īsu `Mozilla/5.0` → 404.
- Profili: Ēbere 410021, Cabule 403848, Mamaja 360060, Runce 332711, Martini Ādamsone 259411 (VBL: "Ki Martini Adamsone"), Vildere 261353, Konstantinova 258656, Rīta 170656, Krieva 333617, Kazaka 410830.
- Tulane un Southern Miss piesaka visu komandu kā "Pair N" ar 4–10 vārdiem → pāris nav nosakāms; rezultātus meklēt skolas ziņās.
- Skolu Sidearm lapas (usctrojans.com, tulanegreenwave.com, gohatters.com, southernmiss.com, fiusports.com, gofrogs.com, goccusports.com, utepminers.com) ir aiz Incapsula aizsardzības: curl no Claude sesijas → 302 cilpa/403. Lasīt tikai ar WebFetch.
- Claude sesijām tīkla piekļuvi nosaka claude.ai **Settings → Capabilities → Allow network egress** (ieslēgts 2026-10-20). Ja curl atgriež "CONNECT tunnel failed, response 403", tas ir šis iestatījums – jāpasaka īpašniekam.
- GitHub GraphQL un Pages API no Claude sesijas nav pieejami; REST `gh api repos/mareks-voley/asvsmiltis/actions/...` strādā.
- Lapa ir tikai par pludmales volejbolu. Anna Rīta rudenī spēlē zāles volejbolu – to neliekam.
- Vārdu rakstība: Marta Vildere, Loreta Cabule, Kitija Martini Ādamsone, Evelīna Krieva, Karlīna Kazaka, Līva Ēbere, Anna Rīta.

## Labojumu žurnāls
- 2026-10-22 — Izveidots `update.py` (VolleyballLife) + GitHub Actions grafiks, `check.py` pārbaudes, šis aģents. Iemesls: Claude rīta uzdevums vairākas dienas pēc kārtas nepublicēja datus (tīkla iestatījums, nepilns User-Agent, 21.–22.10. nav push).
