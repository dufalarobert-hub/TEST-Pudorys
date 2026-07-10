# Simulácia web-app flow: 4 pôdorysy (1.PP, 1.NP, 2.NP, 3.NP) → extrakcia FABLE
# (ručne, vision, 2026-07-09) → _aggregate_floors (kópia z app.py PO refaktore
# 2026-07-07) → reconcile.quality_gate → pricing.calculate
#
# DOM: členitý RD vo svahu (P.T. 278,4 / 277,6 m n.m., svah 21-30°), split-level:
#   1.PP -3,285 (0.01-0.06, steny pravdep. BETÓN/deb. tvárnice + izol., kóty 250+125)
#   medziúroveň -1,460/-1,760 (1.06 obytná hala s.v. 3,86, 1.07 kuchyňa, 1.08-1.09)
#   1.NP ±0,000 (1.01-1.05 + terasa 1.10)
#   2.NP +2,920 (2.01-2.06 + terasa/strecha 2.07 na +3,175)
#   3.NP +5,840 (3.01-3.03 + strecha 3.04 na +6,085/+6,320)
# Schodisko 15x265x182,5 → 16×182,5 = 2 920 mm = presne kóta podlažia ✓
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pricing
import reconcile

# ============ FABLE EXTRAKCIA — 1.PP (-3,285) ============
floor_1pp = {
    "typ_stavby": "rodinny_dum",
    "konstrukce": "zdene",
    "obvod_m": 56.0,           # hlavný blok ~2*(11.5+5.9)=34.8 + blok 0.03 (7.65+2*0.375)×4.5 zdieľa ~4.5 m → +21
    "rozmery_celkove_m": {"sirka_m": 21.0, "dlzka_m": 5.9},
    "obvod_tloustka_mm": 250,   # kóty 250+125: 250 nosná stena + 125 izolácia/prímurovka
    "stena_celkova_mm": 375,
    "tloustka_z_koty": True,
    "ma_zateplenie": True,      # 1.PP: perimetrická izolácia 125 (kóta)
    "obvod_material": None,     # šedá výplň + OS1 → pravdepodobne BETÓN/monolit, NIE tehla!
    "obvod_material_trieda": None,
    "zdivo_zdroj": "kóta",
    "vnitrni_nosne_m": 8.0,     # jadro schodiska + stena 0.02|0.03 (tl. 250)
    "vnitrni_nosne_tloustka_mm": 250,
    "pricky_m": 7.0,            # kúpeľňa 0.05 + WC + 0.04 (tl. 100/150)
    "pricky_tloustka_mm": 125,
    "pricky_material": None,
    "plochy_mistnosti_m2": [9.5, 14.7, 28.7, 3.4, 4.2, 10.2],  # 0.01-0.06 (z kót)
    "uzitna_plocha_m2": 70.7,
    "zastavena_plocha_m2": None,
    "pocet_podlazi": 1,
    "ma_schodiste": True,
    "ma_garaz": True,           # 0.03 (7.65×3.75, s.v. 2,6) — garáž/sklad, vlastný blok
    "ma_garazova_vrata": False, # vráta NEVIDNO — len okenný pás 4500 s parapetom (950)
    "vyska_podlazi_m": 3.29,    # -3,285→±0,000 (s.v. 2,885 + strop)
    "schodiste_stupne": 18,     # 9+4+... medzipodesty, výška stupňa 182,5
    "schodiste_vyska_stupne_mm": 182.5,
    # KONVENCIA KÓT OTVOROV (dekódovaná): šírka NAD kótou, výška(parapet) POD ňou.
    # Overenie: 0.03: 950+1650 = 2600 = s.v. 2,6 ✓
    "otvory": [
        {"typ": "okno", "sirka_m": 4.5, "pocet": 1, "vyska_m": 1.65},  # pás 0.03 juh: 4500 × 1650(950)
        {"typ": "dvere_vchod", "sirka_m": 0.9, "pocet": 1, "vyska_m": 2.03},  # D6 900/2025 (vstup z dlažby -2,555)
        {"typ": "dvere_vnitrni", "sirka_m": 0.8, "pocet": 2},          # D5 800/1970 ×2
        {"typ": "dvere_vnitrni", "sirka_m": 0.7, "pocet": 1},          # D1 700/1970 (0.05)
        {"typ": "dvere_vnitrni", "sirka_m": 0.9, "pocet": 1},          # D2 900/1970
    ],
    "pocet_oken": 1,
    "pocet_dveri": 5,
    "pocet_mistnosti": 6,
    "koty_mm": [21000, 5500, 5350, 7650, 3750, 4500, 2750, 2485, 1850, 250, 125,
                1800, 1600, 2100, 5250, 1950, 900, 2025, 800, 700, 1970, 4400, 3100],
    "meritko_source": "z kót",
    "confidence_0_100": 72,
    "co_potvrdit": [
        "materiál stien 1.PP — šedá výplň vyzerá ako BETÓN/debniace tvárnice (kóta 250+125), tehlová cena je len náhrada",
        "0.03 = garáž alebo sklad? vráta nevidno, len okenný pás 4500",
        "obvod 1.PP je odhad z členitého polygonu (blok 0.03 čiastočne zdieľa steny)",
    ],
    "note": "Suterén vo svahu, sever+západ pod terénom (šrafy). Kvalitný CAD, kóty čitateľné.",
}

