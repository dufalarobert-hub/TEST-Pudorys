"""
Eval harness — meria PRESNOSŤ extrakcie proti ground truth (nie len „čo model povedal").

Fáza 0 z PLAN_PRESNOST.md: každá zmena promptu/cien = regresný beh tohto skriptu.

  ground_truth/*.json   ručne overené výmery (L1) + voliteľná referenčná cena (L2)
  eval_history/*.json   história behov → trend medzi verziami

Použitie:
  python3 eval.py                      # všetky verified GT, 1 beh/výkres
  python3 eval.py --runs 5             # 5 behov/výkres → meria aj VARIANCE
  python3 eval.py --all                # aj neoverené GT (draft)
  python3 eval.py --label "prompt v2"  # popis verzie do histórie
"""
import json
import statistics
import sys
import time
from pathlib import Path

import extract
import pricing

ROOT = Path(__file__).parent
GT_DIR = ROOT / "ground_truth"
HIST_DIR = ROOT / "eval_history"

# Polia porovnávané proti GT: (kľúč, váha na cene — orientačne pre error budget)
FIELDS = [
    ("obvod_m", 0.45),
    ("obvod_tloustka_mm", 0.45),
    ("vnitrni_nosne_m", 0.10),
    ("pricky_m", 0.15),
    ("pocet_oken", 0.05),
    ("pocet_dveri", 0.05),
    ("zastavena_plocha_m2", 0.0),
    ("uzitna_plocha_m2", 0.0),
]

# Error budget z PLAN_PRESNOST.md (D3) — cieľové MAPE per pole
TARGETS = {
    "obvod_m": 2.0, "obvod_tloustka_mm": 5.0, "vnitrni_nosne_m": 15.0,
    "pricky_m": 15.0, "pocet_oken": 15.0, "pocet_dveri": 20.0,
    "zastavena_plocha_m2": 5.0, "uzitna_plocha_m2": 5.0,
}


def pct_err(got, truth):
    """Percentuálna odchýlka; None keď sa nedá počítať."""
    if truth in (None, 0) or got is None:
        return None
    return abs(float(got) - float(truth)) / float(truth) * 100.0


def load_gt(include_unverified=False):
    out = []
    for f in sorted(GT_DIR.glob("*.json")):
        if f.name == "TEMPLATE.json":
            continue
        gt = json.loads(f.read_text())
        if gt.get("verified") or include_unverified:
            gt["_gt_file"] = f.name
            out.append(gt)
    return out


def run_one(path, runs):
    """N behov extrakcie na jednom výkrese → per-pole zoznamy hodnôt + usage."""
    vals, usages, errs = {k: [] for k, _ in FIELDS}, [], []
    for _ in range(runs):
        try:
            d = extract.extract_from_plan(str(path))
        except Exception as e:  # noqa: BLE001
            errs.append(str(e))
            continue
        for k, _ in FIELDS:
            v = d.get(k)
            if v is not None:
                vals[k].append(float(v))
        usages.append(d.get("_usage", {}))
        last = d
    return vals, usages, errs, (last if usages else None)


