"""
Kalibračný beh: Gemini vs Claude (vízia) cez všetky test výkresy.
Vypíše kompaktnú tabuľku rozdielov → nech vidíme reálny rozptyl prahov.
"""
import glob
import os

import extract
import claude_vision

PLANS = sorted(glob.glob(os.path.join("test_podorysy", "*.jpg")))


def run():
    rows = []
    total_cost = 0.0
    for path in PLANS:
        name = os.path.basename(path)
        try:
            g = extract.extract_from_plan(path)
            imgs = extract._pages_to_images(path)
            res = claude_vision.read_independently(imgs, g)
        except Exception as e:  # noqa: BLE001
            rows.append((name, f"CHYBA: {str(e)[:60]}"))
            continue
        if not res.get("available"):
            rows.append((name, f"Claude N/A: {res.get('reason')}"))
            continue
        c = res["read"]
        cmp = res["compare"]
        total_cost += res.get("_cost_czk", 0) + (g.get("_usage", {}).get("out", 0) and 1.0 or 0)
        rows.append((name, g, c, cmp, res.get("_cost_czk", 0)))
    return rows, total_cost


def fmt(rows):
    print(f"\n{'výkres':<22}{'pole':<14}{'Gemini':>9}{'Claude':>9}{'Δ%':>7}  zhoda")
    print("-" * 74)
    for r in rows:
        if len(r) == 2:
            print(f"{r[0]:<22}{r[1]}")
            continue
        name, g, c, cmp, cost = r
        first = True
        for ch in cmp["checks"]:
            label = name if first else ""
            first = False
            zh = "OK" if ch["zhoda"] else "⚠FLAG"
            gv = ch["gemini"]; cv = ch["claude"]; d = ch["rozdiel_pct"]
            print(f"{label:<22}{ch['pole']:<14}{str(gv):>9}{str(cv):>9}"
                  f"{(str(d) if d is not None else '-'):>7}  {zh}")
        print(f"{'':<22}{'→ score ' + str(cmp['agreement_score']):<14}"
              f"{'conf G=' + str(g.get('confidence_0_100')):>9} "
              f"C={c.get('confidence_0_100')}  ({cost} Kč) {cmp['verdict']}")
        print("-" * 74)


if __name__ == "__main__":
    rows, _ = run()
    fmt(rows)
