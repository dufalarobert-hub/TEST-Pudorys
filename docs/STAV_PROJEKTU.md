# 📌 STAV PROJEKTU — Kalkulačka rozpočtu (archív 2026-07-07)

## ⚡ UPDATE 2026-07-09/10 — Fable testy 4+5 s verifikáciou proti reálnej PD

Prvé dva testy s úplnou ground truth (čítanie naslepo → porovnanie s PD):
**test 4** = cvut_hanspaulka_RD.pdf (realizačný projekt s kótami, 4 podlažia, svah,
split-level) · **test 5** = cvut_romanov_RD.pdf (štúdia BEZ vnútorných kót, 24×7,5 m,
podkrovie). Súbory: `fable_testy/test4_*.py/md`, `test5_*.py/md` (čítanie + verifikácia).

**Výsledky presnosti:**
- Z kót (test 4): úžitná −2,8 %, obytná časť +1,5 %, hrúbky stien/materiálová skladba
  všetko ✓, schodiská 100 % (4 ramená presne), šírky otvorov z kót presné.
- Z mierky bez kót (test 5): 1.NP +0,9 %(!), úžitná celkom +6 %, podkrovie +13–20 % ✗.
- Chyby sú takmer výhradne INTERPRETAČNÉ, nie meracie: funkcia miestnosti (garáž
  v 1.NP so zníženou s.v. čítaná ako izba; kancelária v 1.PP ako pivnica), skladba
  steny (Porotherm T Profi 500 jednovrstvové vs tip „300+200 zateplenie"),
  šikminy podkrovia, obostavaný priestor z footprintu (+37 % — NEODHADOVAŤ bez rezu).

**Zistenia → TODO do extract.py promptu (zatiaľ NEimplementované):**
1. Detektor garáže v obytnom podlaží: znížená s.v. + mohutný preklad (OV bublina) +
   čiarkovaná konzola nad vjazdom; garáž NIE JE len „uzavretá vedľajšia miestnosť".
2. Podkrovie + sedlová strecha bez rezu → redukovať úžitnú ~×0,85 + warning (test 5:
   systematických +15 %).
3. Obostavaný priestor NEpočítať z footprint×výška (±40 %); len Σ(zastavaná×konštr. výška).
4. Rohové okná: pravidlo v prompte je, ale aj Fable ho pri čítaní nepoužil (O4 Hanspaulka
   6000×1125 čítané ako 2 okná) — zvýrazniť/dať príklad.
5. Kótovacia konvencia otvorov „šírka NAD kótou, výška(parapet) POD" — overená na 2 PD;
   krížový check: parapet+výška = s.v. alebo jednotná hlava (2400). Pridať do promptu.
6. Výšky francúzskych okien/dverí z pôdorysu nevidno — paušál ich podceňuje ~30 %
   (2435 vs 1650); pri type francouzske_okno/portál brať výšku ≈ s.v. − 0,2 m.
7. Jednovrstvové 500 vs zateplené 300+200 bez šráf nerozoznateľné → nechať UI voľbu
   skladby, ale defaultovať na jednovrstvové pri hrúbke 440–500 (už čiastočne v prompte).
8. Numeráciu miestností nebrať ako identitu — porovnávať/agregovať podľa FUNKCIE
   (labely bývajú posunuté/nejednoznačné).

**Poznatok k _aggregate_floors (drobný bug-kandidát):** `ma_zateplenie = any(...)` —
perimetrická izolácia SUTERÉNU „presiakne" na celý dom a zmení label skladby na
575 mm vč. zateplenia (cena zdiva OK, label mätúci). Zvážiť: zateplenie brať z base
nadzemného podlažia.

**Poznatok ku gate:** štúdie bez kót korektne REFUSne (test 5). Ručný test ale ukázal,
že degradovaný režim (len celkové kóty + mierka → úžitná ±6 %, pásmo ±30 %) by mal
pre lead-capture zmysel — kandidát na feature.

## ⚡ UPDATE 2026-07-07 popoludní — Fable čítacie testy + implementované zistenia

3 manuálne testy čítania pôdorysov Fable modelom (Křepelková RD, Dobřejovice, Počaply)
vs. reálne PD → zistenia implementované (NEcommitnuté, over a commitni):

- **app.py `_aggregate_floors`**: itemizované otvory sa teraz zbierajú zo VŠETKÝCH
  podlaží (predtým len z base podlažia → okná 2.NP sa neodpočítavali) + agregácia
  `ma_garazova_vrata` a `pricky_material`.
- **pricing.py**: (a) preklad garážovej brány + odpočet vrát 10,5 m² viazané na NOVÉ
  pole `ma_garazova_vrata` (technická miestnosť/kolna bez vrát už nedostane +18 tis.;
  None = fallback na ma_garaz = spätná kompatibilita); (b) `_plocha_otvorov` používa
  `vyska_m` otvoru z kót, keď existuje (paušál 1,5 m podceňoval celopresklené domy
  ~30 %); (c) varianta „plné murivo" berie `stena_celkova_mm` z kóty (450→440+omietka,
  nie blok+200); (d) SDK priečky (`pricky_material="sdk"`) = 0 Kč zdiva + warning.
