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
GARAGE_DOOR_M2 = 10.5   # garážové vráta ~2.4×4.4 m — bez odpočtu by sme "murovali dieru"

# priečky sa nedajú spoľahlivo zmerať ani najlepším modelom (kóty na ne chýbajú)
PRICKY_INHERENT_UNC = 0.18

# inherentná neistota AI ČÍTANIA pôdorysu — aj pri vysokej confidence model varíruje
# a môže nezachytiť časť stien. Bez tohto by ±band falošne predstieral presnosť (~±9 %).
READING_BASE_UNC = 0.10
# keď zdivo vyjde VÝRAZNE NÍZKY podiel hrubej stavby → možné nezachytené steny (garáž, nosné).
# Reálne zdivo (po čestnej kalibrácii věnca/prekladov) tvorí ~22-28 % hrubej stavby (steny sú
# ~¼-⅓, zvyšok základy/stropy/strecha). Preto prah 18 % (predtým 25 = falošný poplach skoro vždy).
# Skutočné podčítanie aj tak chytá garáž-varovanie + geometrický strop obvodu, nezávisle od %.
LOW_SHARE_PCT = 18
UNDERCOUNT_UP = 0.15   # asymetrické rozšírenie HORE (reálne môže byť vyššie)

# keď poznáme PRESNÝ produkt z legendy, nehádame v celom rozsahu triedy (lacný↔drahý variant),
# zostáva len trhová/regionálna/časová odchýlka ceny KONKRÉTNEJ tehly → úzke ±okolo kc_m3.
LEGEND_PRODUCT_PRICE_UNC = 0.06

# Geometrický odhad dĺžky priečok z PLÔCH MIESTNOSTÍ (nezávislý od vizuálneho odhadu AI).
# Obvod jednej miestnosti ≈ K·√plocha (K≈4 pre štvorec, ~4.1-4.2 pre bežný obdĺžnik/chodby).
ROOM_PERIM_K = 4.1
PRICKY_UNC_AGREE = 0.11    # dva nezávislé zdroje priečok sa zhodujú → istejšie
PRICKY_UNC_DIVERGE = 0.25  # silno sa líšia → neistejšie

