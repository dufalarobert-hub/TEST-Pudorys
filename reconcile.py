"""
Zmierenie (reconcile) dvoch nezávislých čítaní výkresu → finálne parametre + neistota.

ARCHITEKTÚRA (kalibrované 2026-06-04 na ground truth, Gemini 3.1-pro × Sonnet 4.6 × Opus 4.8):
  - OBVOD: Gemini ≈ Opus ≈ pravda (Buk: G=50, Opus=49, pravda=49). Sonnet podčítava (43,4).
      → Gemini sa dá veriť. Druhý čitateľ = LEN Opus (Sonnet vyrábal falošné rozpory).
  - PRIEČKY: neistota je NEREDUKOVATEĽNÁ (nie sú okótované) — rozchádza sa aj Opus.
      → fixný „inherent" band na priečky (viď pricing.PRICKY_INHERENT_UNC), nie cross-check.
  - Opus je drahý (1,5–4 Kč/výkres) → volá sa len pri ESKALÁCII (needs_escalation).

Pravidlá kalibrované na 5 testovacích výkresoch (2026-06-04, Gemini vs Sonnet 4.6):
  - obvod_m: cenovo kľúčový, väčšinou spoľahlivý (Δ 0–6 %), občas vybuchne (14 %).
      → KOTVA = Gemini (v teste čítal L-tvary správne). Pri rozpore >8 % flag + širší band.
  - pricky_m: rozpor je NORMA (Δ 5–35 %, medián ~20 %). Oba modely hádajú.
      → finál = STRED dvoch čítaní; veľkosť rozporu = hlavný zdroj neistoty (ženie band).
  - hrúbky: prefer zhodu, inak Gemini.
  - okná/dvere: oba modely nespoľahlivé (Δ 27–40 %, niekedy 0). NEhýbu verdiktom;
      počty doplní/koriguje Claude TEXT vrstva (claude_review). Tu len max(oba), nikdy 0→None.

Výstup feeduje pricing.calculate() cez `model_uncertainty` (0..1) → pripočíta sa k ±bandu.
"""

import math

# váhy dôležitosti polí pre celkový verdikt (cenový dopad)
W_OBVOD = 0.35
W_PRICKY = 0.50
W_THICK = 0.15

TOL_OBVOD = 0.08     # nad tým flagni obvod (občasný výbuch na ~14 %)
TOL_THICK = 0.15

# --- Eskalácia na Opus víziu (drahé, len keď sa to oplatí) ---
ESCALATE_CONF = 70           # pod touto Geminiho confidence over druhým čítaním
ESCALATE_MODEL = "claude-opus-4-8"   # na obvode ≈ Gemini ≈ pravda; Sonnet NIE


def quality_gate(g):
    """Input-quality gate: má výkres na čom merať? (kóty + confidence).
    Vráti (decision, sprava). ACCEPT → počítaj, WARN → počítaj hrubo, REFUSE → odmietni."""
    koty = len(g.get("koty_mm") or [])
    src = g.get("meritko_source") or "žádné"
    conf = int(g.get("confidence_0_100") or 0)
    has_koty = src == "z kót" or koty >= 2
    if has_koty and conf >= 60:
        return "ACCEPT", None
    if src in ("plochy m²", "měřítko/scale bar") and conf >= 45:
        return "WARN", ("Půdorys nemá čitelné kóty — počítám z ploch/měřítka, "
                        "výsledek je hrubší (širší rozpětí).")
    # Projektová dokumentácia, v ktorej sme NENAŠLI pôdorys (žiadne kóty, nič na meranie)
    # → iná príčina ako zlý pôdorys; povedz to používateľovi presne.
    if g.get("_from_project") and float(g.get("obvod_m") or 0) == 0 and koty == 0:
        return "REFUSE", ("V nahraném dokumentu jsme nenašli půdorys (výkres 1.NP s kótami) — "
                          "vypadá to na textovou část projektu (technická zpráva apod.). "
                          "Nahrajte prosím dokument, který obsahuje půdorys, nebo rovnou "
                          "stránku s okótovaným půdorysem přízemí.")
    return "REFUSE", ("Tento půdorys neumíme spolehlivě změřit — chybí čitelné kóty "
                      "(celkové rozměry domu). Nahrajte prosím okótovaný půdorys celého "
                      "podlaží ve vyšším rozlišení. Viz návod, jaký půdorys nahrát.")


