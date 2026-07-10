# TEST 3 — bungalov Počaply nad Loučnou (Řehák), 1 podlažie, sedlová strecha
# Fable čítanie z JEDNÉHO pôdorysu (single-fóto flow). PD: fgv_komplet_dokumentace.pdf
# Realita: obvodové murivo = Porotherm 44 EKO Profi 440 mm BEZ zateplenia (jednovrstvový
#          tepelnoizolačný blok = trieda "drahé"); nosné 175, priečky 125 murované.
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pricing
import reconcile

# ============ FABLE EXTRAKCIA — 1.NP (bungalov, single) ============
# Pozn.: Fable z pôdorysu (bez legendy materiálu) odhadol stenu 450 ako murivo+zateplenie
# → ZLE (v skutočnosti jednovrstvový blok 440). Nižšie NECHÁVAM pôvodné (chybné) čítanie,
# aby test verne reprodukoval, čo Fable spravil; realitu drž v komentári + README.
fable_1np = {
    "typ_stavby": "rodinny_dum", "konstrukce": "zdene",
    "obvod_m": 43.1,                      # 2*(8.4+13.15) obdĺžnik
    "rozmery_celkove_m": {"sirka_m": 8.4, "dlzka_m": 13.15},
    "obvod_tloustka_mm": 300,             # Fable: stena 450 → odhad blok 300 + zateplenie 150
    "stena_celkova_mm": 450,              # celková hrúbka steny z kóty (NOVÉ pole)
    "tloustka_z_koty": True, "ma_zateplenie": True,   # ❌ realita: bez zateplenia (jednovrstvový 440)
    "obvod_material": None, "obvod_material_trieda": None, "zdivo_zdroj": "kóta",
    "vnitrni_nosne_m": 6.0, "vnitrni_nosne_tloustka_mm": 175,   # ✅ 175 presne
    "pricky_m": 19.0, "pricky_tloustka_mm": 125, "pricky_material": "zdene",  # ✅ murované
    "plochy_mistnosti_m2": [4.5, 1.5, 30.0, 2.7, 7.0, 5.0, 6.0, 11.1, 11.1, 10.2],
    "uzitna_plocha_m2": 89.0, "zastavena_plocha_m2": 110.5,   # ✅ zast. presne (PD 110,5)
    "pocet_podlazi": 1, "ma_schodiste": False,
    "ma_garaz": False, "ma_garazova_vrata": False,
    "vyska_podlazi_m": 2.8,               # bungalov bez rezu → default (PD neudáva svetlú v.)
    "otvory": [
        {"typ": "okno", "sirka_m": 1.5, "vyska_m": 1.0, "pocet": 4},   # sever+západ 1500(850)
        {"typ": "okno", "sirka_m": 1.0, "vyska_m": 1.0, "pocet": 3},   # východ 1000(1350)
        {"typ": "francouzske_okno", "sirka_m": 2.35, "vyska_m": 2.35, "pocet": 1},  # juh terasa
        {"typ": "okno", "sirka_m": 2.5, "vyska_m": 1.5, "pocet": 1},   # kuchyňa juh
        {"typ": "dvere_vchod", "sirka_m": 1.0, "pocet": 1},            # vchod 1000/2350
        {"typ": "dvere_vnitrni", "sirka_m": 0.8, "pocet": 4},          # pokoje/chodba 800/1970
        {"typ": "dvere_vnitrni", "sirka_m": 0.7, "pocet": 3},          # kúpeľňa/WC/tech 700/1970
    ],
    "pocet_oken": 9, "pocet_dveri": 9, "pocet_mistnosti": 10,
    "koty_mm": [8400, 13150, 7500, 3690, 3000, 3400, 1500, 850, 1000, 1350, 2350, 2500,
                125, 175, 1250, 1825, 800, 1970, 700, 450, 2450],
    "meritko_source": "z kót",
    "confidence_0_100": 80,
    "co_potvrdit": ["skladba steny 450 (jednovrstvový blok vs murivo+zateplenie — legenda chýba)",
                    "výška podlažia (bez rezu)", "počet okien na juhu pri terase"],
    "note": "Čistý CAD bungalov, kompletné kóty. Skladba steny 450 bez legendy = nejednoznačná.",
}

dec, msg = reconcile.quality_gate(fable_1np)
print(f"GATE 1.NP: {dec} {('— ' + msg) if msg else ''}")

# single-fóto flow: priamo pricing (bez agregácie podlaží)
r = pricing.calculate(fable_1np)

print("\n===== ROZPOČET (Fable čítanie) =====")
print(f"Trieda: {r['tier']} ({r['tier_popis']}), auto={r['tier_auto']}")
print(f"Skladba: assumed={r['assumed_skladba']}, volba={r['skladba_volba']}, "
      f"stena_raw={r['stena_mm_raw']}, zdivo={r['detected_thickness_mm']} mm")
for i in r["items"]:
    print(f"  {i['name']:<45} {i['detail']:<52} {i['total']:>10,} Kč")
li = r["labor_item"]
print(f"  {li['name']:<45} {li['detail']:<52} {li['total']:>10,} Kč")
print(f"\nZDIVO SPOLU: {r['zdivo_total']:,} Kč  ±{r['band_pct']} % => {r['range_lo']:,} – {r['range_hi']:,} Kč")
if r.get("skladba_variants"):
    print("Varianty skladby steny (prepínač v UI):")
    for v, d in r["skladba_variants"].items():
        print(f"  {v}: {d['zdivo_total']:,} Kč (zdivo {d['obvod_th']} mm)")
print("Cross-check:", json.dumps(r.get("crosscheck"), ensure_ascii=False))
print("VAROVANIA:")
for w in r["warnings"]:
    print("  •", w)

print("\n[Realita PD: PTH 44 EKO 440 mm bez zateplenia = trieda 'drahé', "
      "správna je varianta 'plné murivo'. Nosné 175 aj priečky 125 Fable trafil presne.]")
