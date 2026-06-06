"""
Výkaz výmer + cena HRUBÉHO ZDIVA — brand-agnostic tier model.

Cihlomat je NEZÁVISLÝ portál → nedávame do popredia výrobcu. Užívateľ volí
cenovú triedu (lacné / stredné / drahé); cena = REÁLNA RETAIL cena referenčnej
tehly v triede (stred), trhový rozsah triedy kŕmi ±band. LEN ZDIVO (bez zateplenia).

Metodika (ÚRS 801-1): zdivo v m² steny, otvory sa odčítavajú, materiál a práca oddelené.
Ceny editovateľné v cihly.json (research-grounded retail, 2026-06-04). Zdroje viď tam.
"""
import json
import math
import os

_CFG = json.load(open(os.path.join(os.path.dirname(__file__), "cihly.json"), encoding="utf-8"))

# Priemerné plochy otvorov (m²) pre odpočet zo steny
WINDOW_M2 = 1.5
ENTRANCE_DOOR_M2 = 2.0
INTERIOR_DOOR_M2 = 1.6

# priečky sa nedajú spoľahlivo zmerať ani najlepším modelom (kóty na ne chýbajú)
PRICKY_INHERENT_UNC = 0.18

# inherentná neistota AI ČÍTANIA pôdorysu — aj pri vysokej confidence model varíruje
# a môže nezachytiť časť stien. Bez tohto by ±band falošne predstieral presnosť (~±9 %).
READING_BASE_UNC = 0.10
# keď zdivo vyjde NÍZKY podiel hrubej stavby → pravdepodobne nezachytené steny (garáž, nosné)
LOW_SHARE_PCT = 25
UNDERCOUNT_UP = 0.15   # asymetrické rozšírenie HORE (reálne môže byť vyššie)

# keď poznáme PRESNÝ produkt z legendy, nehádame v celom rozsahu triedy (lacný↔drahý variant),
# zostáva len trhová/regionálna/časová odchýlka ceny KONKRÉTNEJ tehly → úzke ±okolo kc_m3.
LEGEND_PRODUCT_PRICE_UNC = 0.06

# Cross-check: priamy trhový benchmark hrubej stavby (Kč/m² podlahy) — viď cihly.json

# spätná kompatibilita starých názvov systému → tier
_LEGACY = {"porotherm": "drahe", "ytong": "lacne"}


def _tier_from_thickness(mm):
    """Hrúbka MURIVA → návrh triedy. Hrúbka nepripne materiál (rovnaká hrúbka =
    rôzny materiál), preto default = bežné zdivo; lacné = manuálna voľba usera."""
    try:
        t = float(mm)
    except (TypeError, ValueError):
        return None
    if t <= 0:
        return None
    if t >= 440:
        return "drahe"        # hrubý jednovrstvý blok = pravdepodobne tepelnoizolačný
    return "stredne"          # bežné zdivo (Ytong Standard / Porotherm Profi, ~4300-4500 Kč/m³)


def _tier_key(name, thickness_mm=None):
    if name:
        name = _LEGACY.get(name.lower(), name.lower())
        if name in _CFG["obvodove_tiery"]:
            return name, False        # explicitná voľba usera
    auto = _tier_from_thickness(thickness_mm)
    if auto:
        return auto, True             # odvodené z hrúbky na výkrese
    return "stredne", False