# ============ FABLE EXTRAKCIA — 1.NP (±0,000 + medziúroveň -1,460) ============
floor_1np = {
    "typ_stavby": "rodinny_dum",
    "konstrukce": "zdene",
    "obvod_m": 48.0,           # horný blok ~11.5×6.0 + znížený blok 1.06/1.07 ~12.0×5.6 (L/split polygon)
    "rozmery_celkove_m": {"sirka_m": 12.75, "dlzka_m": 11.5},
    "obvod_tloustka_mm": 375,   # kóta 375, jednovrstvové (zateplenie na výkrese nevidno)
    "stena_celkova_mm": 375,
    "tloustka_z_koty": True,
    "ma_zateplenie": False,
    "obvod_material": None,     # legenda materiálov na pôdoryse nie je
    "obvod_material_trieda": None,
    "zdivo_zdroj": "kóta",
    "vnitrni_nosne_m": 12.0,    # deliaca stena split-levelu + jadro schodiska (tl. 250-375)
    "vnitrni_nosne_tloustka_mm": 250,
    "pricky_m": 10.0,           # 1.01|1.02|1.03 + 1.05 + 1.08|1.09 (tl. 100/150)
    "pricky_tloustka_mm": 125,
    "pricky_material": None,
    # 1.01 zádverie/hala 8.5, 1.02 WC 2.4, 1.03 izba 7.3, 1.04 izba 24.4 (5250×4650),
    # 1.05 hala+schody 10.0, 1.06 obytný priestor 40.7 (7750×5250, s.v. 3,86, -1,460),
    # 1.07 kuchyňa 12.3 (4250×2900), 1.08 špajza 4.0, 1.09 tech. 5.0 (s.v. 2,26)
    "plochy_mistnosti_m2": [8.5, 2.4, 7.3, 24.4, 10.0, 40.7, 12.3, 4.0, 5.0],
    "uzitna_plocha_m2": 114.6,
    "zastavena_plocha_m2": None,
    "pocet_podlazi": 1,
    "ma_schodiste": True,
    "ma_garaz": False,
    # VÁŽENÁ výška za celý dom (pricing berie výšku z base podlažia = tohto):
    # (56×3.29 + 26×2.92 + 22×4.38[steny 1.06/1.07 od -1,460 po +2,920] + 41×2.92
    #  + 24×2.7) / 169 ≈ 3.20 m
    "vyska_podlazi_m": 3.20,
    "schodiste_stupne": 16,     # 15x265x182,5 + nástup = 16×182,5 = 2 920 ✓
    "schodiste_vyska_stupne_mm": 182.5,
    # Konvencia: šírka NAD kótou, výška(parapet) POD ňou. 1.06: 400+3460 = 3860 = s.v. ✓
    "otvory": [
        {"typ": "dvere_vchod", "sirka_m": 0.9, "pocet": 1, "vyska_m": 2.1},    # hlavný vstup (zóna 1600/2400)
        {"typ": "okno", "sirka_m": 1.5, "pocet": 1, "vyska_m": 0.85},          # 1500 × 850(1550), zóna 1.02/1.03
        {"typ": "okno", "sirka_m": 0.8, "pocet": 1, "vyska_m": 0.85},          # západ ~800 × 850(1550)
        {"typ": "hs_portal", "sirka_m": 3.6, "pocet": 1, "vyska_m": 2.4},      # 1.04 → terasa 1.10 (šírka VIZUÁLNY odhad!)
        {"typ": "hs_portal", "sirka_m": 6.05, "pocet": 1, "vyska_m": 3.46},    # 1.06 juh: 6050 × 3460(400) = 20,9 m²!
        {"typ": "dvere_vchod", "sirka_m": 0.725, "pocet": 1, "vyska_m": 1.97}, # D4 725/1970 (1.06 → exteriér)
        {"typ": "okno", "sirka_m": 1.5, "pocet": 1, "vyska_m": 0.85},          # 1.07 kuchyňa: ~1500 × 850(1200)
        {"typ": "dvere_vnitrni", "sirka_m": 0.7, "pocet": 3},                  # D1 700/1970 ×3
        {"typ": "dvere_vnitrni", "sirka_m": 0.9, "pocet": 1},                  # D2 900/1970
        {"typ": "dvere_vnitrni", "sirka_m": 0.8, "pocet": 1},                  # D8/D5 800
    ],
    "pocet_oken": 5,
    "pocet_dveri": 7,
    "pocet_mistnosti": 9,
    "koty_mm": [12750, 11500, 8500, 4250, 5500, 2400, 375, 100, 150, 5250, 6450,
                4650, 7750, 2900, 4250, 2750, 3090, 2050, 3060, 850, 1550, 6050,
                3460, 400, 725, 1970, 700, 900, 12000, 1460, 1760, 2920],
    "meritko_source": "z kót",
    "confidence_0_100": 80,
    "co_potvrdit": [
        "šírka presklenia 1.04→terasa (kóta šírky chýba, vizuálny odhad 3,6 m)",
        "presklenie 1.06 juh: čítam 6050 so segmentom 3460, parapet 400 — over členenie",
        "jednovrstvové murivo 375 bez zateplenia? (žiadna vrstva ETICS na výkrese)",
        "steny 1.06/1.07 sú vysoké ~4,4 m (od -1,460 po +2,920) — zohľadnené vo váženej výške 3,20 m",
    ],
    "note": "Split-level: 1.06/1.07 na -1,460 so s.v. 3,86; zvyšok ±0,000 s.v. 2,64. Terasa 1.10 nezapočítaná.",
}

