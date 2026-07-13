# 🎯 PLÁN PRESNOSTI v2 — cesta k ±10 % na hrubom zdive

> Vypracované 2026-07-05, revidované po diskusii. ROZSAH SA NEMENÍ: materiál + murárska
> práca (zdivo, preklady, veniec). ŽIADNE lešenie/presun hmôt/réžia — namiesto toho
> transparentná veta v UI. Len free zdroje. Nadväzujeme na existujúci dobrý základ —
> spresňujeme a šperkujeme, nerozširujeme.

---

## ROZSAH — čo appka počíta (a s čím sa porovnáva)

**Počítame:** tvárnice + malta/lepidlo + preklady + veniec + murárska práca. Bez DPH.
**Nepočítame (zámerne):** lešenie, presun hmôt, doprava, réžia firmy, zateplenie.
**UI doplniť vetu:** „Cena neobsahuje lešenie, presun hmôt a réžiu stavebnej firmy."

Dva medzisúčty vo výkaze (už čiastočne existujú — len zvýrazniť):
- 📦 MATERIÁL → porovnateľné s ponukou stavebnín / výrobcu (Wienerberger, Ytong, DEK)
- 🔨 PRÁCA → porovnateľné so sadzbami murárov
Klient tak vie, ktoré číslo s ktorou reálnou ponukou porovnávať.

---

## A. OPRAVY V EXISTUJÚCEJ LOGIKE (revízia kódu, rozsah sa nemení)

Chyby sa dnes čiastočne kompenzujú → na Ytong ponuke to sedí, na inom type domu nemusí.
Každú opraviť SAMOSTATNE a overiť izolovane proti ground truth.

| # | Nález | Kde | Dopad |
|---|---|---|---|
| A1 | Zdivo na plných 2.8 m × podlažie A veniec zvlášť = dvojpočet. Murivo sa muruje po spodok venca: výška muriva = konštrukčná − (veniec+strop) ≈ 2.5–2.75 m | pricing.py:169 | ~+9 % obvod. zdiva |
| A2 | Okno paušál 1.5 m² — moderné RD: francúzske okná 4–7 m². Čítať šírky otvorov z kót / výpis okien z dokumentácie | pricing.py:18 | odpočty podcenené |
| A3 | Preklad paušál na otvor — reálne f(svetlosť, hrúbka): okno 1 m ≈ 1 400 Kč, HS portál 8–15 tis., garáž 10–15 tis. Tabuľka do cihly.json | pricing.py:247 | ± desaťtisíce |
| A4 | Priečky murované na 2.8 m — reálne po strop (svetlá ~2.6 m) | pricing.py:227 | ~+7 % priečok |
| A5 | Štítové steny pri sedlovej streche = 15–30 m² zdiva — ignorované. Čítať typ strechy (rez/pohľady ak sú); inak parametricky + širší band | extract+pricing | podcenenie |
| A6 | Nosné vnútorné bez odpočtu otvorov (dvere v nosných + ich preklady) | pricing.py:192 | malý |

Pozn.: ztratné/prořez materiálu (~5 %) — zvážiť ako súčasť spotreby materiálu (nie ako
položku réžie). Rozhodnúť pri kalibrácii proti reálnym ponukám stavebnín.

---

## B. EXTRACTION UPGRADE (1 prompt + podmienené prídavky — NIE 4 povinné passy)

Dnes: mega-prompt, agregáty, globálna confidence, variance ~7 % medzi behmi.

**B1. Itemizovaná schéma (najväčšia zmena):** model vracia ZOZNAMY, nie súčty:
- steny: [{segment, dĺžka, hrúbka, typ nosná/priečka/obvod}]
- otvory: [{typ okno/dvere/garáž/portál, šírka_m, v_stene}]
- Súčty a plochy počíta PYTHON (LLM zle sčítava).
- **Deterministický check uzavretosti polygónu:** Σ obvodových segmentov v smere X aj Y
  musí sedieť s celkovými kótami (bounding box) → matematický dôkaz správneho čítania.

**B2. Gemini `response_schema` (JSON mode)** — vynútená štruktúra, eliminuje parsovacie chyby.

**B3. Self-consistency 3× PARALELNE** (asyncio — inak sa nezmestíme do Vercel 60s):
numerické polia → medián. Variance ~7 % → <3 %. Zhoda 3/3 → užší ±band, rozptyl → eskalácia.

**B4. Confidence PER POLE** namiesto globálnej → cielená eskalácia (Opus číta len sporné
pole, nie celý výkres).

**B5. Podmienené passy LEN pre projektové dokumentácie (viacstránkové PDF):**
- výpis okien/dverí (tabuľka) → presné plochy otvorov (najlepší zdroj pre A2)
- rez → konštrukčná/svetlá výška (vstup pre A1, A4)
- pohľady → typ strechy/štíty (vstup pre A5)
Samostatný pôdorys tieto passy NEspúšťa (latencia, cena).

**B6. Disciplína:** každá zmena promptu = regresný beh eval.py, porovnanie metrík pred/po.
Žiadne ladenie „od oka".

**B7. Model risk:** gemini-3.1-pro-preview je PREVIEW — pin + otestovaný fallback reťazec
(pro → flash), s odmeraným dopadom fallbacku na presnosť (eval.py to zmeria).

---

## C. ZÍSKAVANIE ZNALOSTÍ (free)

1. **Verejné zákazky (NEN, profily zadávateľov):** výkazy výmer S CENAMI víťazov =
   reálne jednotkové ceny murovacích prác a materiálu zadarmo. Zozbierať 10–20.