def calculate(params: dict) -> dict:
    obvod_t = params.get("obvod_tloustka_mm")
    z_koty = bool(params.get("tloustka_z_koty"))   # je hrúbka daná VÝSLOVNOU kótou?
    zatepl = bool(params.get("ma_zateplenie"))     # stena = murivo + zateplenie?
    # SKLADANÁ STENA (deterministické pravidlo): zateplenie + veľká hrúbka (>375 mm) =
    # murivo + izolácia. Murivo je NORMÁLNY blok (~300), NIE 450mm jednovrstvý tepelný
    # blok → nesmie sa cenť 450 ani auto-vybrať trieda Dražší. (Tepelný blok nemá
    # samostatné zateplenie — tieto dve veci si protirečia.)
    if zatepl and obvod_t and float(obvod_t) > 375:
        obvod_t = 300
    # PRIORITA triedy: user explicit > MATERIÁL Z LEGENDY > heuristika z hrúbky > stredne
    legend_tier = params.get("obvod_material_trieda")
    user_tier = params.get("tier") or params.get("system")
    tier_key, tier_auto = _tier_key(user_tier or legend_tier, obvod_t if z_koty else None)
    tier_from_legend = bool(legend_tier and not user_tier)
    tier = _CFG["obvodove_tiery"][tier_key]
    pt = _CFG["priecky_tier"]
    po = _CFG["praca_obvod"]
    pp = _CFG["praca_priecky"]

    obvod_m = float(params.get("obvod_m") or 0)
    pricky_m = float(params.get("pricky_m") or 0)
    vyska = float(params.get("vyska_podlazi_m") or _CFG["vyska_podlazia_m"])
    podlazi = int(params.get("pocet_podlazi") or 1)
    okna = int(params.get("pocet_oken") or 0)
    dvere = int(params.get("pocet_dveri") or 0)
    conf = int(params.get("confidence_0_100") or 40)

    zast = params.get("zastavena_plocha_m2")
    uzit = params.get("uzitna_plocha_m2")

    items = []

    # hrúbky: použij NAMERANÚ len ak je z kóty (spoľahlivá); inak typická pre triedu + "(odhad)"
    pricky_t = params.get("pricky_tloustka_mm")
    nosne_t = params.get("vnitrni_nosne_tloustka_mm")
    obvod_th_read = z_koty and bool(obvod_t)
    pricky_th_read = z_koty and bool(pricky_t)
    nosne_th_read = z_koty and bool(nosne_t)
    obvod_th = float(obvod_t) if obvod_th_read else tier["typ_hrubka_mm"]
    pricky_th = float(pricky_t) if pricky_th_read else pt["typ_hrubka_mm"]
    nosne_th = float(nosne_t) if nosne_th_read else 250.0

    # ===== 1. OBVODOVÉ ZDIVO (materiál = Kč/m³ × hrúbka) =====
    obvod_gross = obvod_m * vyska * podlazi
    # okná sa opakujú na KAŽDOM podlaží (čítame ich z 1.NP), vchodové dvere len raz (prízemie)
    obvod_openings = okna * WINDOW_M2 * podlazi + ENTRANCE_DOOR_M2
    obvod_net = max(obvod_gross - obvod_openings, 0)
    obvod_price = round(tier["kc_m3"] * obvod_th / 1000)        # Kč/m² steny pri tejto hrúbke
    obvod_mat = round(obvod_net * obvod_price)
    if zatepl:
        obvod_th_note = f"{int(obvod_th)} mm zdivo (+ zateplení)"
    elif obvod_th_read:
        obvod_th_note = f"{int(obvod_th)} mm"
    else:
        obvod_th_note = f"~{int(obvod_th)} mm (odhad)"
    items.append(_item(f"Obvodové zdivo — {tier['popis']}",
                       f"{obvod_net:.0f} m² · tl. {obvod_th_note} (−{obvod_openings:.0f} m² otvory)",
                       round(obvod_net), "m²", obvod_price, obvod_mat))

    # ===== 2. VNÚTORNÉ NOSNÉ STENY (rovnaký materiál ako obvod, vlastná hrúbka) =====
    nosne_m = float(params.get("vnitrni_nosne_m") or 0)
    nosne_net = nosne_m * vyska * podlazi   # nosné majú málo otvorov, neodpočítavame
    nosne_price = round(tier["kc_m3"] * nosne_th / 1000)
    nosne_mat = round(nosne_net * nosne_price)
    if nosne_m > 0:
        nosne_th_note = f"{int(nosne_th)} mm" if nosne_th_read else f"~{int(nosne_th)} mm (odhad)"
        items.append(_item("Vnútorné nosné steny",
                           f"{nosne_net:.0f} m² · tl. {nosne_th_note}",
                           round(nosne_net), "m²", nosne_price, nosne_mat))

    # ===== 3. VNÚTORNÉ PRIEČKY (materiál = Kč/m³ × hrúbka) =====
    pricky_gross = pricky_m * vyska * podlazi
    # vnútorné dvere (dvere − 1 vchod) sa tiež opakujú na každom podlaží
    pricky_openings = max(0, dvere - 1) * INTERIOR_DOOR_M2 * podlazi
    pricky_net = max(pricky_gross - pricky_openings, 0)
    pricky_price = round(pt["kc_m3"] * pricky_th / 1000)
    pricky_mat = round(pricky_net * pricky_price)
    pricky_th_note = f"{int(pricky_th)} mm" if pricky_th_read else f"~{int(pricky_th)} mm (odhad)"
    items.append(_item("Vnútorné priečky",
                       f"{pricky_net:.0f} m² · tl. {pricky_th_note} (−{pricky_openings:.0f} m² dvere)",
                       round(pricky_net), "m²", pricky_price, pricky_mat))

    # ===== 3. PREKLADY (paušál na otvor, bez značky) — otvory sa opakujú na každom podlaží =====
    openings = (okna + dvere) * podlazi
    preklad_cost = openings * _CFG["preklad_kc_otvor"]
    if openings:
        items.append(_item("Preklady nad otvormi", f"{openings}× otvor (okná + dvere)",
                           openings, "otvor", _CFG["preklad_kc_otvor"], preklad_cost))

    # ===== 4. ŽB VĚNEC — nielen po obvode, ale aj nad vnútornými nosnými stenami (nesú strop) =====
    venec_m = (obvod_m + nosne_m) * podlazi
    venec_cost = round(venec_m * _CFG["venec_kc_m"])
    venec_detail = (f"{obvod_m + nosne_m:.0f} m (obvod + nosné) × {podlazi} podl."
                    if nosne_m > 0 else f"{obvod_m:.0f} m × {podlazi} podl.")
    items.append(_item("Železobetónový věnec ⚠odhad", venec_detail,
                       round(venec_m), "m", _CFG["venec_kc_m"], venec_cost))

    material_total = sum(i["total"] for i in items)

    # ===== 6. MURÁRSKA PRÁCA (sadzba RASTIE s hrúbkou; NEmení sa podľa triedy) =====
    labor_obvod_m2 = po["base_kc_m2"] + po["per_mm"] * obvod_th
    labor_nosne_m2 = po["base_kc_m2"] + po["per_mm"] * nosne_th     # nosné = ako obvod
    labor_pricky_m2 = pp["base_kc_m2"] + pp["per_mm"] * pricky_th
    labor = round(obvod_net * labor_obvod_m2 + nosne_net * labor_nosne_m2
                  + pricky_net * labor_pricky_m2)
    wall_area_total = obvod_net + nosne_net + pricky_net
    labor_item = _item("Murárske práce (zdenie)",
                       f"{wall_area_total:.0f} m² stien (sadzba podľa hrúbky)",
                       round(wall_area_total), "m²",
                       round(labor / wall_area_total) if wall_area_total else 0, labor)

    zdivo_total = material_total + labor

    # ===== ±BAND: nezávislé zdroje neistoty v KVADRATÚRE =====
    # a) čítanie výkresu: inherentná neistota AI + (chýbajúca) confidence + Opus rozpor
    model_unc = float(params.get("model_uncertainty") or 0)
    u_read = READING_BASE_UNC + (100 - conf) / 250.0 + model_unc * 0.7
    # b) neredukovateľná neistota DĹŽKY priečok (úmerne ich cenovému podielu)
    pricky_cost = pricky_mat + round(pricky_net * labor_pricky_m2)
    u_pricky = PRICKY_INHERENT_UNC * (pricky_cost / zdivo_total if zdivo_total else 0)
    # c) CENOVÝ rozsah zvolenej triedy (retail Kč/m³ od–do × hrúbka) premietnutý na celok.
    #    Keď je obvodový materiál čítaný PRESNE z legendy (a triedu si user neprepísal), nehádame
    #    v celom rozsahu triedy — pre obvod/nosné použijeme úzke ±okolo kc_m3 (známy produkt).
    base = zdivo_total - obvod_mat - nosne_mat - pricky_mat
    if tier_from_legend and params.get("zdivo_zdroj") == "legenda":
        kc = tier["kc_m3"]
        tlo, thi = kc * (1 - LEGEND_PRODUCT_PRICE_UNC), kc * (1 + LEGEND_PRODUCT_PRICE_UNC)
    else:
        tlo, thi = tier["kc_m3_rozsah"]
    plo, phi = pt["kc_m3_rozsah"]
    z_lo = base + (obvod_net * obvod_th + nosne_net * nosne_th) * tlo / 1000 \
                + pricky_net * plo * pricky_th / 1000
    z_hi = base + (obvod_net * obvod_th + nosne_net * nosne_th) * thi / 1000 \
                + pricky_net * phi * pricky_th / 1000
    u_tier = (z_hi - z_lo) / (2 * zdivo_total) if zdivo_total else 0
    # d) regionálny rozptyl (Praha/Brno +10-20 %, práca, metodika)
    u_region = _CFG["regionalna_neistota"]

    band = min(0.45, max(0.08, math.sqrt(u_read**2 + u_pricky**2 + u_tier**2 + u_region**2)))
    up_extra = 0.0   # asymetrické rozšírenie hore (nastaví sa pri podozrení na nezachytené steny)

    # ===== Sanity check geometrie =====
    warnings = []
    geom_ratio = None
    plocha_celk = (float(zast) * podlazi) if zast else (float(uzit) if uzit else None)
    if plocha_celk and obvod_m:
        plocha_1np = plocha_celk / podlazi
        geom_ratio = obvod_m / (4 * math.sqrt(plocha_1np)) if plocha_1np > 0 else None
        if geom_ratio and geom_ratio > 1.5:
            warnings.append(f"Obvod {obvod_m:.0f} m je vysoký na plochu ~{plocha_1np:.0f} m² "
                            f"(pomer {geom_ratio:.2f}). Over, či AI nezdvojnásobila obvod / dom je členitý.")
        elif geom_ratio and geom_ratio < 0.7:
            warnings.append(f"Obvod {obvod_m:.0f} m je nízky na plochu ~{plocha_1np:.0f} m² "
                            f"(pomer {geom_ratio:.2f}). Over, či AI prečítala celý obrys.")
    if pricky_m and obvod_m and pricky_m > obvod_m * 1.5:
        warnings.append("Dĺžka priečok je nezvyčajne vysoká voči obvodu — over odhad priečok.")

    # počet podlaží sa z jedného pôdorysu 1.NP NEDÁ spoľahlivo zistiť → tichý default 1 = až 2× chyba ceny.
    if podlazi <= 1:
        if params.get("ma_schodiste"):
            warnings.append("Na výkrese je SCHODIŠTĚ → dům má pravděpodobně víc podlaží, ale počítáme "
                            "s 1. Nastavte počet podlaží — cena zdiva se násobí počtem podlaží.")
        else:
            warnings.append("Počítáme s 1 nadzemním podlažím. Má dům patro nebo obytné podkroví? "
                            "Upravte počet podlaží níže — cena zdiva se počtem podlaží násobí.")

    # ===== Robustný odhad úžitnej plochy pre cross-check =====
    uz = None
    zast_total = float(zast) * podlazi if zast else None
    if uzit:
        uz = float(uzit)
        if zast_total and uz < 0.5 * zast_total:
            warnings.append(f"Úžitná plocha {uz:.0f} m² je nízka voči zastavanej {zast_total:.0f} m² "
                            "— AI ju asi podčítala; cross-check beriem zo zastavanej.")
            uz = round(zast_total * 0.82)
    elif zast_total:
        uz = round(zast_total * 0.82)

    # ===== Cross-check celej hrubej stavby (PRIAMY trhový benchmark Kč/m²) =====
    crosscheck = None
    if uz:
        b_lo, b_hi = _CFG["sanity_hruba_stavba_kc_m2"]
        b_avg = (b_lo + b_hi) / 2
        podiel = round(100 * zdivo_total / (uz * b_avg)) if uz * b_avg else None
        crosscheck = {
            "plocha_m2": round(uz),
            "min": round(uz * b_lo),
            "avg": round(uz * b_avg),
            "max": round(uz * b_hi),
            "unit_avg": round(b_avg),
            "zdivo_podiel_pct": podiel,
            "note": (f"Odhad CELEJ hrubej stavby ≈ {round(uz)} m² × {b_lo//1000}–{b_hi//1000} tis. Kč/m² "
                     "(trhový benchmark zděného RD: základy, zdivo, stropy, krov+strecha). "
                     f"Vyššie spočítané zdivo je z toho ~{podiel} % — zvyšok sú základy, stropy a strecha."),
        }
        if podiel and podiel > 55:
            warnings.append(f"Zdivo tvorí ~{podiel} % hrubej stavby (bežne 30–45 %). Over hrúbku a triedu "
                            "— nie je v hrúbke započítané zateplenie? Nie je zvolená drahšia trieda než treba?")
        elif podiel and podiel < LOW_SHARE_PCT:
            # Nízky podiel sám osebe ešte neznamená chybu — lacná TENKÁ stavba ho má prirodzene.
            # Rozšír hore + ostro varuj LEN keď je aj GEOMETRICKÝ signál chýbajúcich stien:
            # chýbajú vnútorné nosné pri väčšom dome, alebo obvod vyšiel nízky na plochu.
            chyba_stien = (nosne_m == 0 and plocha_celk and plocha_celk > 120) \
                          or (geom_ratio is not None and geom_ratio < 0.85)
            if chyba_stien:
                up_extra = UNDERCOUNT_UP
                warnings.append(f"⚠ Zdivo je len ~{podiel} % hrubej stavby (bežne 30–45 %) a geometria "
                                "napovedá, že sa z výkresu nepodarilo prečítať všetky steny (napr. garáž "
                                "alebo vnútorné nosné). Reálna cena môže byť VYŠŠIA — dorovnaj dĺžky nižšie.")
            else:
                warnings.append(f"Zdivo tvorí ~{podiel} % hrubej stavby (bežne 30–45 %). Ak je to lacná/tenká "
                                "stavba (tenké zdivo), môže to sedieť; ak má dom navyše garáž či vnútorné "
                                "nosné steny, over/dorovnaj dĺžky stien nižšie.")

    # finálne rozpätie: dole symetricky, hore prípadne širšie (riziko podčítania stien)
    lo = round(zdivo_total * (1 - band))
    hi = round(zdivo_total * (1 + band + up_extra))
    band_pct = round((hi - lo) / (2 * zdivo_total) * 100) if zdivo_total else 0

    return {
        "tier": tier_key,
        "tier_popis": tier["popis"],
        "tier_auto": tier_auto,
        "tier_from_legend": tier_from_legend,
        "obvod_material": params.get("obvod_material"),
        "zdivo_zdroj": params.get("zdivo_zdroj"),
        "ma_zateplenie": zatepl,
        "detected_thickness_mm": int(obvod_th) if obvod_th_read else None,
        "neobsahuje": _CFG["neobsahuje"],
        "items": items,
        "labor_item": labor_item,
        "material_total": material_total,
        "labor_total": labor,
        "zdivo_total": zdivo_total,
        "band_pct": band_pct,
        "range_lo": lo,
        "range_hi": hi,
        "band_zdroje": {"citanie": round(u_read, 3), "priecky": round(u_pricky, 3),
                        "cena_triedy": round(u_tier, 3), "region": u_region},
        "warnings": warnings,
        "crosscheck": crosscheck,
        "wall_area_total": round(wall_area_total),
        "used_params": {
            "obvod_m": obvod_m, "pricky_m": pricky_m, "vyska_podlazi_m": vyska,
            "vnitrni_nosne_m": nosne_m, "vnitrni_nosne_tloustka_mm": int(nosne_th),
            "pocet_podlazi": podlazi, "pocet_oken": okna, "pocet_dveri": dvere,
            "confidence_0_100": conf, "tier": tier_key,
            "obvod_tloustka_mm": int(obvod_t) if obvod_t else None,
            "tloustka_z_koty": z_koty, "ma_zateplenie": zatepl,
            "obvod_material_trieda": legend_tier, "obvod_material": params.get("obvod_material"),
            "zdivo_zdroj": params.get("zdivo_zdroj"),
            "uzitna_plocha_m2": uzit, "zastavena_plocha_m2": zast,
            "model_uncertainty": model_unc,
        },
    }


def _item(name, detail, qty, unit, price, total):
    return {"name": name, "detail": detail, "qty": qty, "unit": unit,
            "price": round(price), "total": round(total)}


if __name__ == "__main__":
    for t in ("lacne", "stredne", "drahe"):
        d = calculate({"obvod_m": 49, "pricky_m": 40, "vyska_podlazi_m": 2.8, "pocet_podlazi": 1,
                       "pocet_oken": 9, "pocet_dveri": 9, "zastavena_plocha_m2": 137.5,
                       "uzitna_plocha_m2": 105.8, "confidence_0_100": 85, "tier": t})
        print(f"\n[{d['tier_popis']}] Zdivo: {d['zdivo_total']:,} Kč "
              f"(mat {d['material_total']:,} + práca {d['labor_total']:,}) "
              f"±{d['band_pct']}% => {d['range_lo']:,}–{d['range_hi']:,} Kč")
        print("   band zdroje:", d["band_zdroje"])
        for i in d["items"]:
            print(f"   {i['name']:<40} {i['detail']:<28} {i['total']:>9,} Kč")
        print(f"   {'Murárske práce':<40} {d['labor_item']['detail']:<28} {d['labor_total']:>9,} Kč")