def needs_escalation(g):
    """Treba drahé druhé čítanie (Opus)? Vráti (bool, [dôvody]). Z LACNÝCH signálov."""
    reasons = []
    conf = int(g.get("confidence_0_100") or 0)
    obvod = float(g.get("obvod_m") or 0)
    src = g.get("meritko_source") or "žádné"

    if not obvod:
        reasons.append("obvod sa nenačítal")
    if conf < ESCALATE_CONF:
        reasons.append(f"nízka confidence ({conf})")
    if src not in ("z kót", "měřítko/scale bar"):
        reasons.append(f"slabý zdroj mierky ('{src}')")

    # geometria: obvod vs plocha (rovnaká logika ako pricing sanity)
    podl = int(g.get("pocet_podlazi") or 1)
    zast = g.get("zastavena_plocha_m2")
    uzit = g.get("uzitna_plocha_m2")
    plocha_celk = (float(zast) * podl) if zast else (float(uzit) if uzit else None)
    if plocha_celk and obvod and podl:
        plocha_1np = plocha_celk / podl
        if plocha_1np > 0:
            ratio = obvod / (4 * math.sqrt(plocha_1np))
            if ratio > 1.5 or ratio < 0.7:
                reasons.append(f"geometria nesedí (pomer {ratio:.2f})")

    return (len(reasons) > 0, reasons)


def _rel(a, b):
    try:
        a, b = float(a), float(b)
    except (TypeError, ValueError):
        return None
    base = max(abs(a), abs(b))
    return abs(a - b) / base if base else 0.0


def _opening(g, c):
    """Otvory: ber väčší z dvojice, ignoruj None/0 (text vrstva ich opraví)."""
    vals = [v for v in (g, c) if isinstance(v, (int, float)) and v > 0]
    return max(vals) if vals else None


def merge(gemini: dict, claude_read: dict) -> dict:
    g, c = gemini, claude_read
    flags = []

    # --- obvod: Gemini kotva, flag pri rozpore ---
    obvod_g = float(g.get("obvod_m") or 0)
    obvod_c = float(c.get("obvod_m") or 0)
    obvod_diff = _rel(obvod_g, obvod_c) or 0.0
    obvod_final = obvod_g or obvod_c
    if obvod_diff > TOL_OBVOD:
        flags.append(f"Obvod: Gemini {obvod_g:.1f} m vs Claude {obvod_c:.1f} m "
                     f"(±{obvod_diff*100:.0f} %) — over hlavné kóty.")

    # --- priečky: stred dvoch, rozpor = hlavná neistota ---
    pricky_g = float(g.get("pricky_m") or 0)
    pricky_c = float(c.get("pricky_m") or 0)
    pricky_diff = _rel(pricky_g, pricky_c) or 0.0
    both = [v for v in (pricky_g, pricky_c) if v > 0]
    pricky_final = round(sum(both) / len(both), 1) if both else 0.0
    pricky_lo, pricky_hi = (min(both), max(both)) if both else (0, 0)
    if pricky_diff > 0.12:
        flags.append(f"Priečky: modely {pricky_lo:.0f}–{pricky_hi:.0f} m "
                     f"(±{pricky_diff*100:.0f} %) — najmenej istá položka, zváž potvrdenie.")

    # --- hrúbka obvod: zhoda, inak Gemini ---
    th_g = int(g.get("obvod_tloustka_mm") or 0)
    th_c = int(c.get("obvod_tloustka_mm") or 0)
    thick_diff = _rel(th_g, th_c) or 0.0
    thick_final = th_g or th_c
    if thick_diff > TOL_THICK and th_g and th_c:
        flags.append(f"Hrúbka obvodu: {th_g} vs {th_c} mm — over typ tvárnice.")

    # --- otvory: nedôverujeme vízii, text vrstva opraví ---
    okna = _opening(g.get("pocet_oken"), c.get("pocet_oken"))
    dvere = _opening(g.get("pocet_dveri"), c.get("pocet_dveri"))

    # --- celková modelová neistota (0..1) — vážená, priečky dominujú ---
    model_uncertainty = round(
        W_OBVOD * obvod_diff + W_PRICKY * pricky_diff + W_THICK * thick_diff, 3)

    # vážená zhoda v % pre human verdikt
    agree = round(100 * (1 - min(model_uncertainty, 1.0)))
    if model_uncertainty <= 0.06:
        verdict = "Modely sa zhodujú — odhad dôveryhodný."
    elif model_uncertainty <= 0.15:
        verdict = "Drobné rozdiely — orientačne v poriadku, priečky over."
    else:
        verdict = "Modely sa rozchádzajú (hlavne priečky) — beriem ako rozpätie, over."

    return {
        "params": {
            "obvod_m": obvod_final,
            "obvod_tloustka_mm": thick_final,
            "pricky_m": pricky_final,
            "pricky_tloustka_mm": int(g.get("pricky_tloustka_mm")
                                      or c.get("pricky_tloustka_mm") or 100),
            "pocet_oken": okna,
            "pocet_dveri": dvere,
        },
        "model_uncertainty": model_uncertainty,
        "agreement_pct": agree,
        "verdict": verdict,
        "flags": flags,
        "spreads": {
            "obvod_m": [round(min(obvod_g, obvod_c), 1), round(max(obvod_g, obvod_c), 1)],
            "pricky_m": [round(pricky_lo, 1), round(pricky_hi, 1)],
        },
        "diffs": {"obvod": round(obvod_diff, 3), "pricky": round(pricky_diff, 3),
                  "thick": round(thick_diff, 3)},
    }
