# Simulácia web-app flow: 2 pôdorysy (1.NP, 2.NP) → extrakcia FABLE (ručne, vision,
# 2026-07-10) → _aggregate_floors (kópia z app.py po refaktore) → gate → pricing.
#
# DOM: „longhouse" 24,0 × 7,5 m, 2 podlažia, ±3,120, bez garáže (parkovanie vonku).
# ⚠️ ARCHITEKTONICKÁ ŠTÚDIA BEZ VNÚTORNÝCH KÓT — jediné kóty 24000, 7500, ±3,120.
# Všetka geometria vnútri = odhad z mierky 1:100 → nízka confidence (test správania
# gate + pricing na štúdii). Detaily: test5_citanie_kompletne.md
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pricing
import reconcile

# ============ FABLE EXTRAKCIA — 1.NP ============
floor_1np = {
    "typ_stavby": "rodinny_dum",
    "konstrukce": "zdene",            # NEISTÉ — plná šedá bez šráf (môže byť aj CLT)
    "obvod_m": 63.0,                  # 2×(24,0+7,5) [z kót]
    "rozmery_celkove_m": {"sirka_m": 24.0, "dlzka_m": 7.5},
    "obvod_tloustka_mm": 300,         # z mierky ~500 celkovo → tip murivo 300 + zateplenie 200
    "stena_celkova_mm": 500,
    "tloustka_z_koty": False,         # meranie z mierky, NIE kóta!
    "ma_zateplenie": True,
    "obvod_material": None,
    "obvod_material_trieda": None,
    "zdivo_zdroj": "mierka",
    "vnitrni_nosne_m": 6.0,           # hrubšie priečne steny pri schodisku [V]
    "vnitrni_nosne_tloustka_mm": 250,
    "pricky_m": 20.0,                 # stredná zóna (WC/špajza/tech/kúpeľňa) + spálňová časť [V]
    "pricky_tloustka_mm": 125,
    "pricky_material": None,
    # 1.02 zádverie 5, 1.03 chodba 8, 1.04 WC 2, 1.05 kuchyňa+jedáleň 35, 1.06 obývačka 30,
    # 1.07 špajza 3, 1.08 technická 6, kúpeľňa stred 5, 1.09 chodba 6, 1.10 spálňa 16,
    # 1.11 kúpeľňa 10, 1.12 šatník 4, 1.13 schody 5
    "plochy_mistnosti_m2": [5, 8, 2, 35, 30, 3, 6, 5, 6, 16, 10, 4, 5],
    "uzitna_plocha_m2": 135.0,
    "zastavena_plocha_m2": 180.0,     # 24×7,5 [z kót]
    "pocet_podlazi": 1,
    "ma_schodiste": True,
    "ma_garaz": False,                # autá vonku na státí — POUČENIE z testu 4
    "ma_garazova_vrata": False,
    "vyska_podlazi_m": 3.12,          # ±0,000 → ±3,120 [K]
    "schodiste_stupne": 18,           # odhad (3120/178) — na výkrese nespočítateľné
    "schodiste_vyska_stupne_mm": 173,
    "otvory": [
        {"typ": "hs_portal", "sirka_m": 4.5, "pocet": 1, "vyska_m": 2.4},   # sever → terasa 1.15 [V]
        {"typ": "hs_portal", "sirka_m": 2.5, "pocet": 1, "vyska_m": 2.4},   # juh → terasa 1.14 [V]
        {"typ": "dvere_vchod", "sirka_m": 1.0, "pocet": 1, "vyska_m": 2.1}, # hlavný vstup z 1.01
        {"typ": "francouzske_okno", "sirka_m": 1.0, "pocet": 2, "vyska_m": 2.4},  # obývačka [V]
        {"typ": "okno", "sirka_m": 2.0, "pocet": 1, "vyska_m": 1.5},        # 1.10 štít [V]
        {"typ": "okno", "sirka_m": 1.2, "pocet": 1, "vyska_m": 1.2},        # 1.11 [V]
        {"typ": "okno", "sirka_m": 1.0, "pocet": 2, "vyska_m": 1.2},        # kuchyňa/1.02 [V]
        {"typ": "dvere_vnitrni", "sirka_m": 0.8, "pocet": 8},
        {"typ": "dvere_vnitrni", "sirka_m": 0.7, "pocet": 2},
    ],
    "pocet_oken": 8,
    "pocet_dveri": 11,
    "pocet_mistnosti": 13,
    "koty_mm": [24000, 7500],
    "meritko_source": "z mierky 1:100 (štúdia bez vnútorných kót!)",
    "confidence_0_100": 58,
    "co_potvrdit": [
        "materiál stien — plná šedá výplň bez šráf (murivo vs CLT/drevostavba?)",
        "VŠETKY vnútorné rozmery sú z mierky, nie z kót",
        "šírky HS portálov na terasy 1.14/1.15",
        "svetlé výšky (na výkrese nie sú)",
    ],
    "note": "Štúdia 1:100; kóty len 24000×7500 a ±3,120. Terasy 1.01/1.14/1.15 nezapočítané.",
}

