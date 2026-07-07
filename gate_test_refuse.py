"""Gate test: negatívne súbory MUSIA byť REFUSE, degradovaný NESMIE byť REFUSE."""
import sys, extract, reconcile
NEG = ["plan_49667100.jpg", "plan_49667101.jpg", "plan_49675097.jpg", "plan_49675098.jpg",
       "plan_49675099.jpg", "plan_49675100.jpg", "plan_49682792.jpg"]
DEG = ["plan_49681853.jpg"]
ok = bad = 0
for f, expect_refuse in [(x, True) for x in NEG] + [(x, False) for x in DEG]:
    try:
        ex = extract.extract_from_plan(f"test_podorysy/{f}")
        dec, msg = reconcile.quality_gate(ex)
    except Exception as e:
        dec, msg = "ERROR", str(e)[:80]
    is_refuse = dec == "REFUSE"
    passed = (is_refuse == expect_refuse)
    ok += passed; bad += not passed
    exp = "REFUSE" if expect_refuse else "NIE-REFUSE"
    print(f"{'✅' if passed else '❌'} {f}: {dec} (očak. {exp})  {(msg or '')[:70]}")
print(f"\n{ok}/8 správne, {bad} zlyhaní")