2. **Výrobcovia (free kalkulačky + MOC cenníky):** Wienerberger/Ytong/Heluz — spotreba
   ks/m², malta l/m² → validácia malta_pct; cenníky → triedy v cihly.json.
   ⚠️ Ich ponuky = LEN MATERIÁL (+doprava, palety) — porovnávať s materiálovým medzisúčtom!
3. **RTS cenové ukazatele (stavebnistandardy.cz, free):** Kč/m³ obostavaného priestoru →
   nezávislý cross-check (spresniť sanity band).
4. **DEK + cenikyremesel** (už používame) → scrapers/ rozšíriť na kvartálny refresh
   cihly.json s verziou/dátumom/zdrojom pri každej cene.
5. **Vlastné referenčné rozpočty = zlatý štandard:** pre 3–5 pôdorysov ručne zostaviť
   výkaz výmer v NAŠOM rozsahu (materiál+práca) s cenami z 1–4. + Ytong ponuka
   (materiálová referencia). Bez tohto sa ±10 % nedá MERAŤ.

---

## D. TESTOVANIE & KALIBRÁCIA

**D1. Ground truth — 2 úrovne:**
- L1 VÝMERY: 10–15 pôdorysov ručne zmerať: obvod, hrúbky, nosné, priečky, otvory
  SO ŠÍRKAMI, plochy → ground_truth/*.json (draft pripraví AI, ČLOVEK overí — inak kruh)
- L2 CENA: referenčné rozpočty (C5) + Ytong ponuka + NEN výkazy.

**D2. eval.py** (rozšírenie batch_test.py):
- MAPE per pole proti L1, end-to-end odchýlka ceny proti L2
- variance: 5 behov/pôdorys → std dev
- história behov → trend medzi verziami promptu/cien

**D3. Error budget** (kam investovať):
obvod ≤2 % · hrúbky ≤5 % · priečky ≤15 % · otvory ≤20 % · ceny materiálu ≤5 % ·
práca ≤8 % → kvadratúra ≈ 7–8 % total, rezerva na región.

**D4. Akceptácia:** cena ±10 % od referencie na ≥80 % test setu, variance <3 %.

**D4b. Politika quality gate (potvrdené Robertom 2026-07-06):**
- REFUSE VÝHRADNE keď vstup NIE JE pôdorys RD (foto, okenársky detail, cenová ponuka,
  byt, situácia...) — s jasnou správou prečo.
- Horší pôdorys sa NIKDY neodmieta: amatérsky room-planner, nekonzistentné kóty,
  chýbajúce hrúbky → spočítať z toho, čo je, rozšíriť ±band a POVEDAŤ používateľovi,
  čo presnosť znížilo (napr. „kóty si nesedia, počítam z celkových rozmerov").
- Test set má preto 3 kategórie:
  1. POZITÍVNE (plnohodnotný pôdorys) → presnosť proti GT
  2. DEGRADOVANÉ (horšia kvalita, napr. plan_49681853) → NESMIE byť REFUSE,
     výsledok so širším bandom; meria sa, či band poctivo pokrýva realitu
  3. NEGATÍVNE (ne-pôdorysy, 7 ks v test_podorysy) → MUSÍ byť REFUSE
  eval.py rozšíriť o kategórie 2 a 3 (gate správnosť), nie len MAPE.

**D5. Kalibračná krivka confidence:** z eval dát premapovať Gemini confidence na
empirickú neistotu („conf 80 = reálne ±12 %") → poctivý ±band.

**D6. Feedback loop v produkcii:** pri lead capture „Máte už ponuku? Od stavebnín
alebo od firmy? Suma?" — rozlíšiť typ ponuky (materiál vs. na kľúč), inak kalibráciu
pokazíme miešaním jabĺk s hruškami.

---

## E. FÁZY

**FÁZA 0 — Merací základ (NEPRESKOČITEĽNÁ)**
ground truth L1 (10–15 pôdorysov) + eval.py + baseline report súčasného stavu

**FÁZA 1 — Extraction:** itemizovaná schéma + response_schema + self-consistency 3×
paralelne + polygon check + per-field confidence + podmienené passy (B5)
Cieľ: obvod <2 %, hrúbky <5 %, otvory <15 %, priečky <15 %, variance <3 %

**FÁZA 2 — Opravy logiky:** A1–A6 (každá samostatne, overená proti GT)
Cieľ: výkaz výmer položkovo sedí s referenčným rozpočtom v našom rozsahu

**FÁZA 3 — Cenová kalibrácia:** NEN + výrobcovia + RTS + referenčné rozpočty +
scraper refresh + UI: dva medzisúčty + veta o rozsahu
Cieľ: ±10 % na ≥80 % test setu ✅

**FÁZA 4 — Hardening & produkcia:** regresné behy pri každej zmene, rate-limit,
lead capture s feedback otázkou (D6), PDF export výkazu ako lead magnet

**FÁZA 5 (neskôr):** základy + stropy → hrubá stavba, ambícia ±5 %

---

## PRINCÍPY
1. Merať skôr než meniť — Fáza 0 najprv.
2. Žiadna kompenzácia chýb — nálezy A1–A6 fixovať a overiť samostatne.
3. LLM číta, Python počíta.
4. Každá zmena promptu = regresný beh.
5. Ceny sú dáta, nie kód — cihly.json verziovať, zdroj pri každej cene.
6. Rozsah je svätý: materiál + práca. Čo tam nie je, povie UI jednou vetou.
