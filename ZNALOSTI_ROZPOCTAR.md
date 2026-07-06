# 📚 ZNALOSTI ROZPOČTÁRA — overené konštanty a pravidlá (2026-07-06)

> Zdroje: LEN primárne — ÚRS katalóg 801-1 (cs-urs.cz), technické listy a cenník
> Wienerberger, DEK, cenikyremesel.cz, ČKAIT TS 01. Žiadne študentské práce.
> Istota: ✅✅ = potvrdené 2+ zdrojmi · ✅ = 1 primárny zdroj (technický list/oficiálna
> metodika) · ⚠️ = 1 zdroj, overiť pred použitím ako konštanta.

---

## 1. PRAVIDLÁ VÝKAZU VÝMER (ÚRS 801-1) — metodika merania

| Pravidlo | Istota | Zdroj |
|---|---|---|
| Murivo sa vykazuje v **m³** objemu (alt. m² pri danej hrúbke) | ✅ | [ÚRS 801-1 2020/I](https://www.cs-urs.cz/podminky/cu201/801-1-Budovy-a-haly---zdene-a-monoliticke-(2020-I)/25/) |
| Odpočítavajú sa **všetky kótované otvory** (okná, dvere) — pravidlo 0,25 m² sa na stránke NENAŠLO | ✅ | tamtiež |
| Od muriva sa odpočítava aj objem **prekladov a ŽB vencov** → murivo je NETTO, veniec + preklady sú samostatné položky | ✅ | tamtiež |
| Priečky sa merajú v **m²**, otvory sa odpočítavajú z kótovaných rozmerov | ✅ | tamtiež |

**→ DOPAD NA APPKU (potvrdenie nálezu A1):** pricing.py dnes počíta obvodové murivo
na plnú výšku podlažia (2.8 m) A veniec zvlášť = dvojpočet výšky venca (~0.25 m).
Podľa ÚRS: murivo = (výška podlažia − výška venca − výška prekladov v páse otvorov),
veniec a preklady zvlášť. FIX: výška muriva ≈ konštrukčná − 0.25 (veniec+strop-časť).

## 2. VÝŠKY (ČKAIT TS 01, ČSN 73 4301)

| Hodnota | Číslo | Istota | Zdroj |
|---|---|---|---|
| Min. svetlá výška obytnej miestnosti RD | 2 500 mm | ✅ | [ČKAIT TS 01](https://profesis.ckait.cz/dokumenty-ckait/ts-01/) (ČSN 73 4301 čl. 5.2.2.9) |
| Definícia: konštrukčná výška = svetlá + strop + skladba podlahy | — | ✅ | tamtiež |
| Typická svetlá výška nových RD | 2 600–2 700 mm | ⚠️ prax | doplniť z rezov v test_projekty |

**→ APPKA:** default `vyska_podlazia_m: 2.8` je rozumný pre KONŠTRUKČNÚ výšku prízemia
bungalovu, ale murivo treba počítať na murovaciu výšku (≈ konštrukčná − veniec/strop).
Keď je v dokumentácii REZ → čítať skutočné výšky.

## 3. SPOTREBY MATERIÁLU (technické listy výrobcov)

| Materiál | Spotreba | Istota | Zdroj |
|---|---|---|---|
| Porotherm modul 25 cm (Profi/EKO/T, hr. 30–50) | **16 ks/m²** (44: 36,4 ks/m³) | ✅✅ (Wienerberger TL + cenník + DEK; Heluz Family 44 tiež 16 ks/m²) | [TL 44 Profi](https://www.wienerberger.cz/content/dam/wienerberger/czech-republic/marketing/documents-magazines/technical/technical-product-info-sheet/wall/CZ_POR_TEC_Pth_44_Profi.pdf), [DEK](https://www.dek.cz/deksmart/zdici-systemy) |
| Porotherm formát 24 (dĺžka 37,2 cm) | 10,7 ks/m² | ✅ | cenník Wienerberger |
| Priečkovky 11,5 / 14 Profi (dĺžka 49,7) | 8 ks/m² | ✅ | cenník Wienerberger |
| Malta tenké škáry, brúsené (44 Profi) | 3,1 l/m² · 7 l/m³ | ✅ | TL 44 Profi |
| Zakladacia malta (30 S Profi) | 6,0 l/bm | ✅ | TL 30 S Profi |
| **Smerná prácnosť** murovania 440 mm | 0,98 h/m² · 2,23 h/m³ | ✅ | TL 44 Profi |
| Ztratné/prořez | — nenájdené v primárnych zdrojoch | ❓ | doplniť (bežná prax ~5 %, NEPOUŽIŤ bez overenia) |

## 4. PREKLADY — pravidlá + cenová krivka (kľúč pre nález A3!)

**Technické pravidlá (Wienerberger TL KP 7):** ✅
- KP 7: prierez 70×238 mm, dĺžky 1000–3500 mm po 250 mm
- Uloženie: do 1750 mm dĺžky → 125 mm · 2000–2250 → 200 mm · ≥2500 → 250 mm
- **Dĺžka prekladu = svetlosť + 2× uloženie** (1000 mm kryje svetlosť 750 mm)
- Počet kusov: 1–4 podľa hrúbky steny (à 70 mm; obvod. stena s izolantom)

**Cenová krivka KP 7 (DEK, s DPH/ks):** ✅ [dek.cz](https://www.dek.cz/produkty/vypis/44358-preklad-kp-7)
| Dĺžka mm | 1000 | 1250 | 1500 | 1750 | 2000 | 2250 | 2500 | 3000 | 3500 |
|---|---|---|---|---|---|---|---|---|---|
| Kč/ks | 303 | 411 | 485 | 622 | 808 | 922 | 1169 | 1330 | 1580 |

(Cenník Wienerberger bez DPH: 100 cm = 544, 350 cm = 2 838 — MOC vyššia než DEK akcia.)

**Veľké rozpony:** KP 7 končí na 3500 mm. Garáž/HS portál → **Porotherm KP XL**
(svetlosť do 500 cm): napr. dĺžka 550 cm = **23 146 Kč/ks bez DPH** ✅ (cenník).

**→ APPKA — náhrada paušálu 2200 Kč/otvor:**
preklad_cena(šírka_otvoru, hrúbka_steny) =
  ks_podľa_hrúbky(napr. 440 mm obvod ≈ 4× KP7 + izolant; 240 nosná ≈ 3×; 300 ≈ 4×)
  × cena_z_krivky(svetlosť + 2×uloženie) + práca/osadenie.
Príklady: okno 1,0 m v 440 mm ≈ 4×485 ≈ 1 940 Kč mat.; dvere 0,8 m priečka = plochý
preklad ~200–400 Kč; garáž 4–5 m = KP XL ~15–23 tis. (dnes paušál 2 200 = pre garáž 10× podcenené!)

## 5. VENIEC (komponenty)

| Položka | Číslo | Istota | Zdroj |
|---|---|---|---|
| Věncovka VT 8 Profi | 2 ks/bm; 97–144 Kč/ks → 194–288 Kč/bm | ✅ | cenník Wienerberger |
| Betón + výstuž + izolácia + práca | — nevyzbierané | ❓ | doplniť (dnešných 1200 Kč/bm zatiaľ ponechať) |

## 6. CENY MURIVA 2026 (cenník Wienerberger, bez DPH, VRÁTANE pojiva, Kč/m²)

| Trieda | Produkt | Kč/m² | Kč/m³ (prepočet) |
|---|---|---|---|
| Tepelnoizolačná („drahe") | 44 T Profi | 4 703 | ~10 700 ⚠️MOC |
| | 38 T Profi | 4 072 | ~10 700 |
| Stredná | 44 EKO Profi | 3 375 | ~7 670 |
| | 38 EKO Profi | 3 015 | ~7 930 |
| Základná („lacne") | 44 Profi | 2 741 | ~6 230 |
| | 38 Profi P10 | 2 266 | ~5 963 |
| Vnútorné nosné | 30 Profi | 1 850 | ~6 170 |
| | 24 Profi | 1 593 | ~6 640 |
| Priečky | 14 Profi | 1 023 | ~7 310 |
| | 11,5 Profi | 888 | ~7 720 |

**⚠️ KRITICKÉ ZISTENIE:** cenníkové (MOC) ceny prepočítané na m³ sú ~6 000–10 700 Kč/m³,
ale cihly.json má 3 600–4 800 Kč/m³. Rozdiel = reálne trhové zľavy 30–50 % z MOC
(bežná prax stavebnín) — cihly.json kalibrovaný na „DEK −20 %" je teda v realistickom
pásme, ALE treba to overiť proti reálnym nákupným cenám (akcie DEK, ponuky stavebnín).
NEPREPISOVAŤ cihly.json na MOC ceny! Použiť MOC ako horný strop + zľavový koeficient.

## 7. MURÁRSKE PRÁCE 2025/26 (cenikyremesel.cz, len práca, Kč/m²)

| Konštrukcia | Kč/m² | Náš vzorec (215+1,10×mm) | Zhoda |
|---|---|---|---|
| Obvod 380 mm | 631 | 633 | ✅✅ PRESNÁ |
| Obvod 440 mm | 696 | 699 | ✅✅ PRESNÁ |
| Obvod ≤500 mm | 754 | 765 | ✅✅ ~1,5 % |
| Priečka 80 mm | 351 | (280+1,2×80)=376 | ⚠️ +7 % |
| Priečka 115 mm | 377 | 418 | ⚠️ +11 % |
| Priečka 175 mm | 403 | 490 | ⚠️ +22 % |
| Ytong 300 mm | 520 | 545 | ✅ ~5 % |
| Ytong 375 mm | 553 | 628 | ⚠️ +14 % |

**→ APPKA:** vzorec pre OBVOD je výborne kalibrovaný (potvrdené nezávislým zdrojom!).
Vzorec pre PRIEČKY nadhodnocuje — fit na dáta: priečky ≈ 330 + 0,55×mm
(80→374✗... presnejšie: lineárna regresia na [80:351, 115:377, 175:403, 240:501]
→ ~283 + 0,90×mm; overiť viac bodmi). Znížiť `praca_priecky.per_mm`.

## 8. ČO SA NEPODARILO VYZBIERAŤ (na ďalšie kolo — LACNO, cielene)

1. Ztratné/prořez % (výrobca/ÚRS) — zatiaľ nepoužívať
2. Veniec komplet Kč/bm (betón+výstuž+práca) — nechať 1200
3. Ytong cenník (Xella) — triedy pórobetónu
4. Benchmarky hrubá stavba Kč/m² (RTS ukazatele) — na cross-check
5. Typické plochy okien moderných RD — na sanity check
6. Reálne zľavy z MOC (overiť cez DEK akciové ceny vs. cenník)

## POZNÁMKA K OVEROVANIU
Adverzariálna verifikácia padla na session limit (hlasy 0-0 = neoverené, NIE vyvrátené).
Všetky čísla sú z primárnych zdrojov (technické listy, oficiálny cenník, ÚRS, DEK,
cenikyremesel) — pred zápisom do cihly.json overiť aspoň kliknutím na zdroj.
Krížovo potvrdené už teraz: 16 ks/m² (3 zdroje), KP7 rozmery (TL+DEK), práce obvod
(cenikyremesel vs. náš vzorec = zhoda do 1,5 %).
