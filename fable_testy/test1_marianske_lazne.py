# Simulácia web-app flow: 2 pôdorysy (multi-fóto) → extrakcia FABLE (ručne, vision)
# → _aggregate_floors (kópia z app.py) → reconcile.quality_gate → pricing.calculate
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pricing
import reconcile

# ============ FABLE EXTRAKCIA — 1.NP ============
floor_1np = {
    "typ_stavby": "rodinny_dum",
    "konstrukce": "zdene",
    "obvod_m": 52.9,          # hlavný dom 2*(8.0+11.5)=39.0 + tech. miestnosť 1.06: 2*(3.80+3.15)=13.9
    "rozmery_celkove_m": {"sirka_m": 11.8, "dlzka_m": 11.5},
    "obvod_tloustka_mm": 300,  # kóta skladby 300 (murivo) + 200 (zateplenie) = stena 500
    "tloustka_z_koty": True,
    "ma_zateplenie": True,
    "obvod_material": None,    # legenda materiálu na výkrese nie je (len značky W2/Ž1/O#)
    "obvod_material_trieda": None,
    "zdivo_zdroj": "kóta",
    "vnitrni_nosne_m": 5.5,    # steny schodiskového jadra tl. 250 (kóta 250)
    "vnitrni_nosne_tloustka_mm": 250,
    "pricky_m": 12.0,          # deliaca stena juh. zóny ~5.5 + 1.03|1.01 2.25 + WC 2.81+1.1 (tl. 150)
    "pricky_tloustka_mm": 150,
    "plochy_mistnosti_m2": [9.1, 3.1, 6.3, 45.0, 7.4, 9.2],  # 1.01-1.06 (z kót, nie popisov)
    "uzitna_plocha_m2": 80.1,
    "zastavena_plocha_m2": 104.0,   # 8.0*11.5=92 + prístavok 3.8*3.15=12
    "pocet_podlazi": 1,
    "ma_schodiste": True,
    "ma_garaz": True,   # 1.06 = uzavretá technická miestnosť so stenami (bod 3c promptu)
    "vyska_podlazi_m": 2.8,  # 2.NP na kóte +2,800
    "otvory": [
        {"typ": "hs_portal", "sirka_m": 2.7, "pocet": 3},        # západná presklená stena ~8.1 m
        {"typ": "francouzske_okno", "sirka_m": 2.73, "pocet": 1}, # O2 rohové zasklenie, kóta 2725
        {"typ": "okno", "sirka_m": 1.6, "pocet": 1},              # O3, kóta 1600
        {"typ": "okno", "sirka_m": 1.0, "pocet": 2},              # O4 ×2 (1.03 + 1.06), kóty 1000
        {"typ": "dvere_vchod", "sirka_m": 0.9, "pocet": 1},       # D1 900/2100
        {"typ": "dvere_vchod", "sirka_m": 0.8, "pocet": 1},       # D2 800/2100 (exteriér 1.06)
        {"typ": "dvere_vnitrni", "sirka_m": 0.7, "pocet": 3},     # D4 ×3 700/2100
    ],
    "pocet_oken": 7,
    "pocet_dveri": 5,
    "pocet_mistnosti": 6,
    "koty_mm": [8000, 11500, 2725, 5275, 300, 200, 150, 250, 210, 8100, 6750,
                4040, 2810, 2250, 1100, 2960, 1080, 1600, 1000, 3380, 2730, 3500, 900, 700, 800],
    "meritko_source": "z kót",
    "confidence_0_100": 82,
    "co_potvrdit": ["šírky západného presklenia (kóta chýba, odhad 3×2,7 m)",
                    "1.06 je technická miestnosť bez garážových vrát",
                    "materiál muriva (na výkrese nie je legenda)"],
    "note": "Kvalitný CAD výkres s kótami; skladba steny 300+200 čítaná z kóty.",
}