# Keď je podlaží > 1, ale máme len jeden pôdorys (1.NP), horné podlažia odhadujeme ako kópiu
# prízemia — neistota navyše úmerná podielu "odhadnutých" podlaží.
ASSUMED_FLOOR_UNC = 0.12

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
    ma_zateplenie_in = zatepl                       # PÔVODNÉ čítanie (zatepl sa nižšie môže zmeniť pri 'plne')
    obvod_t_raw = obvod_t                           # pôvodná hrúbka steny z výkresu (pred rozkladom skladby)
    assumed_skladba = False                         # rozdelili sme stenu→(zdivo+zateplenie) bez výslovnej skladby?
    # Voľba skladby pri NEISTOTE: 'zateplene' = murivo ~300 + izolácia (default),
    # 'plne' = celá hrúbka je murivo (napr. Porotherm 50T / Ytong 500). None → default zateplené.
    skladba_volba = params.get("skladba_volba") or "zateplene"
    # SKLADBA STENY je NEISTÁ keď NEčítame z legendy a stena je BUĎ označená ako zateplená,
    # ALEBO je HRUBÁ (>375 mm) — hrubá stena je sama o sebe nejednoznačná: plné murivo vs
    # nosné murivo + izolácia. Gemini ten istý výkres číta raz „300+zateplenie", raz „500 bez
    # zateplenia" → trigger MUSÍ pokryť oba prípady (zatepl OR hrubá), inak prepínač raz je, raz nie.
    _from_legend = (params.get("zdivo_zdroj") == "legenda")
    _thick = bool(obvod_t) and float(obvod_t) > 375
    if (zatepl or _thick) and not _from_legend:
        assumed_skladba = True
        if _thick:
            blok_mm, plna_mm = 300.0, float(obvod_t)       # Gemini dal celú (hrubú) stenu, napr. 500
        else:
            blok_mm = float(obvod_t or 300)                # Gemini dal nosný blok (~300) + flag zateplenia
            plna_mm = blok_mm + 200                         # + typická izolácia ~200 → plná stena ~500
        obvod_t_raw = plna_mm                               # "stěna ~X mm" = plná hrúbka vč. izolácie
        if skladba_volba == "plne":
            obvod_t, zatepl = plna_mm, False                # PLNÉ murivo: celá hrúbka = tehla
        else:
            obvod_t = blok_mm                               # ZATEPLENÉ: len nosný blok (izolácia sa neráta)
    elif zatepl and obvod_t and float(obvod_t) > 375:
        obvod_t = 300                                       # zateplenie Z LEGENDY + hrubá kóta → murivo 300
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
    # MUROVACIA VÝŠKA (ÚRS 801-1, viď ZNALOSTI_ROZPOCTAR.md §1–2): murivo sa počíta NETTO —
    # objem venca sa z muriva ODPOČÍTAVA (veniec je samostatná položka). Predtým sa murovalo
    # na plnú výšku podlažia A veniec sa účtoval zvlášť = dvojpočet ~0.25 m (~9 % obvod. zdiva).
    # Priečky sa murujú po spodok stropu (≈ rovnaká úroveň) → rovnaký odpočet.
    mur_vyska = max(vyska - float(_CFG.get("venec_vyska_m", 0.25)), 2.0)
    podlazi = int(params.get("pocet_podlazi") or 1)
    okna = int(params.get("pocet_oken") or 0)
    dvere = int(params.get("pocet_dveri") or 0)
    conf = int(params.get("confidence_0_100") or 40)

    zast = params.get("zastavena_plocha_m2")
    uzit = params.get("uzitna_plocha_m2")

    # === GEOMETRICKÝ STROP OBVODU (nezávislá kontrola z plochy, bez ďalšieho API volania) ===
    # Fyzika: obvod budovy NEMÔŽE byť menší než obvod štvorca s rovnakou zastavanou plochou
    # (= 4·√plocha). Keď AI prečíta obvod POD týmto minimom, časť obrysu prehliadla (časté:
    # garáž, zalomenia L/U) → dorovnaj obvod na geometrické minimum. Footprint zo zastavanej,
    # inak z úžitnej (interiér → footprint ≈ /0.82). Mieri presne na wall under-reading.
    obvod_adjusted = False
    obvod_floor_used = None
    _fs = int(params.get("_floors_summed") or 1)
    _ndiv = _fs if _fs > 1 else 1          # multi-fóto: obvod aj plocha sú SÚČET za n podlaží
    if zast:
        footprint_1np = float(zast)
    elif uzit:
        footprint_1np = (float(uzit) / _ndiv) / 0.82
    else:
        footprint_1np = None
    if footprint_1np and footprint_1np > 25 and obvod_m > 0:
        obvod_1np_read = obvod_m / _ndiv
        obvod_floor_1np = 4.0 * math.sqrt(footprint_1np)
        if obvod_1np_read < obvod_floor_1np * 0.97:    # výrazne pod fyzickým minimom = podčítanie
            obvod_m = round(obvod_m * (obvod_floor_1np / obvod_1np_read), 1)
            obvod_adjusted = True
            obvod_floor_used = round(obvod_floor_1np, 1)

    items = []

    # hrúbky: použij NAMERANÚ len ak je z kóty (spoľahlivá); inak typická pre triedu + "(odhad)".
    # Pri VARIANTE SKLADBY (assumed_skladba) sme obvod_t nastavili zámerne (300 blok vs 500 plné) →
    # MUSÍME ju použiť, inak by obe varianty spadli na typickú hrúbku triedy = rovnaká cena (bug).
    pricky_t = params.get("pricky_tloustka_mm")
    nosne_t = params.get("vnitrni_nosne_tloustka_mm")
    obvod_th_read = (z_koty or assumed_skladba) and bool(obvod_t)
    pricky_th_read = z_koty and bool(pricky_t)
    nosne_th_read = z_koty and bool(nosne_t)
    obvod_th = float(obvod_t) if obvod_th_read else tier["typ_hrubka_mm"]
    pricky_th = float(pricky_t) if pricky_th_read else pt["typ_hrubka_mm"]
    nosne_th = float(nosne_t) if nosne_th_read else 250.0

    # ===== 1. OBVODOVÉ ZDIVO (materiál = Kč/m³ × hrúbka) =====
    obvod_gross = obvod_m * mur_vyska * podlazi
    # okná sa opakujú na KAŽDOM podlaží (čítame ich z 1.NP), vchodové dvere len raz (prízemie)
    obvod_openings = okna * WINDOW_M2 * podlazi + ENTRANCE_DOOR_M2
    if params.get("ma_garaz"):
        obvod_openings += GARAGE_DOOR_M2   # vráta len raz (prízemie); preklad rieši položka nižšie
    obvod_net = max(obvod_gross - obvod_openings, 0)
    obvod_price = round(tier["kc_m3"] * obvod_th / 1000)        # Kč/m² steny pri tejto hrúbke
    obvod_mat = round(obvod_net * obvod_price)
    if assumed_skladba and skladba_volba == "plne":
        obvod_th_note = f"{int(obvod_th)} mm plné zdivo (varianta — bez zateplení)"
    elif assumed_skladba:
        obvod_th_note = (f"~{int(obvod_th)} mm zdivo (varianta — stěna {int(obvod_t_raw)} mm "
                         "vč. zateplení)")
    elif zatepl:
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
    nosne_net = nosne_m * mur_vyska * podlazi   # nosné majú málo otvorov, neodpočítavame
    nosne_price = round(tier["kc_m3"] * nosne_th / 1000)
    nosne_mat = round(nosne_net * nosne_price)
    if nosne_m > 0:
        nosne_th_note = f"{int(nosne_th)} mm" if nosne_th_read else f"~{int(nosne_th)} mm (odhad)"
        items.append(_item("Vnútorné nosné steny",
                           f"{nosne_net:.0f} m² · tl. {nosne_th_note}",
                           round(nosne_net), "m²", nosne_price, nosne_mat))

    # ===== Nezávislý odhad PRIEČOK z PLÔCH MIESTNOSTÍ (geometria) =====
    # Σ obvodov miestností = vonkajší obvod + 2×(vnútorné steny) → vnútorné = (Σobvodov − obvod)/2;
    # priečky ≈ vnútorné − nosné. Obvod miestnosti ≈ ROOM_PERIM_K·√plocha. Nezávislé od vizuálu AI.
    rooms = [float(x) for x in (params.get("plochy_mistnosti_m2") or []) if x and float(x) > 1.5]
    pricky_ai = pricky_m
    pricky_geom = None
    pricky_zdroj = "odhad AI (vizuál)"
    pricky_unc_eff = PRICKY_INHERENT_UNC
    rooms_ok = len(rooms) >= 4 and obvod_m > 0 and (not zast or sum(rooms) >= 0.55 * float(zast))
    if rooms_ok:
        room_perim = ROOM_PERIM_K * sum(math.sqrt(a) for a in rooms)
        internal_total = max(0.0, (room_perim - obvod_m) / 2)
        pricky_geom = round(max(0.0, internal_total - nosne_m), 1)
        if pricky_geom > 0 and pricky_ai > 0:
            rel = abs(pricky_geom - pricky_ai) / max(pricky_geom, pricky_ai)
            pricky_m = round((pricky_ai + pricky_geom) / 2, 1)   # blend dvoch nezávislých zdrojov
            pricky_zdroj = "plochy miestností + AI"
            if rel <= 0.25:
                pricky_unc_eff = PRICKY_UNC_AGREE          # zhoda → istejšie
            elif rel > 0.5:
                pricky_unc_eff = PRICKY_UNC_DIVERGE        # rozpor → neistejšie (+ varovanie nižšie)
        elif pricky_geom > 0 and pricky_ai == 0:
            pricky_m = pricky_geom                         # AI nedalo priečky → použi geometrický
            pricky_zdroj = "z plôch miestností"

    # ===== 3. VNÚTORNÉ PRIEČKY (materiál = Kč/m³ × hrúbka) =====
    pricky_gross = pricky_m * mur_vyska * podlazi
    # vnútorné dvere (dvere − 1 vchod) sa tiež opakujú na každom podlaží
    pricky_openings = max(0, dvere - 1) * INTERIOR_DOOR_M2 * podlazi
    pricky_net = max(pricky_gross - pricky_openings, 0)
    pricky_price = round(pt["kc_m3"] * pricky_th / 1000)
    pricky_mat = round(pricky_net * pricky_price)
    pricky_th_note = f"{int(pricky_th)} mm" if pricky_th_read else f"~{int(pricky_th)} mm (odhad)"
    items.append(_item("Vnútorné priečky",
                       f"{pricky_net:.0f} m² · tl. {pricky_th_note} (−{pricky_openings:.0f} m² dvere)",
                       round(pricky_net), "m²", pricky_price, pricky_mat))

    # ===== MALTA / LEPIDLO (zdicí + zakládací) — kupuje sa zvlášť k tvárniciam (~6 %) =====
    malta_pct = _CFG.get("malta_lepidlo_pct", 0)
    if malta_pct:
        tvarnice_mat = obvod_mat + nosne_mat + pricky_mat
        malta_cost = round(tvarnice_mat * malta_pct)
        items.append(_item("Malta / lepidlo (zdicí + zakládací)",
                           f"~{round(malta_pct*100)} % z ceny tvárnic",
                           1, "sada", malta_cost, malta_cost))

    # ===== 3. PREKLADY (paušál na otvor, bez značky) — otvory sa opakujú na každom podlaží =====
    # NOSNÝ preklad (okná + 1 vchod, v nosnej/obvodovej stene) = drahý KP7/U-profil;
    # PRIEČKOVÝ (vnútorné dvere) = lacný plochý/NEP. Bez tohto rozlíšenia sa dverami bohaté
    # / viacpodlažné domy predražovali (každý vnútorný otvor za 2200 namiesto ~700).
    nosne_otvory = okna * podlazi + 1                     # okná na každom podlaží + 1 vchod (raz)
    pricky_otvory = max(0, dvere - 1) * podlazi           # vnútorné dvere (bez vchodu) na podlaží
    preklad_nosny = _CFG["preklad_kc_otvor"]
    preklad_pricka = _CFG.get("preklad_pricka_kc_otvor", 700)
    preklad_cost = nosne_otvory * preklad_nosny + pricky_otvory * preklad_pricka
    openings = nosne_otvory + pricky_otvory
    if openings:
        items.append(_item("Preklady nad otvormi",
                           f"{nosne_otvory}× nosný (okná+vchod) + {pricky_otvory}× příčkový (dveře)",
                           openings, "otvor", round(preklad_cost / openings), preklad_cost))
    # GARÁŽOVÁ BRÁNA = veľký rozpon (~2,5–5 m), KP7 nestačí (končí na 3,5 m dĺžky) →
    # KP XL / ŽB, rádovo drahší než bežný okenný preklad (viď ZNALOSTI_ROZPOCTAR.md §4).
    # Len raz (prízemie) — garáž sa na poschodí neopakuje.
    if params.get("ma_garaz"):
        garaz_kc = _CFG.get("preklad_garaz_kc", 18000)
        items.append(_item("Preklad garážové brány ⚠odhad",
                           "velký rozpon ~2,5–5 m (KP XL / ŽB), jen přízemí",
                           1, "ks", garaz_kc, garaz_kc))

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
    # b) neistota DĹŽKY priečok (úmerne ich cenovému podielu); znížená keď ju potvrdí
    #    nezávislý odhad z plôch miestností, zvýšená keď si dva zdroje protirečia
    pricky_cost = pricky_mat + round(pricky_net * labor_pricky_m2)
    u_pricky = pricky_unc_eff * (pricky_cost / zdivo_total if zdivo_total else 0)
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
    # e) odhadnuté horné podlažia (máme len 1.NP, vyššie berieme ako kópiu prízemia)
    u_floors = ASSUMED_FLOOR_UNC * (podlazi - 1) / podlazi if podlazi > 1 else 0.0

    band = min(0.45, max(0.08, math.sqrt(u_read**2 + u_pricky**2 + u_tier**2 + u_region**2 + u_floors**2)))
    up_extra = 0.0   # asymetrické rozšírenie hore (nastaví sa pri podozrení na nezachytené steny)

    # ===== Sanity check geometrie =====
    warnings = []
    geom_ratio = None

    # PREDPOKLAD SKLADBY STENY: výkres má napr. 500 mm stenu, ale neuvádza, koľko je zdivo a
    # koľko zateplenie. Namiesto tichého hádania ponúkneme userovi OBE varianty (zateplené ~300
    # vs plné 500) ako prepínač s oboma cenami — viď koniec funkcie (skladba_variants). Žiadne
    # skryté rozšírenie pásma ani dlhé varovanie tu netreba.

    # KONTROLA OTVOROV: AI ich z pôdorysu často PODCENÍ (hlavne veľké presklenia a garážové
    # vráta ~10–12 m²). Podcenené otvory = umelo viac steny = vyššia cena. Hrubý orientačný test
    # podľa plochy podlažia (úžitná 1.NP). Soft upozornenie — nech to user prekontroluje.
    uzit_1np = float(uzit) if uzit else None
    if uzit_1np and uzit_1np > 40:
        exp_okna = uzit_1np / 14.0       # orientačne ~1 okno na 14 m² podlahy
        if okna < 0.55 * exp_okna:
            warnings.append(
                f"Otvorů se zdá málo (okna {okna}, dveře {dvere}) na plochu ~{uzit_1np:.0f} m². "
                "AI je z půdorysu často podcení — hlavně velká prosklení a GARÁŽOVÁ VRATA "
                "(~10–12 m²!), která se do otvorů nemusela započítat. Zkontrolujte počet "
                "oken/dveří níže (víc otvorů = míň zdiva = nižší cena).")
    # GARÁŽ: keď ju AI rozpoznala, pripomeň overiť že jej steny SÚ v dĺžkach (na reálnom Ytong
    # projekte garáž tvorila ~62 m² nezachytených stien = ~33 % podcenenie objemu).
    if params.get("ma_garaz"):
        warnings.append("Dům má garáž / vedlejší prostor. Ověřte, že její obvodové i vnitřní "
                        "stěny JSOU zahrnuté v délkách — bývají hlavním zdrojem podcenění zdiva. "
                        "V případě potřeby dorovnejte délky stěn níže.")
    if obvod_adjusted:
        warnings.append(f"Obvod přečtený z výkresu byl POD geometrickým minimem pro tuto zastavěnou "
                        f"plochu (AI pravděpodobně přehlédla část obrysu — garáž, zalomení). "
                        f"Dorovnali jsme obvod na ~{obvod_floor_used} m (fyzikální minimum 4·√plochy). "
                        "Reálný obvod členitého domu bývá ještě vyšší — ověřte/dorovnejte délku obvodu níže.")
    # POZOR: úžitná aj zastavaná sú plochy JEDNÉHO podlažia (úžitná = súčet miestností 1.NP) →
    # pre CELÚ budovu (konzistentne so zdivom, ktoré je × podlazi) ich treba vynásobiť podlažiami.
    # Pri multi-fóto (každé podlažie samostatná fotka) je obvod aj plocha už SÚČET za n podlaží.
    floors_summed = int(params.get("_floors_summed") or 1)
    plocha_celk = (float(zast) * podlazi) if zast else (float(uzit) * podlazi if uzit else None)
    if plocha_celk and obvod_m:
        # normalizuj na JEDNO podlažie: pri multi-fóto vydeľ súčtom podlaží, inak ×podlazi rieši podlazi
        n_div = floors_summed if floors_summed > 1 else podlazi
        plocha_1np = plocha_celk / n_div
        obvod_1np = obvod_m / floors_summed if floors_summed > 1 else obvod_m
        geom_ratio = obvod_1np / (4 * math.sqrt(plocha_1np)) if plocha_1np > 0 else None
        if geom_ratio and geom_ratio > 1.5:
            warnings.append(f"Obvod {obvod_1np:.0f} m je vysoký na plochu ~{plocha_1np:.0f} m² "
                            f"(pomer {geom_ratio:.2f}). Over, či AI nezdvojnásobila obvod / dom je členitý.")
        elif geom_ratio and geom_ratio < 0.7:
            warnings.append(f"Obvod {obvod_1np:.0f} m je nízky na plochu ~{plocha_1np:.0f} m² "
                            f"(pomer {geom_ratio:.2f}). Over, či AI prečítala celý obrys.")
    if pricky_m and obvod_m and pricky_m > obvod_m * 1.5:
        warnings.append("Dĺžka priečok je nezvyčajne vysoká voči obvodu — over odhad priečok.")
    if pricky_geom is not None and pricky_ai > 0 and pricky_unc_eff >= PRICKY_UNC_DIVERGE:
        warnings.append(f"Priečky: vizuálny odhad AI ({pricky_ai:.0f} m) a výpočet z plôch miestností "
                        f"({pricky_geom:.0f} m) sa výrazne líšia — počítam priemer, ale over dĺžku priečok.")

    # počet podlaží sa z jedného pôdorysu 1.NP NEDÁ spoľahlivo zistiť → tichý default 1 = až 2× chyba ceny.
    # Pri multi-fóto (floors_summed>1) sme každé podlažie reálne zmerali → žiadne podlažné varovanie.
    if floors_summed > 1:
        pass  # reálne zmerané podlažia, info ukáže frontend (floors_summed)
    elif podlazi <= 1:
        if params.get("ma_schodiste"):
            warnings.append("Na výkrese je SCHODIŠTĚ → dům má pravděpodobně víc podlaží, ale počítáme "
                            "s 1. Nastavte počet podlaží (nebo nahrajte fotku každého podlaží) — cena "
                            "zdiva se násobí počtem podlaží.")
        else:
            warnings.append("Počítáme s 1 nadzemním podlažím. Má dům patro nebo obytné podkroví? "
                            "Upravte počet podlaží níže (nebo nahrajte fotku každého podlaží).")
    else:
        warnings.append(f"Počítáme {podlazi} podlaží, ale analyzovali jsme jen JEDEN půdorys (1.NP). "
                        "Vyšší podlaží odhadujeme jako kopii přízemí — pokud se liší (menší patro, "
                        "podkroví, jiné dispozice), výsledek se bude lišit. Pro přesný odhad nahrajte "
                        "i půdorys dalšího podlaží. (Proto je u vícepodlažního domu rozpětí širší.)")

    # ===== Robustný odhad úžitnej plochy pre cross-check =====
    uz = None
    zast_total = float(zast) * podlazi if zast else None
    if uzit:
        uz = float(uzit) * podlazi          # úžitná 1.NP × podlažia = úžitná celej budovy
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
        if podiel and podiel > 50:
            warnings.append(f"Zdivo tvorí ~{podiel} % hrubej stavby (bežne ~22–32 %). Over hrúbku a triedu "
                            "— nie je v hrúbke započítané zateplenie? Nie je zvolená drahšia trieda než treba?")
        elif podiel and podiel < LOW_SHARE_PCT:
            # Nízky podiel sám osebe ešte neznamená chybu — lacná TENKÁ stavba ho má prirodzene.
            # Rozšír hore + ostro varuj LEN keď je aj GEOMETRICKÝ signál chýbajúcich stien:
            # chýbajú vnútorné nosné pri väčšom dome, alebo obvod vyšiel nízky na plochu.
            chyba_stien = (nosne_m == 0 and plocha_celk and plocha_celk > 120) \
                          or (geom_ratio is not None and geom_ratio < 0.85)
            if chyba_stien:
                up_extra = UNDERCOUNT_UP
                warnings.append(f"⚠ Zdivo je len ~{podiel} % hrubej stavby (bežne ~22–32 %) a geometria "
                                "napovedá, že sa z výkresu nepodarilo prečítať všetky steny (napr. garáž "
                                "alebo vnútorné nosné). Reálna cena môže byť VYŠŠIA — dorovnaj dĺžky nižšie.")
            else:
                warnings.append(f"Zdivo tvorí ~{podiel} % hrubej stavby (bežne ~22–32 %). Ak je to lacná/tenká "
                                "stavba (tenké zdivo), môže to sedieť; ak má dom navyše garáž či vnútorné "
                                "nosné steny, over/dorovnaj dĺžky stien nižšie.")

    # finálne rozpätie: dole symetricky, hore prípadne širšie (riziko podčítania stien)
    lo = round(zdivo_total * (1 - band))
    hi = round(zdivo_total * (1 + band + up_extra))
    band_pct = round((hi - lo) / (2 * zdivo_total) * 100) if zdivo_total else 0

    result = {
        "tier": tier_key,
        "tier_popis": tier["popis"],
        "tier_auto": tier_auto,
        "tier_from_legend": tier_from_legend,
        "obvod_material": params.get("obvod_material"),
        "zdivo_zdroj": params.get("zdivo_zdroj"),
        "ma_zateplenie": zatepl,
        "assumed_skladba": assumed_skladba,
        "skladba_volba": skladba_volba if assumed_skladba else None,
        "obvod_adjusted": obvod_adjusted,
        "obvod_floor_m": obvod_floor_used,
        "stena_mm_raw": int(obvod_t_raw) if obvod_t_raw else None,
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
                        "cena_triedy": round(u_tier, 3), "region": u_region,
                        "odhad_podlazi": round(u_floors, 3)},
        "pricky_zdroj": pricky_zdroj,
        "pricky_ai_m": round(pricky_ai, 1),
        "pricky_geom_m": pricky_geom,
        "floors_summed": floors_summed,
        "warnings": warnings,
        "crosscheck": crosscheck,
        "wall_area_total": round(wall_area_total),
        "used_params": {
            "obvod_m": obvod_m, "pricky_m": pricky_m, "vyska_podlazi_m": vyska,
            "vnitrni_nosne_m": nosne_m, "vnitrni_nosne_tloustka_mm": int(nosne_th),
            "pocet_podlazi": podlazi, "pocet_oken": okna, "pocet_dveri": dvere,
            "confidence_0_100": conf, "tier": tier_key,
            "obvod_tloustka_mm": int(obvod_t_raw) if obvod_t_raw else None,  # PÔVODNÁ hrúbka (round-trip)
            "tloustka_z_koty": z_koty, "ma_zateplenie": ma_zateplenie_in,
            "obvod_material_trieda": legend_tier, "obvod_material": params.get("obvod_material"),
            "zdivo_zdroj": params.get("zdivo_zdroj"),
            "uzitna_plocha_m2": uzit, "zastavena_plocha_m2": zast,
            "plochy_mistnosti_m2": rooms, "_floors_summed": floors_summed,
            "model_uncertainty": model_unc,
            "skladba_volba": skladba_volba if assumed_skladba else None,
        },
    }

    # VARIANTA SKLADBY STENY pri neistote (nehádať jedno, ukázať obe): zateplené ~300 vs plné 500.
    # Obe sa rátajú TÝM ISTÝM kódom cez rekurziu, _no_variant blokuje zacyklenie.
    if assumed_skladba and not params.get("_no_variant"):
        sv = {}
        for v in ("zateplene", "plne"):
            sub = dict(params); sub["skladba_volba"] = v; sub["_no_variant"] = True
            rv = calculate(sub)
            sv[v] = {"zdivo_total": rv["zdivo_total"], "range_lo": rv["range_lo"],
                     "range_hi": rv["range_hi"], "obvod_th": rv["detected_thickness_mm"]}
        result["skladba_variants"] = sv

    return result


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
