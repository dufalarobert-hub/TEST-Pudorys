# TEST 2 — členitý RD s plochou strechou, kryté státie + krytá terasa (atika +3,530)
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pricing
import reconcile

floor_1np = {
    "typ_stavby": "rodinny_dum", "konstrukce": "zdene",
    "obvod_m": 59.0,   # T-tvar: pravouhlý polygón = bbox perimeter 2*(10.02+19.46)
    "rozmery_celkove_m": {"sirka_m": 10.0, "dlzka_m": 19.5},
    "obvod_tloustka_mm": 300,   # kóty 200|300: murivo 300 + zateplenie 200 ("svod zapuštěný v zateplení")
    "tloustka_z_koty": True, "ma_zateplenie": True,
    "obvod_material": None, "obvod_material_trieda": None, "zdivo_zdroj": "kóta",
    "vnitrni_nosne_m": 12.0, "vnitrni_nosne_tloustka_mm": 240,
    "pricky_m": 25.0, "pricky_tloustka_mm": 120,
    "plochy_mistnosti_m2": [7.4, 1.3, 14.1, 7.5, 13.3, 10.1, 7.9, 58.0],  # 1.01-1.08
    "uzitna_plocha_m2": 119.6, "zastavena_plocha_m2": 159.0,
    "pocet_podlazi": 1, "ma_schodiste": True, "ma_garaz": False,  # kryté státie = carport bez stien
    "vyska_podlazi_m": 3.35,   # schody 19x176=3344, 2.NP na +3,350
    "otvory": [
        {"typ": "francouzske_okno", "sirka_m": 2.15, "pocet": 2},  # O02 sever, 2600(0)
        {"typ": "francouzske_okno", "sirka_m": 1.5, "pocet": 1},   # O01 sever
        {"typ": "francouzske_okno", "sirka_m": 1.1, "pocet": 2},   # O03 východ (1.06, 1.07)
        {"typ": "francouzske_okno", "sirka_m": 2.2, "pocet": 1},   # O04 východ jedáleň (v. 3000)
        {"typ": "francouzske_okno", "sirka_m": 1.8, "pocet": 1},   # O05 juh
        {"typ": "francouzske_okno", "sirka_m": 2.45, "pocet": 1},  # O06 juh
        {"typ": "hs_portal", "sirka_m": 4.65, "pocet": 1},         # O07 západ na terasu
        {"typ": "francouzske_okno", "sirka_m": 2.55, "pocet": 1},  # O08 západ
        {"typ": "dvere_vchod", "sirka_m": 1.0, "pocet": 1},        # D1 1000/2550
        {"typ": "dvere_vnitrni", "sirka_m": 0.8, "pocet": 5},      # D2 800/2550
        {"typ": "dvere_vnitrni", "sirka_m": 1.6, "pocet": 1},      # D3 1600/2600 posuvné
    ],
    "pocet_oken": 10, "pocet_dveri": 7, "pocet_mistnosti": 8,
    "koty_mm": [10020, 19460, 6600, 300, 200, 120, 240, 2150, 1500, 1100, 2200, 1800,
                2450, 4650, 2550, 2600, 3000, 1000, 800, 1600, 4880, 3930, 4260, 3270],
    "meritko_source": "z kót",
    "confidence_0_100": 76,
    "co_potvrdit": ["obvod T-tvaru (členité západné priečelie)", "okno v zádverí 1.01",
                    "dĺžky vnútorných stien (odhad)"],
    "note": "Realizačný výkres; okná majú vzor 'šírka + 2600 (0)' = výška 2,6 m, parapet 0.",
}

