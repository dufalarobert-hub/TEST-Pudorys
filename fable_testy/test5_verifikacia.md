# Test 5 — verifikácia Fable čítania vs. reálna PD (2026-07-10)

Dom = **cvut_romanov_RD.pdf** (ČVUT FSv, Lucie Janovičová, 2018 — „Novostavba venkovského
rodinného domu v Romanově", Mšeno, CHKO Kokořínsko). Fable čítal 2 pôdorysy štúdie BEZ
prístupu k PD (test5_citanie_kompletne.md). Pôdorysy boli BEZ vnútorných kót → všetko [V].

**Dôležité: na pozemku sú DVA objekty** — RD 24×7,5 m + samostatný „Mini Haus" (sauna,
letná kuchyňa s pecou, dielňa, vínna pivnica; 82,56 m²). Screenshoty boli len RD →
porovnávam len RD.

## Súhrnné parametre

| Parameter | Fable | PD (GT) | Odchýlka |
|---|---|---|---|
| Rozmery domu | 24,0 × 7,5 m [K] | 24,0 × 7,5 m | **presne** ✓ |
| Zastavaná RD | 180 m² | 180 m² (footprint) | ✓ |
| Úžitná RD | 265 m² | **250,02 m²** | **+6,0 %** |
| — 1.NP (bez závětří) | 135 m² | 133,77 m² (142,09 so závětřím) | **+0,9 %** ✓✓ |
| — podkrovie | 130 m² (vr. schodov) | 107,93 m² | **+13–20 % ✗** (šikminy!) |
| Konštrukčná výška | 3,12 m [K] | 3,120 | ✓ |
| Obostavaný priestor | zámerne neodhadnutý | 1 092,13 m³ | — (poučenie z testu 4 aplikované) |
| Strecha | „skôr sedlová, podkrovie so šikminami" [V] | **sedlová 42°, obytné podkrovie** | ✓ tip správny |
| Garáž | NIE, 2 státia vonku | 2 parkovacie státia na spevnenej ploche | ✓✓ presne |

## Konštrukcie

| Konštrukcia | Fable [V] | PD (GT) | Verdikt |
|---|---|---|---|
| Obvod — celková hrúbka | **~500 mm** z mierky | **Porotherm T Profi 500** (jednovrstvové, MW v dutinách, omietky) | hrúbka ✓✓ presne; interpretácia „300+200 zateplenie" ✗ — je to PLNÉ murivo 500 → správny je pricing variant „plne" **1 430 695 Kč**, nie základných 1 054 360 |
| Vnútorné nosné | 250 mm | Porotherm 24, tl. 250 | ✓ |
| Priečky | 100–150 (125) | Porotherm 11,5 AKU | ✓ |
| Stropy | „rozpon 6,5 m naprieč, priečny systém" [V] | keramické nosníky PRIEČNE, svetlé rozpätie **6 500 mm**, strop 250 | ✓✓ presný tip |
| Sokel | — | Porotherm 38 TS + XPS 120 | nečitateľné z pôdorysu |
| Krov | — | hambálková sústava, krokvy à 980 | — |
| Kúrenie | „AKU nádrž, vonkajšia TČ jednotka?, krb?" | **TČ vzduch-voda + solár + krbové kamná**, podlahovka | ✓ všetky tri tipy |
| Vstup | krytá časť 1.01 so vstupom | **závětří vykousnuté z hmoty**, posuvné drevené tienenie ×3 | ✓ (tienenie = tie pásy pri terasách) |

## Miestnosti — plochy (Fable čísloval posunuto, porovnané PODĽA FUNKCIE)