# ============ FABLE EXTRAKCIA — 2.NP (+2,920) ============
floor_2np = {
    "typ_stavby": "rodinny_dum",
    "konstrukce": "zdene",
    "obvod_m": 41.0,           # ~2×(11.5+9.0), terasa 2.07 mimo (nad 1.06)
    "rozmery_celkove_m": {"sirka_m": 11.5, "dlzka_m": 9.0},
    "obvod_tloustka_mm": 375,
    "stena_celkova_mm": 375,
    "tloustka_z_koty": True,
    "ma_zateplenie": False,
    "obvod_material": None,
    "obvod_material_trieda": None,
    "zdivo_zdroj": "kóta",
    "vnitrni_nosne_m": 6.0,     # jadro schodiska + stred (tl. 250)
    "vnitrni_nosne_tloustka_mm": 250,
    "pricky_m": 15.0,           # 2.01|2.02|2.03 + 2.04|2.05 + 2.05|2.06 + kúpeľňa (tl. 100/150)
    "pricky_tloustka_mm": 125,
    "pricky_material": None,
    # 2.01 chodba 11.5, 2.02 kúpeľňa 5.2, 2.03 6.5, 2.04 16.0, 2.05 13.9 (4150×3350), 2.06 21.0 (5250×4000)
    "plochy_mistnosti_m2": [11.5, 5.2, 6.5, 16.0, 13.9, 21.0],
    "uzitna_plocha_m2": 74.1,
    "zastavena_plocha_m2": None,
    "pocet_podlazi": 1,
    "ma_schodiste": True,
    "ma_garaz": False,
    "vyska_podlazi_m": 2.92,    # +2,920 → +5,840, schodisko 16×182,5 ✓
    "schodiste_stupne": 16,
    "schodiste_vyska_stupne_mm": 182.5,
    # Konvencia: šírka NAD kótou, výška(parapet) POD ňou. Izby: 750+1650 = 2400 = hlava okien ✓
    "otvory": [
        {"typ": "okno", "sirka_m": 1.5, "pocet": 1, "vyska_m": 0.85},   # 1500 × 850(1550) hore (2.03 zóna)
        {"typ": "okno", "sirka_m": 0.8, "pocet": 1, "vyska_m": 0.85},   # západ ~800 × 850(1550)
        {"typ": "okno", "sirka_m": 4.5, "pocet": 1, "vyska_m": 1.65},   # 2.06: 4500 × 1650(750) [K]
        {"typ": "okno", "sirka_m": 3.0, "pocet": 1, "vyska_m": 1.65},   # 2.04: ? × 1650(750), šírka ODHAD
        {"typ": "okno", "sirka_m": 2.4, "pocet": 1, "vyska_m": 1.65},   # 2.05: ? × 1650(750), šírka ODHAD
        {"typ": "dvere_vchod", "sirka_m": 0.9, "pocet": 1, "vyska_m": 2.02},  # výstup na terasu 2.07 (900/2020)
        {"typ": "dvere_vnitrni", "sirka_m": 0.7, "pocet": 2},           # D1 700/1970 ×2 (2.02, 2.03)
        {"typ": "dvere_vnitrni", "sirka_m": 0.8, "pocet": 3},           # D5 800/1970 ×3 (2.04-2.06)
    ],
    "pocet_oken": 5,
    "pocet_dveri": 6,
    "pocet_mistnosti": 6,
    "koty_mm": [11500, 5500, 6000, 375, 100, 150, 250, 5250, 4150, 3350, 4000,
                2900, 3440, 1650, 750, 850, 1550, 800, 1970, 700, 900, 2020,
                2920, 3175, 15, 265, 182.5],
    "meritko_source": "z kót",
    "confidence_0_100": 78,
    "co_potvrdit": [
        "šírky okien 1650(750) — kóty čítané z krúžkov T3-T5, over",
        "2.07 je terasa/plochá strecha nad 1.06 (+3,175) — nezapočítaná do plôch ani obvodu",
    ],
    "note": "s.v. 2,64 m; znížený podhľad 2,4 m v časti 2.04.",
}