floor_2np = {
    "typ_stavby": "rodinny_dum", "konstrukce": "zdene",
    "obvod_m": 55.1,   # 2*(9.1+18.46)
    "rozmery_celkove_m": {"sirka_m": 9.1, "dlzka_m": 18.5},
    "obvod_tloustka_mm": 300, "tloustka_z_koty": True, "ma_zateplenie": True,
    "obvod_material": None, "obvod_material_trieda": None, "zdivo_zdroj": "kóta",
    "vnitrni_nosne_m": 8.0, "vnitrni_nosne_tloustka_mm": 240,
    "pricky_m": 18.0, "pricky_tloustka_mm": 120,
    "plochy_mistnosti_m2": [26.0, 30.0, 11.0, 6.5, 14.6, 14.6],  # 2.01-2.06
    "uzitna_plocha_m2": 102.7, "zastavena_plocha_m2": 146.0,
    "pocet_podlazi": 1, "ma_schodiste": True, "ma_garaz": False,
    "vyska_podlazi_m": 3.35,
    "otvory": [
        {"typ": "francouzske_okno", "sirka_m": 2.15, "pocet": 2},  # O02 sever
        {"typ": "francouzske_okno", "sirka_m": 1.8, "pocet": 1},   # O05 juh
        {"typ": "francouzske_okno", "sirka_m": 2.45, "pocet": 1},  # O06 juh
        {"typ": "francouzske_okno", "sirka_m": 1.1, "pocet": 1},   # O03 východ (2.04)
        {"typ": "francouzske_okno", "sirka_m": 2.22, "pocet": 1},  # O04 východ (2.01)
        {"typ": "francouzske_okno", "sirka_m": 2.0, "pocet": 1},   # O09 západ (2.01)
        {"typ": "dvere_vnitrni", "sirka_m": 0.8, "pocet": 5},      # D2 800/2550
    ],
    "pocet_oken": 7, "pocet_dveri": 5, "pocet_mistnosti": 6,
    "koty_mm": [9100, 18460, 16800, 6600, 3590, 4080, 7300, 4470, 2150, 1100, 2220,
                2000, 1800, 2450, 120, 300, 3350, 3530],
    "meritko_source": "z kót",
    "confidence_0_100": 72,
    "co_potvrdit": ["západné okná 2.02 (neisté značenie O10)", "výška 2.NP (rez chýba)"],
    "note": "Atiky +3,530 = strechy krytého státia a terasy (stĺpy, bez stien) — vylúčené z obvodu.",
}


def _aggregate_floors(floors):   # verbatim z app.py
    n = len(floors)
    base = max(floors, key=lambda fl: int(fl.get("confidence_0_100") or 0))
    rooms = []
    for fl in floors:
        rooms += list(fl.get("plochy_mistnosti_m2") or [])

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
        "pocet_podlazi": 1,
        "_floors_summed": n,
        "confidence_0_100": min(int(fl.get("confidence_0_100") or 0) for fl in floors),
        "ma_zateplenie": any(fl.get("ma_zateplenie") for fl in floors),
        "ma_garaz": any(fl.get("ma_garaz") for fl in floors),
        "ma_schodiste": False,
    })
    return agg


for label, fl in (("1.NP", floor_1np), ("2.NP", floor_2np)):
    dec, msg = reconcile.quality_gate(fl)
    print(f"GATE {label}: {dec} {('— ' + msg) if msg else ''}")

agg = _aggregate_floors([floor_1np, floor_2np])
r = pricing.calculate(agg)

print("\n===== AGREGÁT =====")
for k in ("obvod_m", "vnitrni_nosne_m", "pricky_m", "pocet_oken", "pocet_dveri",
          "uzitna_plocha_m2", "_floors_summed", "confidence_0_100"):
    print(f"  {k}: {agg[k]}")

print("\n===== ROZPOČET =====")
print(f"Trieda: {r['tier']} ({r['tier_popis']}), auto={r['tier_auto']}")
print(f"Skladba: assumed={r['assumed_skladba']}, volba={r['skladba_volba']}, "
      f"stena_raw={r['stena_mm_raw']}, zdivo={r['detected_thickness_mm']} mm")
for i in r["items"]:
    print(f"  {i['name']:<45} {i['detail']:<52} {i['total']:>10,} Kč")
li = r["labor_item"]
print(f"  {li['name']:<45} {li['detail']:<52} {li['total']:>10,} Kč")
print(f"\nMATERIÁL: {r['material_total']:,} Kč   PRÁCA: {r['labor_total']:,} Kč")
print(f"ZDIVO SPOLU: {r['zdivo_total']:,} Kč  ±{r['band_pct']} % => {r['range_lo']:,} – {r['range_hi']:,} Kč")
print(f"Priečky: {r['pricky_zdroj']}, AI={r['pricky_ai_m']} m, geom={r['pricky_geom_m']} m")
if r.get("skladba_variants"):
    for v, d in r["skladba_variants"].items():
        print(f"  varianta {v}: {d['zdivo_total']:,} Kč ({d['range_lo']:,}–{d['range_hi']:,})")
print("Cross-check:", json.dumps(r.get("crosscheck"), ensure_ascii=False))
print("VAROVANIA:")
for w in r["warnings"]:
    print("  •", w)