### 1.NP
| Miestnosť (GT názov) | GT m² | Fable m² | Δ |
|---|---|---|---|
| závětří (1.02) | 8,32 | — (rátal ako exteriér) | metodický rozdiel |
| zádveří | 5,55 | 5 | −10 % |
| společenská chodba | 5,59 | 8 | +43 % ✗ |
| záchod | 2,31 | 2 | −13 % |
| kuchyně s jídelnou | 36,63 | 35 | **−4,5 %** ✓ |
| obývací pokoj | 23,12 | 30 | **+30 % ✗** (hranica kuchyňa/obývačka bez steny) |
| spíž | 2,95 | 3 | **+1,7 %** ✓✓ |
| technická místnost | 5,20 | 6 | +15 % |
| chodba s pracovním koutem | 12,03 | 6 + fantómová „kúpeľňa" 5 = 11 | −9 % (kúpeľňa v strede NEEXISTUJE — bol to pracovný kout) |
| ložnice | 17,31 | 16 | −7,6 % |
| koupelna | 10,00 | 10 | **0,0 %** ✓✓ |
| šatna | 5,00 | 4 | −20 % |
| prostor schodiště | 5,91 | 5 | −15 % |
| **Σ 1.NP** | **133,77** (bez závětří) | **135** | **+0,9 %** ✓✓ |

### Podkrovie
| GT | GT m² | Fable m² | Δ |
|---|---|---|---|
| 2.01 chodba | 22,23 | 18 | −19 % |
| 2.02 koupelna P1 | 6,89 | 8,5 | +23 % |
| 2.03 **TV místnost** | 16,04 | 20 („pracovňa") | +25 % |
| 2.04 koupelna P2 | 7,22 | 9,5 | +32 % |
| 2.05 pokoj 2 | 19,34 | 22 | +14 % |
| 2.06 šatna P2 | 5,58 | 8 | +43 % |
| 2.07 šatna P1 | 3,58 | 5 | +40 % |
| 2.08 pokoj 1 | 22,35 | 26 | +16 % |
| 2.09 šatna P1 | 4,70 | 5 | +6 % |
| **Σ podkrovie** | **107,93** | 130 (122 bez schodov) | **+13 až +20 % ✗** |

Systematické nadhodnotenie podkrovia = **šikminy** (GT počíta redukované úžitné plochy,
Fable bral plný pôdorys). Presne to bolo vo Fable co_potvrdit.

## Hlavné zistenia

1. **Geometria z 2 kót + mierky: výborná.** 1.NP plochy z čistej proporcie trafené na +0,9 %,
   celková úžitná +6 %. Krabicový dom 24×7,5 je na proporčné čítanie ideálny.
2. **Podkrovie bez rezu = systematická chyba +15 %.** Bez rezu nevieme šikminy — extract by
   mal pri „podkrovie + sedlová strecha" automaticky redukovať úžitnú (~×0,85) alebo pýtať rez.
3. **Materiál:** hrúbka 500 z mierky presná, ale bez šráf nerozoznateľné jednovrstvové vs
   zateplené. Porotherm T Profi 500 = PREMIUM tehla → reálna cena bližšie k variantu „plne"
   (1,43 mil.) s vyššou triedou. Kalkulačka varianty správne ponúkla — UI voľba skladby je tu kľúčová.
4. **Gate REFUSE bol správny** — štúdia bez kót nemá ísť do ostrého merania; ručný test
   ukázal, že s celkovými kótami + mierkou sa dá dostať na ±6 % úžitnej, ale otvory/výšky nie.
5. Numeracia miestností: Fable priradil čísla posunuto (1.05↔1.06 atď.) — funkcie boli
   správne, čísla labelov nie vždy pri správnej miestnosti. Pri PD flow porovnávať PODĽA FUNKCIE.
6. Fantómová kúpeľňa v strede 1.NP (bol to pracovný kout s umývadlom?? — na výkrese kruh
   = pravdepodobne svietidlo/stôl, nie umývadlo). Zariaďovacie predmety na štúdii zavádzajú.
7. Tipy potvrdené: stropné nosníky priečne na 6,5 m ✓, TČ+krb+AKU ✓, závětří ✓,
   2 státia bez garáže ✓, sedlová strecha ✓.
