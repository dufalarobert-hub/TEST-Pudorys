"""
3-way porovnanie čítania výkresu: Gemini 3.1-pro × Claude Sonnet 4.6 × Claude Opus 4.8.
Cieľ: na sporných výkresoch zistiť, či rozpor Sonnet vs Gemini zmizne s Opusom
(= bola to slabosť modelu) alebo pretrvá (= nejednoznačnosť výkresu).
"""
import sys
import extract
import claude_vision

GROUND_TRUTH = {  # čo vieme ručne (memory): Buk obvod 2×11+2×13.5 = 49 m
    "Buk 2013.pdf": {"obvod_m": 49.0},
}


def field(label, gem, son, opu, gt=None):
    g = gem.get(label); s = son.get(label); o = opu.get(label)
    line = f"  {label:<20} Gemini={str(g):>7}  Sonnet={str(s):>7}  Opus={str(o):>7}"
    if gt is not None:
        line += f"   | pravda={gt}"
    print(line)


def run(paths):
    for path in paths:
        import os
        name = os.path.basename(path)
        print(f"\n===== {name} =====")
        gem = extract.extract_from_plan(path)
        imgs = extract._pages_to_images(path)
        son = claude_vision.read_independently(imgs, model="claude-sonnet-4-6")
        opu = claude_vision.read_independently(imgs, model="claude-opus-4-8")
        if not (son.get("available") and opu.get("available")):
            print("  CHYBA vízie:", son.get("reason"), opu.get("reason"))
            continue
        s, o = son["read"], opu["read"]
        gt = GROUND_TRUTH.get(name, {})
        field("obvod_m", gem, s, o, gt.get("obvod_m"))
        field("pricky_m", gem, s, o, gt.get("pricky_m"))
        field("obvod_tloustka_mm", gem, s, o)
        field("pocet_oken", gem, s, o)
        field("pocet_dveri", gem, s, o)
        print(f"  cena vízie: Sonnet {son['_cost_czk']} Kč · Opus {opu['_cost_czk']} Kč")


if __name__ == "__main__":
    run(sys.argv[1:])