# ============ FABLE EXTRAKCIA — 3.NP / podkrovie (+5,840) ============
floor_3np = {
    "typ_stavby": "rodinny_dum",
    "konstrukce": "zdene",
    "obvod_m": 24.0,           # malý blok ~6.0×6.0 (zvyšok = strecha 3.04)
    "rozmery_celkove_m": {"sirka_m": 6.0, "dlzka_m": 6.0},
    "obvod_tloustka_mm": 375,
    "stena_celkova_mm": 375,
    "tloustka_z_koty": True,
    "ma_zateplenie": False,
    "obvod_material": None,
    "obvod_material_trieda": None,
    "zdivo_zdroj": "kóta",
    "vnitrni_nosne_m": 2.0,
    "vnitrni_nosne_tloustka_mm": 250,
    "pricky_m": 5.0,            # 3.01|3.02 + 3.03 (tl. 100/150)
    "pricky_tloustka_mm": 125,
    "pricky_material": None,
    "plochy_mistnosti_m2": [6.5, 15.8, 4.1],  # 3.01 hala, 3.02 izba (3000×5250), 3.03 kúpeľňa
    "uzitna_plocha_m2": 26.4,
    "zastavena_plocha_m2": None,
    "pocet_podlazi": 1,
    "ma_schodiste": True,
    "ma_garaz": False,
    "vyska_podlazi_m": 2.7,     # s.v. 2,64/2,4 + strop (posledné podlažie)
    "schodiste_stupne": 16,
    "schodiste_vyska_stupne_mm": 182.5,
    # Konvencia: šírka NAD kótou, výška(parapet) POD ňou.
    "otvory": [
        {"typ": "okno", "sirka_m": 1.5, "pocet": 1, "vyska_m": 0.85},   # hore (3.03 zóna): ~1500 × 850(1550)
        {"typ": "okno", "sirka_m": 0.8, "pocet": 1, "vyska_m": 0.85},   # 3.01 západ: ~800 × 850(1550)
        {"typ": "okno", "sirka_m": 1.5, "pocet": 1, "vyska_m": 1.65},   # 3.02 juh (kóta 1500, Z8 zábradlie → možno francúzske)
        {"typ": "dvere_vnitrni", "sirka_m": 0.7, "pocet": 1},           # D1 700/1970 (3.03)
        {"typ": "dvere_vnitrni", "sirka_m": 0.8, "pocet": 1},           # D5 800/1970 (3.02)
    ],
    "pocet_oken": 3,
    "pocet_dveri": 2,
    "pocet_mistnosti": 3,
    "koty_mm": [6000, 3000, 3750, 5250, 2400, 375, 100, 150, 850, 1550, 1905,
                2150, 1500, 700, 800, 1970, 5840, 6085, 6320, 460, 665],
    "meritko_source": "z kót",
    "confidence_0_100": 74,
    "co_potvrdit": [
        "3.04 je plochá strecha (+6,085/+6,320, K4 klampiarske) — nezapočítaná",
        "okno 3.02 juh: kóta 1500 pri Z8 — okno alebo francúzske so zábradlím?",
    ],
    "note": "Ustúpené podlažie ~6×6 m nad schodiskovou časťou; zvyšok pôdorysu = strechy.",
}