def main(argv):
    runs = 1
    include_unverified = "--all" in argv
    label = ""
    if "--runs" in argv:
        runs = int(argv[argv.index("--runs") + 1])
    if "--label" in argv:
        label = argv[argv.index("--label") + 1]

    gts = load_gt(include_unverified)
    if not gts:
        print("Žiadne ground truth súbory (ground_truth/*.json s verified=true).")
        print("Najprv vytvor GT — viď ground_truth/TEMPLATE.json. Alebo --all pre drafty.")
        return 1

    print(f"Eval: {len(gts)} výkresov × {runs} behov"
          + (f" · label: {label}" if label else ""))
    print(f"{'Výkres':<26}{'pole':<22}{'GT':>9}{'model':>9}{'err%':>7}{'var%':>7}{'cieľ':>6}")
    print("-" * 88)

    all_errs = {k: [] for k, _ in FIELDS}
    all_vars = {k: [] for k, _ in FIELDS}
    price_errs = []
    report_rows = []

    for gt in gts:
        path = ROOT / gt["soubor"]
        name = Path(gt["soubor"]).name[:25]
        if not path.exists():
            print(f"{name:<26}  CHÝBA SÚBOR: {gt['soubor']}")
            continue
        vals, usages, errs, last = run_one(path, runs)
        if not last:
            print(f"{name:<26}  VŠETKY BEHY ZLYHALI: {errs[:1]}")
            continue

        row = {"soubor": gt["soubor"], "verified": bool(gt.get("verified")),
               "model": last.get("_model", "?"), "fields": {}}
        for k, _w in FIELDS:
            truth = gt.get(k)
            got = statistics.median(vals[k]) if vals[k] else None
            var = (statistics.pstdev(vals[k]) / statistics.mean(vals[k]) * 100.0
                   if len(vals[k]) > 1 and statistics.mean(vals[k]) else None)
            err = pct_err(got, truth)
            if err is not None:
                all_errs[k].append(err)
            if var is not None:
                all_vars[k].append(var)
            row["fields"][k] = {"gt": truth, "got": got, "err_pct": err, "var_pct": var}
            if truth is not None:
                flag = "" if err is None or err <= TARGETS.get(k, 10) else " ⚠"
                print(f"{name:<26}{k:<22}{truth:>9.0f}{(got if got is not None else float('nan')):>9.0f}"
                      f"{(f'{err:.1f}' if err is not None else '—'):>7}"
                      f"{(f'{var:.1f}' if var is not None else '—'):>7}"
                      f"{TARGETS.get(k, 10):>5.0f}{flag}")
            name = ""  # meno len na prvom riadku výkresu

        # L2: cena — model params (medián) → pricing vs. referenčná cena
        if gt.get("ref_cena_kc"):
            params = dict(last)
            for k, _ in FIELDS:
                if row["fields"][k]["got"] is not None:
                    params[k] = row["fields"][k]["got"]
            try:
                res = pricing.calculate(params)
                # materiálová ponuka (stavebniny/výrobca) → porovnaj len materiál;
                # 'komplet' (firma / referenčný rozpočet) → materiál + práca
                cena = (res.get("material_total") if gt.get("ref_cena_typ") == "material"
                        else res.get("zdivo_total")) or 0
                perr = pct_err(cena, gt["ref_cena_kc"])
                price_errs.append(perr)
                row["cena"] = {"got": cena, "ref": gt["ref_cena_kc"],
                               "typ": gt.get("ref_cena_typ"), "err_pct": perr}
                print(f"{'':<26}{'CENA vs ref (' + str(gt.get('ref_cena_typ')) + ')':<22}"
                      f"{gt['ref_cena_kc']:>9.0f}{cena:>9.0f}{perr:>6.1f}%")
            except Exception as e:  # noqa: BLE001
                row["cena"] = {"error": str(e)}
        report_rows.append(row)
        print()

    # ===== Súhrn =====
    print("=" * 88)
    print(f"{'pole':<22}{'MAPE':>8}{'max':>8}{'⌀var':>8}{'cieľ':>7}  n")
    for k, _ in FIELDS:
        if not all_errs[k]:
            continue
        mape = statistics.mean(all_errs[k])
        mx = max(all_errs[k])
        av = statistics.mean(all_vars[k]) if all_vars[k] else None
        ok = "✅" if mape <= TARGETS.get(k, 10) else "❌"
        print(f"{k:<22}{mape:>7.1f}%{mx:>7.1f}%"
              f"{(f'{av:.1f}%' if av is not None else '—'):>8}{TARGETS.get(k,10):>6.0f}% {ok} {len(all_errs[k])}")
    if price_errs:
        mape_c = statistics.mean(price_errs)
        within10 = sum(1 for e in price_errs if e <= 10) / len(price_errs) * 100
        print(f"\nCENA: MAPE {mape_c:.1f}% · v ±10 %: {within10:.0f}% výkresov "
              f"(cieľ ≥80 %) {'✅' if within10 >= 80 else '❌'}")

    # ===== História =====
    HIST_DIR.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = {
        "stamp": stamp, "label": label, "runs": runs,
        "models": sorted({r.get("model", "?") for r in report_rows}),
        "n_vykresov": len(report_rows),
        "mape": {k: statistics.mean(v) for k, v in all_errs.items() if v},
        "variance": {k: statistics.mean(v) for k, v in all_vars.items() if v},
        "price_mape": statistics.mean(price_errs) if price_errs else None,
        "rows": report_rows,
    }
    hist_file = HIST_DIR / f"eval_{stamp}.json"
    hist_file.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"\nUložené: {hist_file.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