- **extract.py**: prompt rozšírený o rohové okná (sčítať ramená cez roh), voidy/galérie
  (nie sú podlahová plocha), SDK priečky, jednovrstvové bloky 440-500 bez zateplenia,
  kótu schodiska; nové polia `stena_celkova_mm`, `pricky_material`, `ma_garazova_vrata`,
  `schodiste_stupne`, `schodiste_vyska_stupne_mm`, `otvory[].vyska_m`. `_normalize`
  DETERMINISTICKY odvodzuje výšku podlažia zo schodiska (stupne × výška stupňa;
  pri konflikte s úrovňovou kótou > 0,15 m vyhráva schodisko — dom 1: kóta +2,800
  vs reálnych 2,99 m) → `_vyska_zdroj`.
- Overené offline: pricing smoke ✓, 5 cielených testov nového správania ✓, spätná
  kompatibilita ✓ (starý vstup = identická cena 681 210). Dom 1 simulácia: odchýlka
  vs GT parametre +4,4 % → **−3,3 %** (a už bez kompenzujúcich sa chýb).
- ⚠️ NEBEŽALO (metrované API): `gate_test_refuse.py` (8 Gemini volaní) a regresný
  `eval.py --all` — zmena promptu = POVINNÝ regresný beh pred nasadením!
- Frontend: nové polia (vrata, SDK priečky, výška zo schodiska) zatiaľ NEMAJÚ UI
  prepínače — warnings na ne odkazujú („zapněte níže"), treba doplniť do templates.

> Práca pozastavená 2026-07-07 po veľkom refaktore. Tento súbor = návod na návrat.
> Kontext: PLAN_PRESNOST.md (plán ±10 %) · ZNALOSTI_ROZPOCTAR.md (konštanty+citácie)
> · ground_truth/README.md (merací etalón) · eval_history/ (baseline).

## Kde sme skončili (commit 5dbea1d + gate_test_refuse.py)

**2026-07-13: PUSHNUTÉ na main (e7800f1..377b015) a nasadené na Vercel** — Robert
rozhodol pushnúť BEZ regresného evalu (beh bol prerušený). ⚠️ Regresný `eval.py --all`
+ `gate_test_refuse.py` teda STÁLE dlhujeme — čísla novej verzie nie sú overené proti
baseline; spustiť pri najbližšej príležitosti (~24 volaní, ~4-5 Kč).

**Hotové:**
- Model-agnostická architektúra: `providers.py`, `EXTRACTOR_PROVIDER=gemini|anthropic`
  (Fable pripravený — tool-use schéma; budúcnosť = Fable API extractor)
- ÚRS metodika: murivo netto (−veniec 0.25 m), práca priečok 283+0.90×mm,
  garážový preklad 18k + odpočet vrát; itemizované otvory → preklady podľa rozponu
- Bbox polygon check (worst outlier 44→57.9 m = presne GT), PD deep-mining
  (rez+výpis otvorov+2.NP), duplikát-detektor podlaží, self-consistency (`EXTRACT_RUNS`)
- Komentár rozpočtára (komentar.py, Haiku, graceful) + karta v UI
- Robustný JSON parser + retry; gate test 8/8 (`python3 gate_test_refuse.py` cez PYTHONPATH=.)
- eval.py harness; baseline PRED zmenami: obvod MAPE 6.5 %, úžitná 0 %,
  slabiny nosné/priečky 164 % a okná 59 % (eval_history/eval_20260706_174916.json)

## ⚠️ Známe nedostatky (priznané, neopravené)

1. **Zmeny po baseline NEZMERANÉ** — re-eval nebežal; zhoda s Ytong ponukou vedome
   rozbitá (odstránené kompenzujúce sa chyby) a nová presnosť nepotvrdená
2. Nosné vs. priečky klasifikácia 164 % MAPE (najhoršie číslo, nedotknuté)
3. Ceny materiálu: MOC vs. reálne zľavy nedoriešené; NEN mining nespravený
4. Frontend zmeny (komentár karta, PD 2.NP flow) NEotestované v prehliadači
   (pravidlo projektu: puppeteer test po každej frontend zmene!)
5. Self-consistency default vypnutá; celková latencia PD flow vs Vercel 60 s nemeraná
6. claude_review nevie o itemizovaných otvoroch; README tabuľka súborov mierne neaktuálna

## ▶️ AKO POKRAČOVAŤ (presné poradie)

1. **Browser test** — `python3 app.py` → :5005, puppeteer/ručne preklikať:
   upload pôdorysu, komentár karta, PD s 2.NP (1–2 Gemini volania)
2. **Robert overí GT drafty** — ground_truth/README.md checklist, prepnúť verified=true
3. **Re-eval po zmenách** — `python3 eval.py --all --label "po refaktore"` (9 volaní ~2 Kč)
   → porovnať s baseline v eval_history/
4. **A/B Fable** — kľúč: `ANTHROPIC_ENV_FILE="$HOME/Desktop/Influencer Report Generator/app/.env.local"`
   + `EXTRACTOR_PROVIDER=anthropic python3 eval.py --all --label "Fable A/B"` (9 volaní ~25–35 Kč)
5. **Rozhodnúť push→Vercel** (main = produkčný deploy)
6. Potom: rate-limit (NUTNÉ pred Meta Ads), lead capture cez Ecomail + feedback
   otázka „máte už ponuku? materiál/komplet?", PDF export, NEN kalibrácia

## Pravidlá (Robert)

- API volania hlásiť VOPRED (metrované API vadí, subscription tokeny nie)
- Konštanty LEN z primárnych zdrojov (ÚRS/výrobcovia/cenníky), žiadne študentské práce
- Žiadna kompenzácia chýb; LLM číta, Python počíta; zmena promptu = regresný beh
- Rozsah = materiál+práca zdiva (bez lešenia/réžie), bez DPH
