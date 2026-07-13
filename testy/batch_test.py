"""
Batch test presnosti/robustnosti extrakcie na vzorke výkresov.
Reportuje extrahované hodnoty, confidence, čítané plochy a REÁLNE tokeny + odhad ceny.

Použitie:  python3 batch_test.py            # default vzorka
           python3 batch_test.py file1 file2 ...
"""
import math
import sys

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
import extract

# Gemini 3 Pro orientačné ceny (USD / 1M tokenov) – len pre odhad nákladu
USD_IN_PER_M = 2.0
USD_OUT_PER_M = 12.0
USD_CZK = 23.0

PRJ = "/Users/robertdufala/house_projects_scraper/house_projects_data/projektyrd_floor_plans"
FAM = "/Users/robertdufala/house_projects_scraper/house_projects_data/familyhouse_floor_plans"

DEFAULT = [
    f"{PRJ}/Buk 2013.pdf",
    f"{PRJ}/Balau 2013.pdf",
    f"{PRJ}/Asan I 2013.pdf",
    f"{PRJ}/Cesmína 2013.pdf",
    f"{PRJ}/Brusinka 2013.pdf",
    f"{PRJ}/Cypřišek II 2013.pdf",
    f"{FAM}/projekt_domu_anna_3_podorys.png",
    f"{FAM}/projekt_domu_eva_7_podorys.png",
]


def sanity_ratio(obvod, plocha):
    """obvod / (4*sqrt(plocha)) ~ 1.0 pre kompaktný obdĺžnik, vyššie pre členitý tvar."""
    if not plocha or plocha <= 0:
        return None
    return obvod / (4 * math.sqrt(plocha))


def main(files):
    print(f"{'Výkres':<22}{'obvod':>7}{'priečky':>9}{'conf':>6}{'plocha':>8}{'merítko':>10}{'sanity':>8}{'tok(in/out)':>14}")
    print("-" * 94)
    tot_in = tot_out = 0
    rows = []
    for f in files:
        name = f.rsplit("/", 1)[-1][:21]
        try:
            d = extract.extract_from_plan(f)
        except Exception as e:  # noqa: BLE001
            print(f"{name:<22}  CHYBA: {e}")
            continue
        plocha = d["zastavena_plocha_m2"] or d["uzitna_plocha_m2"]
        sr = sanity_ratio(d["obvod_m"], plocha)
        u = d["_usage"]
        tot_in += u["in"]
        tot_out += u["out"]
        rows.append((name, d, sr))
        print(f"{name:<22}{d['obvod_m']:>7.0f}{d['pricky_m']:>9.0f}{d['confidence_0_100']:>6}"
              f"{(plocha or 0):>8.0f}{d['meritko_source'][:9]:>10}"
              f"{(f'{sr:.2f}' if sr else '—'):>8}{u['in']:>8}/{u['out']:<5}")

    print("-" * 94)
    cost_usd = tot_in / 1e6 * USD_IN_PER_M + tot_out / 1e6 * USD_OUT_PER_M
    n = len(rows)
    print(f"\n{n} výkresov · tokeny spolu: {tot_in:,} in / {tot_out:,} out")
    print(f"Odhad nákladu: ${cost_usd:.3f}  (~{cost_usd*USD_CZK:.1f} Kč)  =>  ~${cost_usd/max(n,1):.4f}/výkres")
    confs = [d["confidence_0_100"] for _, d, _ in rows]
    if confs:
        print(f"Confidence: min {min(confs)} · max {max(confs)} · ⌀ {sum(confs)/len(confs):.0f}")
    read_area = sum(1 for _, d, _ in rows if (d["zastavena_plocha_m2"] or d["uzitna_plocha_m2"]))
    from_koty = sum(1 for _, d, _ in rows if "kót" in d["meritko_source"])
    print(f"Prečítaná plocha: {read_area}/{n} · mierka z kót: {from_koty}/{n}")


if __name__ == "__main__":
    main(sys.argv[1:] or DEFAULT)
