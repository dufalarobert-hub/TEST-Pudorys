# Fable čítacie testy — pôdorys vs. realita (2026-07-07)

Manuálne testy: Fable model číta pôdorysy (bez PD), potom sa porovná s reálnou
projektovou dokumentáciou. Cieľ = zistiť, kde Fable ako extractor trafí a kde nie,
a odvodiť vylepšenia kalkulačky. **Žiadne API volania** — Fable číta z chatu
(subscription), výpočet beží lokálne cez `pricing.py` (rovnaká cesta ako web-app
multi-fóto flow: extrakcia → `app._aggregate_floors` → `reconcile.quality_gate` →
`pricing.calculate`).

Bežateľné simulácie: `test1_marianske_lazne.py`, `test2_dobrejovice.py`,
`test3_pocaply.py` (spúšťať z rootu repa: `python3 fable_testy/testX.py`).
Zdrojové PD: `test_projekty/cvut_krepelkova_RD.pdf`, `cvut_dobrejovice2024_komplet.pdf`,
`fgv_komplet_dokumentace.pdf`.

---

## Test 1 — RD Mariánské Lázně (Křepelková) · 2 podlažia + sklad

| Parameter | Fable z pôdorysov | Realita (PD) | Odchýlka |
|---|---|---|---|
| Rozmery domu | 8,0 × 11,5 m | 8,0 × 11,5 m | ✅ 0 % |
| Obvod stien spolu | 91,9 m | ~91,7 m | ✅ +0,2 % |
| Zastavaná plocha | 104 m² | ~104 m² | ✅ 0 % |
| Úžitná plocha | 146,2 m² | 142,2 m² | ✅ +2,8 % |
| Hrúbka obvod. muriva | 300 mm + zateplenie | Porotherm 30 Profi + EPS | ✅ |
| Cenová trieda (auto) | stredné | Porotherm Profi = stredné | ✅ |
| Steny skladu | 210 mm | 190 mm (PTH 19) | ~✅ |
| Výška podlažia | 2,80 m | 2,99 m | ❌ −6,4 % |
| Počet okien | 13 | 11 | ❌ +2 (HS portál ako 3 ks) |
| Plocha okenných otvorov | ~30 m² | ~57 m² | ❌ −47 % |
| Počet dverí | 9 | 9 | ✅ 0 % |
| Priečky | murované 150 | **SDK** 150 | ❌ zlý materiál |
| **Cena zdiva** | **681 210 Kč** | 652 745 Kč (GT vstupy) | **+4,4 %** |

Hlavné chyby: SDK priečky brané ako murivo (~68 tis. navyše), výška 2,8 vs 2,99,
podcenené šírky okien (HS portál + rohové), `ma_garaz` pre sklad → falošný preklad brány.

---

## Test 2 — RD Dobřejovice (Kyrylyč) · 2 podlažia, ploché strechy, L-tvar

| Parameter | Fable z pôdorysov | Realita (PD) | Odchýlka |
|---|---|---|---|
| Rozmery 1.NP | 10,0 × 19,5 m | 10 020 × 19 460 | ✅ 0 % |
| Obvod 1.NP | ~59,0 m | ~59,0 m | ✅ 0 % |
| Obvod 2.NP | ~55,1 m | ~55,6 m | ✅ +1 % |
| Murivo | 300 mm + zateplenie | Porotherm 30 Profi P15 + EPS | ✅ |
| Priečky | murované 120 | Porotherm AKU 115 | ✅ |
| Vnútorné nosné | 240 mm | PTH 30 (300) + PTH 24 | ⚠️ čiastočne |
| Výška podlažia | 3,35 m (19×176) | +3,350 | ✅ 0 % |
| Kryté státie + terasa | vylúčené (bez stien) | carport + terasa | ✅ |
| Úžitná plocha | 222,3 m² | 252,9 m² | ❌ −12 % |
| Počet okien | 17 | 20 | ⚠️ −3 ks (rohové) |
| Súčet šírok okien | 33,6 m | 41,0 m | ❌ −18 % |
| Počet dverí | 12 | 13 | ✅ −1 |
| D2 interiérové | 10 ks | 10 ks | ✅ 0 % |