# ============ FABLE EXTRAKCIA — 2.NP ============
floor_2np = {
    "typ_stavby": "rodinny_dum",
    "konstrukce": "zdene",
    "obvod_m": 39.0,           # 2*(8.0+11.5)
    "rozmery_celkove_m": {"sirka_m": 8.0, "dlzka_m": 11.5},
    "obvod_tloustka_mm": 300,
    "tloustka_z_koty": True,
    "ma_zateplenie": True,
    "obvod_material": None,
    "obvod_material_trieda": None,
    "zdivo_zdroj": "kóta",
    "vnitrni_nosne_m": 6.0,    # steny schodiska (sever+juh jadra)
    "vnitrni_nosne_tloustka_mm": 250,
    "pricky_m": 19.0,          # 2.02|2.03 4.6 + 2.03|2.04 4.04 + 2.04|2.01 3.0 + 2.04|2.05 4.04 + 2.05|2.06 3.5 (tl. 150)
    "pricky_tloustka_mm": 150,
    "plochy_mistnosti_m2": [6.0, 12.9, 14.5, 8.4, 14.5, 9.8],  # 2.01-2.06 (z kót)
    "uzitna_plocha_m2": 66.1,
    "zastavena_plocha_m2": 92.0,
    "pocet_podlazi": 1,
    "ma_schodiste": True,
    "ma_garaz": False,
    "vyska_podlazi_m": 2.8,
    "otvory": [
        {"typ": "okno", "sirka_m": 2.0, "pocet": 3},          # O5 ×3 západ — šírka VIZUÁLNY odhad
        {"typ": "okno", "sirka_m": 1.2, "pocet": 2},          # O6, O7 východ — šírka VIZUÁLNY odhad
        {"typ": "okno", "sirka_m": 1.6, "pocet": 1},          # O8 juh, kóta 1600
        {"typ": "dvere_vnitrni", "sirka_m": 0.8, "pocet": 3}, # D3 ×3 800/2100
        {"typ": "dvere_vnitrni", "sirka_m": 0.7, "pocet": 1}, # D4 700/2100 (kúpeľňa)
    ],
    "pocet_oken": 6,
    "pocet_dveri": 4,
    "pocet_mistnosti": 6,
    "koty_mm": [8000, 11500, 4040, 2810, 3600, 4600, 3000, 3500, 150, 1060, 9380,
                1600, 800, 700, 2100, 540, 1400, 1960, 1000, 4995, 1405],
    "meritko_source": "z kót",
    "confidence_0_100": 78,
    "co_potvrdit": ["šírky okien O5–O7 (kóty šírok chýbajú, vizuálny odhad)"],
    "note": "Kvalitný CAD výkres; medzipodesta +1,400, podlažie +2,800.",
}


# ============ _aggregate_floors — VERBATIM kópia z app.py ============
def _aggregate_floors(floors):
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
result = pricing.calculate(agg)

print("\n===== AGREGÁT (vstup do pricing) =====")
for k in ("obvod_m", "vnitrni_nosne_m", "pricky_m", "pocet_oken", "pocet_dveri",
          "uzitna_plocha_m2", "_floors_summed", "confidence_0_100", "ma_garaz"):
    print(f"  {k}: {agg[k]}")

print("\n===== ROZPOČET (pricing.calculate) =====")
print(f"Trieda: {result['tier']} ({result['tier_popis']}), auto={result['tier_auto']}")
print(f"Skladba: assumed={result['assumed_skladba']}, volba={result['skladba_volba']}, "
      f"stena_raw={result['stena_mm_raw']} mm, zdivo={result['detected_thickness_mm']} mm")
for i in result["items"]:
    print(f"  {i['name']:<45} {i['detail']:<50} {i['total']:>10,} Kč")
li = result["labor_item"]
print(f"  {li['name']:<45} {li['detail']:<50} {li['total']:>10,} Kč")
print(f"\nMATERIÁL: {result['material_total']:,} Kč   PRÁCA: {result['labor_total']:,} Kč")
print(f"ZDIVO SPOLU: {result['zdivo_total']:,} Kč   ±{result['band_pct']} % "
      f"=> {result['range_lo']:,} – {result['range_hi']:,} Kč")
print(f"Priečky: zdroj={result['pricky_zdroj']}, AI={result['pricky_ai_m']} m, "
      f"geom={result['pricky_geom_m']} m, band zdroje={result['band_zdroje']}")
if result.get("skladba_variants"):
    print("\nVarianty skladby steny:")
    for v, d in result["skladba_variants"].items():
        print(f"  {v}: {d['zdivo_total']:,} Kč ({d['range_lo']:,}–{d['range_hi']:,}), "
              f"zdivo {d['obvod_th']} mm")
print("\nCross-check:", json.dumps(result.get("crosscheck"), ensure_ascii=False, indent=2))
print("\nVAROVANIA:")
for w in result["warnings"]:
    print("  •", w)