# ============ _aggregate_floors — VERBATIM kópia z app.py (po refaktore 2026-07-07) ============
def _aggregate_floors(floors):
    n = len(floors)
    base = max(floors, key=lambda fl: int(fl.get("confidence_0_100") or 0))
    rooms, otvory = [], []
    for fl in floors:
        rooms += list(fl.get("plochy_mistnosti_m2") or [])
        otvory += list(fl.get("otvory") or [])

    def s(k):
        return sum(float(fl.get(k) or 0) for fl in floors)

    agg = dict(base)
    agg.update({
        "obvod_m": round(s("obvod_m"), 1),
        "vnitrni_nosne_m": round(s("vnitrni_nosne_m"), 1),
        "pricky_m": round(s("pricky_m"), 1),
        "pocet_oken": int(s("pocet_oken")),
        "pocet_dveri": int(s("pocet_dveri")),
        "uzitna_plocha_m2": round(s("uzitna_plocha_m2"), 1) or None,
        "zastavena_plocha_m2": None,
        "plochy_mistnosti_m2": rooms,
        "otvory": otvory,
        "pocet_podlazi": 1,
        "_floors_summed": n,
        "confidence_0_100": min(int(fl.get("confidence_0_100") or 0) for fl in floors),
        "ma_zateplenie": any(fl.get("ma_zateplenie") for fl in floors),
        "ma_garaz": any(fl.get("ma_garaz") for fl in floors),
        "ma_schodiste": False,
    })
    vrata = [fl.get("ma_garazova_vrata") for fl in floors]
    agg["ma_garazova_vrata"] = (any(v for v in vrata)
                                if any(v is not None for v in vrata) else None)
    if any(fl.get("pricky_material") == "sdk" for fl in floors):
        agg["pricky_material"] = "sdk"
    return agg


def report(label, floors):
    print(f"\n{'=' * 70}\n===== {label} =====\n{'=' * 70}")
    for fl in floors:
        dec, msg = reconcile.quality_gate(fl)
        print(f"GATE conf={fl['confidence_0_100']}: {dec} {('— ' + msg) if msg else ''}")

    agg = _aggregate_floors(floors)
    result = pricing.calculate(agg)

    print("\n----- AGREGÁT (vstup do pricing) -----")
    for k in ("obvod_m", "vnitrni_nosne_m", "pricky_m", "pocet_oken", "pocet_dveri",
              "uzitna_plocha_m2", "_floors_summed", "confidence_0_100",
              "ma_garaz", "ma_garazova_vrata", "vyska_podlazi_m"):
        print(f"  {k}: {agg.get(k)}")

    print("\n----- ROZPOČET (pricing.calculate) -----")
    print(f"Trieda: {result['tier']} ({result['tier_popis']}), auto={result['tier_auto']}")
    print(f"Skladba: assumed={result['assumed_skladba']}, volba={result['skladba_volba']}, "
          f"stena_raw={result['stena_mm_raw']} mm, zdivo={result['detected_thickness_mm']} mm")
    for i in result["items"]:
        print(f"  {i['name']:<45} {i['detail']:<52} {i['total']:>10,} Kč")
    li = result["labor_item"]
    print(f"  {li['name']:<45} {li['detail']:<52} {li['total']:>10,} Kč")
    print(f"\nMATERIÁL: {result['material_total']:,} Kč   PRÁCA: {result['labor_total']:,} Kč")
    print(f"ZDIVO SPOLU: {result['zdivo_total']:,} Kč   ±{result['band_pct']} % "
          f"=> {result['range_lo']:,} – {result['range_hi']:,} Kč")
    if result.get("skladba_variants"):
        print("Varianty skladby steny:")
        for v, d in result["skladba_variants"].items():
            print(f"  {v}: {d['zdivo_total']:,} Kč ({d['range_lo']:,}–{d['range_hi']:,}), "
                  f"zdivo {d['obvod_th']} mm")
    print("Cross-check:", json.dumps(result.get("crosscheck"), ensure_ascii=False))
    print("VAROVANIA:")
    for w in result["warnings"]:
        print("  •", w)
    return result


r_all = report("VARIANT A: celý dom (1.PP ako murovaný — HORNÁ hranica)",
               [floor_1pp, floor_1np, floor_2np, floor_3np])
r_bez = report("VARIANT B: bez 1.PP (suterén = betón, mimo rozsah zdiva)",
               [floor_1np, floor_2np, floor_3np])

print(f"\n{'=' * 70}")
print(f"SUMÁR: A (s 1.PP) {r_all['zdivo_total']:,} Kč | B (bez 1.PP) {r_bez['zdivo_total']:,} Kč")
print("Úžitná plocha celkom: 285,8 m² (1.PP 70,7 + 1.NP 114,6 + 2.NP 74,1 + 3.NP 26,4)")