Hlavné chyby: rohové presklenia (šírka pokračuje cez roh — O06/O08/O10),
void galéria nad jedálňou započítaná do plochy 2.NP, ložnica 1.05 so šatňou 29,6 m².
Výška podlažia zo schodiska trafená presne (poučenie z testu 1).

---

## Test 3 — bungalov Počaply nad Loučnou (Řehák) · 1 podlažie

| Parameter | Fable z pôdorysu | Realita (PD) | Odchýlka |
|---|---|---|---|
| Rozmery domu | 8,4 × 13,15 m | 8,4 × 13,15 m | ✅ 0 % |
| Zastavaná plocha | 110,5 m² | 110,5 m² | ✅ 0 % |
| Úžitná plocha | ~89 m² | 86,42 m² | ✅ +3 % |
| Obvod stien | 43,1 m | 43,1 m | ✅ 0 % |
| Počet podlaží | 1 | 1 | ✅ |
| Počet miestností | 10 | 10 (vr. duplicitného č. 103) | ✅ |
| Obvodové murivo | 450 → „300 + 150 zateplenie" | **440 jednovrstvové (PTH 44 EKO), bez zateplenia** | ❌ |
| Cenová trieda | stredné | drahé (tepelnoizolačný blok) | ❌ |
| Vnútorné nosné | 175 mm | 175 mm (PTH 17,5) | ✅ 0 mm |
| Priečky | 125 murované | 125 murované (PTH 11,5) | ✅ 0 mm |
| Okná sever/západ | 1500, parapet 850 | 1500×1000, parapet 850 | ✅ |
| Vchodové dvere | ~1000 | 1000 × 2350 | ✅ |
| Kotol/komín | turbo 80/125 + krb Schiedel | turbo 80/125 + krb, komín | ✅ |

Jediná vážna chyba: skladba steny 440 mm — jednovrstvový blok interpretovaný ako
murivo+zateplenie (posun triedy stredné→drahé). Z pôdorysu bez legendy sa to objektívne
rozhodnúť nedá — správne = ponúknuť obe varianty (appka má prepínač).

---

## Spoločný vzorec (3 testy)

**Kóty a geometriu Fable číta takmer bezchybne** (obvody 0–1 %, plochy ±3 %, počty
dverí presne). **Systematické riziká sú interpretačné:**

1. Výška podlažia — z pôdorysu len nepriamo (schodisko / úrovňová kóta), autoritatívny je rez
2. Rohové presklenia — šírka pokračuje cez roh budovy
3. Voidy / galérie — otvorený priestor do patra nie je podlahová plocha
4. SDK vs. murované priečky — tenká nešrafovaná stena
5. Jednovrstvový blok vs. murivo+zateplenie — hrubá stena 440–500 je nejednoznačná

## Implementované zistenia (2026-07-07, viď STAV_PROJEKTU.md sekcia UPDATE)

- `app._aggregate_floors`: otvory zo VŠETKÝCH podlaží + agregácia nových polí
- `pricing.py`: `ma_garazova_vrata` (kolna bez vrát ≠ +18k), `otvory[].vyska_m`,
  `stena_celkova_mm` (varianta plné = 450), `pricky_material=sdk` (0 Kč zdiva)
- `extract.py`: prompt (rohové okná, voidy, SDK, jednovrstvový blok, kóta schodiska) +
  nové polia; `_normalize` odvodí výšku podlažia zo schodiska (bije úrovňovú kótu pri konflikte)
- Dom 1 po fixoch: +4,4 % → **−3,3 %** (bez kompenzujúcich sa chýb)

⚠️ NEBEŽALO (metrované API): `gate_test_refuse.py` + `eval.py --all` — regresný beh pred nasadením!
