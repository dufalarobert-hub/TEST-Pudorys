# Test 4 — verifikácia Fable čítania vs. reálna PD (2026-07-09)

Dom = **cvut_hanspaulka_RD.pdf** (ČVUT FA, Michaela Hablová, LS 2016/17, „Rodinný dům
s architektonickou kanceláří, Praha-Hanspaulka"). Fable čítal 4 pôdorysy BEZ prístupu k PD
(test4_citanie_kompletne.md); tu porovnanie s technickou správou (str. 13, 20) a tabuľkami
(str. 41–43, 48).

## Súhrnné parametre

| Parameter | Fable z pôdorysov | PD (ground truth) | Odchýlka |
|---|---|---|---|
| Úžitná plocha | 285,8 m² | **294,18 m²** | **−2,8 %** ✓ |
| — z toho obytná časť (1.NP–3.NP) | 215,1 m² | 211,99 m² | **+1,5 %** ✓✓ |
| — z toho kancelária (1.PP) | 70,7 m² | 82,19 m² | −14 % ✗ |
| Zastavaná plocha | 160–170 m² [V] | 177,19 m² | −4…−10 % |
| Obostavaný priestor | 1 100–1 200 m³ [V] | **822,57 m³** | **+34…+46 % ✗✗** |
| Konštrukčná výška podlažia | 2,92 m | 2 920 mm | **presne** ✓ |

## Konštrukcie — všetko trafené

| Konštrukcia | Fable | PD | Verdikt |
|---|---|---|---|
| Obvod nadzemné | 375 mm, jednovrstvové, bez ETICS | **Ytong Lambda 375**, omietky 5+15 (OS2) | ✓✓ vrátane „bez zateplenia" |
| Vnútorné nosné | 250 mm | Ytong Standard 250 | ✓ |
| Priečky | 100/150 (priemer 125) | příčkovky Ytong 100/150 | ✓ |
| 1.PP steny | betón 250 + izolácia 125 [V] | **ŽB monolit 250 + XPS 120** (OS1) | ✓✓ (tip na betón správny) |
| Stužujúci veniec | — | ŽB veniec 250×420 | (pricing ho počíta ✓) |
| Stropy | — | ŽB doska 180/200 | nečitateľné z pôdorysu |
| Materiál | „legenda nie je" → None | Ytong (Lambda/Standard) | správne priznaná neznalosť |

## Schodiská — 100 % zásah

PD: 1.PP→1.NPs **10** stupňov · 1.NPs→1.NP **8** · 1.NP→2.NP **16** · 2.NP→3.NP **16**,
všetko 265×182,5, sklon 34,55°. Fable z kót odvodil identicky (16×182,5 = 2 920 ✓,
8×182,5 = 1 460 ✓, 10×182,5 = 1 825 ✓). Deterministická výška zo schodiska funguje.

## Otvory — tabuľka okien/dverí (str. 42–43)

| Prvok | Fable | PD | Verdikt |
|---|---|---|---|
| O1 | 1500×850, parapet 1550 | 1500×785 (3×: 1NP/2NP/3NP) | šírka ✓, výška −8 % |
| O2 | 800×850 | 800×785 (4×: každé podlažie) | ✓ (1 ks mi ušiel — mal som 3×) |
| O3 garáž. pás + 2.06 | 4500×1650, oba identifikované | **4500×1585, 2 ks** (1PP+2NP) | ✓✓ |
| O4 | 2 okná: 3,0 + 2,4 m ✗ | **rohové 12-dielne 6000×1125×1585** (2NP) | šírka 2.04 = 3000? nie — je to JEDNO okno cez roh 2.04/2.05; Σ dĺžky 5,4 vs 7,125 m |
| O5 (3NP juh) | 1500, tip „francúzske so Z8" ✓ | 1500×2435 francúzske | šírka ✓, výška ✗ (1,65 vs 2,435) |
| O6 | „2.04 ~3000 ODHAD" | 3000×1585 (2NP) | **šírka presne** ✓ |
| O7 | — (nevidel som) | 1500×2435 (2NP) | chýba |
| F1 portál 1.06 | 6050×3460 (kóty) | Schüco FW 50, ~5,87–6,7 × 3,38 m | ~✓ (±5 %) |
| D1 700/1970 | 7× | 8× (1NP má 4) | −1 |
| D2 900/1970 | 2× | 2× | ✓ |
| D3 vstup | 900×2100 | rám 1600×2400, krídlo 900×2320 + fix 550 | šírka ✓, zostava podcenená |
| D4 (v portáli) | 725×1970 | 725×2320 (rám 825×2400) | šírka presne ✓, výška ✗ |
| D5 800/1970 | 6× (1PP 2, 2NP 3, 3NP 1) | **6× (1PP 2, 2NP 3, 3NP 1)** | ✓✓ presné rozmiestnenie |
| D6 vstup 1PP | 900/2025 | rám 1080×2150, krídlo 900×2320 | ✓ |
| D7 | 700/1970 (1.09) | 700/1970 požiarne, 1NP | ✓ (je to dvere do garáže) |
| D8 | 800 | posuvné 2×550 (zárubňa 1200) | ✗ |
| Σ okná / dvere | 14 / 20 | 13+F1 / 21 | ~✓ |

## Hlavné omyly interpretácie (nie kót)

1. **1.04 je GARÁŽ** (temperovaná, s.v. 2,56, konzola 2.NP nad vjazdom, preklad OV1 5250 =
   nadpražie vjazdu) — Fable: „izba s výstupom na terasu". Preto aj hs_portal 3,6 m
   v 1.04 je v skutočnosti **vjazd do garáže** (vráta v tabuľke ostatných výrobkov).
   → `ma_garaz` malo byť na 1.NP a `ma_garazova_vrata=True`.
2. **1.PP nie je pivnica, ale architektonická kancelária** (jednacia miestnosť 0.03,
   pracovňa, sklad, hygiena; samostatný vstup vonkajším schodiskom). Funkčne vedľajšie,
   na zdivo bez vplyvu.
3. **Obostavaný priestor +37 %** — hrubý odhad z „footprint × výška" ignoroval, že hmota
   je 3 do seba vklinené kvádre a 1.PP je menšie než footprint.
4. **O4 rohové okno** — extract.py prompt na rohové okná pamätá („sčítať ramená cez roh"),
   ale Fable pri ručnom čítaní roh nespojil → 2 samostatné okná a −1,7 m šírky.
5. Výšky francúzskych okien (O5/O7 2435, D4 2320) — z pôdorysu principiálne neviditeľné,
   paušál/parapetový dopočet ich podcenil.
6. Sklon terénu: PD ~5 % (Fable z terénnych šráf odhadoval strmší svah — kozmetické).

## Dôsledok pre rozpočet

Variant B (bez 1.PP; suterén ŽB potvrdený) zostáva správny rámec zdiva nadzemných podlaží.
Po oprave: garáž s vrátami v 1.NP (preklad brány +18k, odpočet vrát) a O4/O5/O7 väčšie
odpočty — čistý efekt na cenu ~±2 %, vnútri pásma ±21 %. Trieda materiálu: Ytong **Lambda**
(obvod) je vyšší štandard než „stredne" default — cena obvodového zdiva reálne vyššia.

## Poznatky do kalkulačky

- Pôdorysy tohto typu (FA práce) NEMAJÚ tabuľku miestností ani legendu materiálov na
  výkrese — materiál je len v technickej správe/tabuľke skladieb → PD deep-mining nutný.
- Garáž v obytnom podlaží: indície = znížená s.v. + mohutný preklad (OV) + prerušovaná
  čiara konzoly nad vjazdom; zvážiť do extract promptu.
- Obostavaný priestor z jedného podlažia neodhadovať (chyba ±40 %); počítať len ako
  Σ(zastavaná podlažia × konštr. výška), keď sú k dispozícii všetky podlažia.
- Konvencia kót otvorov „šírka nad / výška(parapet) pod" potvrdená — výšky okien 785/1585
  vs čítané 850/1650: kóty na pôdoryse boli stavebné otvory, tabuľka rámové rozmery.