# ============ FABLE EXTRAKCIA — 2.NP (±3,120) ============
floor_2np = {
    "typ_stavby": "rodinny_dum",
    "konstrukce": "zdene",
    "obvod_m": 63.0,
    "rozmery_celkove_m": {"sirka_m": 24.0, "dlzka_m": 7.5},
    "obvod_tloustka_mm": 300,
    "stena_celkova_mm": 500,
    "tloustka_z_koty": False,
    "ma_zateplenie": True,
    "obvod_material": None,
    "obvod_material_trieda": None,
    "zdivo_zdroj": "mierka",
    "vnitrni_nosne_m": 6.0,
    "vnitrni_nosne_tloustka_mm": 250,
    "pricky_m": 18.0,
    "pricky_tloustka_mm": 125,
    "pricky_material": None,
    # 2.01 chodba+knižnica 18, 2.02 kúpeľňa 8.5, 2.03 pracovňa 20, 2.04 kúpeľňa 9.5,
    # 2.05 izba 22, 2.06 šatník 8, 2.07 komora 5, 2.08 izba 26, 2.09 komora 5, schody 8
    "plochy_mistnosti_m2": [18, 8.5, 20, 9.5, 22, 8, 5, 26, 5, 8],
    "uzitna_plocha_m2": 130.0,
    "zastavena_plocha_m2": 180.0,
    "pocet_podlazi": 1,
    "ma_schodiste": True,
    "ma_garaz": False,
    "ma_garazova_vrata": False,
    "vyska_podlazi_m": 3.0,           # [V] — podkrovie(?), výška hore neznáma
    "otvory": [
        {"typ": "okno", "sirka_m": 1.5, "pocet": 1, "vyska_m": 1.2},   # štít západ 2.05 [V]
        {"typ": "okno", "sirka_m": 1.5, "pocet": 1, "vyska_m": 1.2},   # štít východ 2.08 [V]
        {"typ": "okno", "sirka_m": 1.0, "pocet": 2, "vyska_m": 1.2},   # pozdĺžne steny [V]
        {"typ": "okno", "sirka_m": 0.8, "pocet": 2, "vyska_m": 1.0},   # možné strešné [V]
        {"typ": "dvere_vnitrni", "sirka_m": 0.8, "pocet": 6},
        {"typ": "dvere_vnitrni", "sirka_m": 0.7, "pocet": 2},
    ],
    "pocet_oken": 6,
    "pocet_dveri": 8,
    "pocet_mistnosti": 10,
    "koty_mm": [24000, 7500, 3120],
    "meritko_source": "z mierky 1:100 (štúdia bez vnútorných kót!)",
    "confidence_0_100": 55,
    "co_potvrdit": [
        "má 2.NP šikminy? (bodkočiarkované čiary v 2.05/2.08 = hrebeň/šikmina?)",
        "okná 2.NP — na štúdii takmer nečitateľné (počty aj rozmery neisté)",
        "výška 2.NP neznáma",
    ],
    "note": "Podkrovie(?) na ±3,120; knižnica pozdĺž chodby; komín pri schodisku.",
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


floors = [floor_1np, floor_2np]
for label, fl in (("1.NP", floor_1np), ("2.NP", floor_2np)):
    dec, msg = reconcile.quality_gate(fl)
    print(f"GATE {label}: {dec} {('— ' + msg) if msg else ''}")

agg = _aggregate_floors(floors)
result = pricing.calculate(agg)

print("\n===== AGREGÁT (vstup do pricing) =====")
for k in ("obvod_m", "vnitrni_nosne_m", "pricky_m", "pocet_oken", "pocet_dveri",
          "uzitna_plocha_m2", "_floors_summed", "confidence_0_100",
          "ma_garaz", "ma_garazova_vrata", "vyska_podlazi_m"):
    print(f"  {k}: {agg.get(k)}")

print("\n===== ROZPOČET (pricing.calculate) =====")
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
