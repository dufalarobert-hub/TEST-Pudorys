# Ground Truth — merací etalón (Fáza 0)

Drafty čítal Claude (iný model než Gemini v appke — nie je to kruh). Pred použitím
v eval.py treba každý súbor ĽUDSKY OVERIŤ proti výkresu a prepnúť `"verified": true`.

## Prehľad test setu (16 súborov)

### ✅ POZITÍVNE — plnohodnotné pôdorysy (8 súborov, 6 unikátnych domov)

| Súbor | Dom | Obvod | Hrúbka | Okná/dvere | Čo overiť prioritne |
|---|---|---|---|---|---|
| plan_49661930 | bungalov obdĺžnik 12.18×7.30 | 38.96 m | 350 | 8/8 | nosné 6.5 m? priečky 20 m? |
| plan_49661933 | L-tvar 14.10×7.65 (73.91 m²) | 43.5 m | 450 | 6/8 | počet vnút. dverí |
| plan_49662023 | ⚠️ TEN ISTÝ dom ako 49661933 | 43.5 m | 450 | 6/8 | krížová kontrola — čísla musia sedieť s 49661933 |
| plan_49665296 | POSCHODIE poľského projektu 15.98×7.24 | 46.4 m | ~250 ⚠️odvodená | 3/7 | hrúbka NIE JE kótovaná — odhad! |
| plan_49665297 | PRÍZEMIE toho istého, L + dvojgaráž | 62.7 m | ~250 ⚠️odvodená | 5/9 | odskoky južnej fasády (±2 m), HS portál 5 m |
| plan_49673151 | L-bungalov 5+KK 15.23×13.72 | 57.9 m | 405 | 10/11 | stena pri obývačke nosná vs. priečka |
| plan_49676022 | podlažie 16.85×7.0 | 47.7 m | 500 | ~5/8 | steny chodby nosné (16 m?) alebo priečky? |
| plan_49681696 | L-bungalov 16.71×11.21 (121.35 m²) | 55.84 m | 480 ⚠️dopočet | ~8/11 | hrúbka z rozdielu kót, nie priama kóta |

Pozn.: 49665296 + 49665297 = 2 podlažia jedného domu → použiť aj ako multi-floor test
(nahrať oba naraz, súčet musí sedieť).

### ⚠️ DEGRADOVANÝ — horšia kvalita, NESMIE byť REFUSE (1 súbor)

| Súbor | Popis | Použiteľné |
|---|---|---|
| plan_49681853 | amatérsky room-planner, L ~17.1×8.9, KÓTY SI NESEDIA, bez hrúbok a okien | len obvod ~52 m + plochy 119.4 m² |

Očakávané správanie appky: spočítať z dostupného, ROZŠÍRIŤ ±band, vysvetliť prečo.

### ❌ NEGATÍVNE — appka MUSÍ odmietnuť (7 súborov)

| Súbor | Čo to je |
|---|---|
| plan_49667100 | cenová ponuka projektovej dokumentácie (177 000 Kč) |
| plan_49667101 | cenová ponuka projekčných prác (152 000 Kč) |
| plan_49675097 | okenár Otherm — rohová zostava VAR.1 |
| plan_49675098 | detail rohu okenných profilov (RD Hlušovice) |
| plan_49675099 | okenár Otherm — rohová zostava VAR.2 |
| plan_49675100 | detail rohu okennej zostavy |
| plan_49682792 | fotografia kuchynského showroomu |

## Ako overovať (na 1 súbor ~2–5 min)

1. Otvor výkres + JSON vedľa seba.
2. Skontroluj v tomto poradí (podľa váhy na cene):
   a) **obvod_m** — sedí polygón? nezapočítaná terasa? (najväčšia váha!)
   b) **obvod_tloustka_mm** — je z kóty, alebo odhad? (pozri `_tloustka_zdroj`)
   c) **nosné vs. priečky** — drafty tu priznávajú najväčšiu neistotu
   d) okná/dvere počty, plochy
3. Oprav čísla priamo v JSON, do `kdo_meril` doplň seba, prepni `"verified": true`.
4. Polia s `_` prefixom sú komentáre — nechaj/dopĺňaj, eval.py ich ignoruje.

Až po overení má zmysel baseline: `python3 eval.py` (1 beh/výkres, max ~9 volaní
na pozitívne+degradovaný; negatívne sa testujú zvlášť na gate).
