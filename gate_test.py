"""
Gate + ensemble test na PESTREJ vzorke OKÓTOVANÝCH pôdorysov.

Krok 1 (GATE, lacný Gemini pass): má výkres kóty? → ACCEPT, inak REFUSE.
Krok 2 (ENSEMBLE, len pre ACCEPT): Claude vízia + reconcile → zhoda/rozpor.

Cieľ: na vstupoch S KÓTAMI zmerať, ako veľmi sa modely (ne)zhodujú a čo žene
zvyškový rozpor. Vstup = ľubovoľný zoznam ciest (fórum JPG aj projektyrd PDF).

Použitie:  python3 gate_test.py <subor1> <subor2> ...
           python3 gate_test.py --auto   (5 fórum + 6 projektyrd vzorka)
"""
import glob
import os
import sys

import extract
import claude_vision
import reconcile

PROJEKTYRD = os.path.expanduser("~/house_projects_scraper/house_projects_data/projektyrd_floor_plans")
FORUM = "test_podorysy"


def gate(g):
    """Prototyp input-quality gate z LACNÝCH signálov (bez extra API)."""
    koty = len(g.get("koty_mm") or [])
    src = g.get("meritko_source") or "žádné"
    conf = g.get("confidence_0_100") or 0
    has_koty = src == "z kót" or koty >= 2
    if has_koty and conf >= 60:
        return "ACCEPT", f"kóty={koty}, zdroj='{src}', conf={conf}"
    if src in ("plochy m²", "měřítko/scale bar") and conf >= 45:
        return "WARN", f"bez kót ale {src} (conf={conf}) — dopočet z plôch, ±širšie"
    return "REFUSE", f"kóty={koty}, zdroj='{src}', conf={conf} → nahraj okótovaný pôdorys"


def run(paths):
    print(f"\n{'súbor':<26}{'GATE':<8}{'obvodΔ%':>8}{'príčkyΔ%':>9}{'unc':>7}  poznámka")
    print("-" * 92)
    accepted = []
    for path in paths:
        name = os.path.basename(path)[:24]
        try:
            g = extract.extract_from_plan(path)
        except Exception as e:  # noqa: BLE001
            print(f"{name:<26}{'CHYBA':<8} {str(e)[:50]}")
            continue
        decision, why = gate(g)
        if decision != "ACCEPT":
            print(f"{name:<26}{decision:<8}{'—':>8}{'—':>9}{'—':>7}  {why}")
            continue
        # ensemble len pre ACCEPT
        try:
            imgs = extract._pages_to_images(path)
            v = claude_vision.read_independently(imgs, g)
        except Exception as e:  # noqa: BLE001
            print(f"{name:<26}{'VÍZIA✗':<8} {str(e)[:50]}")
            continue
        if not v.get("available"):
            print(f"{name:<26}{'VÍZIA✗':<8} {v.get('reason')}")
            continue
        m = reconcile.merge(g, v["read"])
        od = m["diffs"]["obvod"] * 100
        pd = m["diffs"]["pricky"] * 100
        flagtxt = " | ".join(f["flags"] if isinstance(f, dict) else f for f in []) or m["verdict"][:40]
        print(f"{name:<26}{decision:<8}{od:>8.0f}{pd:>9.0f}{m['model_uncertainty']:>7.3f}  {m['verdict'][:34]}")
        accepted.append((name, g, v["read"], m))
    # súhrn rozptylu na okótovaných
    if accepted:
        ods = [a[3]["diffs"]["obvod"] for a in accepted]
        pds = [a[3]["diffs"]["pricky"] for a in accepted]
        print("-" * 92)
        print(f"OKÓTOVANÉ (n={len(accepted)}): obvod Δ medián={_med(ods)*100:.0f}% max={max(ods)*100:.0f}%"
              f" | príčky Δ medián={_med(pds)*100:.0f}% max={max(pds)*100:.0f}%")
    return accepted


def _med(xs):
    s = sorted(xs); n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


if __name__ == "__main__":
    if "--auto" in sys.argv:
        forum = sorted(glob.glob(os.path.join(FORUM, "*.jpg")))[:5]
        rd = sorted(glob.glob(os.path.join(PROJEKTYRD, "*.pdf")))[:6]
        paths = forum + rd
    else:
        paths = [a for a in sys.argv[1:] if not a.startswith("--")]
    run(paths)
