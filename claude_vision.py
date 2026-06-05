"""
Nezávislý DRUHÝ čitateľ výkresu (Claude Sonnet vízia).

Filozofia (ensemble / cross-check):
  Gemini = primárny čitateľ (lacný, dobrý na kóty).
  Claude = nezávislý druhý pohľad na ten istý obrázok. NEVIDÍ Geminiho čísla,
  číta výkres "naslepo". Až potom porovnáme → zhoda zdvíha confidence,
  rozdiel flagne sporné miesto (hlavne PRIEČKY = najslabší článok).

GRACEFUL: ak nie je kľúč/kredit, vráti {"available": False} a appka beží ďalej.
Náklad: vízia ~0,2–0,4 Kč/výkres (Sonnet, podľa rozlíšenia). Volá sa raz pri analyze.
"""
import base64
import json
import os
import re

import claude_review  # zdieľame _get_key()

# Najnovší Sonnet (user explicitne chcel najnovší). Override cez env (napr. claude-opus-4-8).
VISION_MODEL = os.environ.get("CLAUDE_VISION_MODEL", "claude-sonnet-4-6")
USD_CZK = 23.0

# tarify za 1M tokenov (in, out) podľa modelu — nech je report ceny reálny
_RATES = {"opus": (15.0, 75.0), "sonnet": (3.0, 15.0), "haiku": (1.0, 5.0)}


def _rates(model):
    for k, v in _RATES.items():
        if k in model:
            return v
    return _RATES["sonnet"]

# o koľko % sa smú čísla líšiť, aby sme to brali ako "zhoda"
TOL_OBVOD = 0.08    # obvod z kót býva presný → prísnejšia tolerancia
TOL_PRICKY = 0.20   # priečky sú odhad → voľnejšia


VISION_PROMPT = r"""Jsi expert na čtení stavebních půdorysů a výkaz výměr.
Dostáváš stránky projektu rodinného domu. Přečti výkres SÁM, nezávisle.

Soustřeď se hlavně na dvě čísla, která se těžko odhadují:
1. OBVODOVÉ ZDIVO (obvod_m): délka vnějšího obrysu domu v metrech.
   Čti celkové kóty (pozor na jednotky: mm vs m) a sečti vnější strany.
   U členitého (L/U) tvaru sečti všechny vnější úseky.
2. VNITŘNÍ PŘÍČKY (pricky_m): součet délek vnitřních dělících stěn v metrech.
   Toto je nejtěžší – odhadni co nejpoctivěji v poměru ke kótám, ne od oka.

Dál ověř: tloušťky stěn (mm), počet oken, počet dveří, a jestli na výkrese
vidíš kóty (pokud ne, sniž confidence – čteš jen vizuálně).

Vrať POUZE validní JSON, žádný text okolo:
{
  "obvod_m": <číslo>,
  "obvod_tloustka_mm": <číslo>,
  "pricky_m": <číslo>,
  "pricky_tloustka_mm": <číslo>,
  "pocet_oken": <číslo nebo null>,
  "pocet_dveri": <číslo nebo null>,
  "koty_videl": true/false,
  "confidence_0_100": <číslo>,
  "poznamka": "1-2 věty: jak jistý jsi a kde je riziko (hlavně u příček)"
}
Nevymýšlej si kóty které nevidíš – radši dej nižší confidence.
Až výkres přečteš, zavolej nástroj report_reading s naměřenými hodnotami."""


# vynútený štruktúrovaný výstup (Sonnet 4.6 nepodporuje prefill)
READING_TOOL = {
    "name": "report_reading",
    "description": "Nahlás hodnoty vyčítané z výkresu.",
    "input_schema": {
        "type": "object",
        "properties": {
            "obvod_m": {"type": "number"},
            "obvod_tloustka_mm": {"type": "number"},
            "pricky_m": {"type": "number"},
            "pricky_tloustka_mm": {"type": "number"},
            "pocet_oken": {"type": ["integer", "null"]},
            "pocet_dveri": {"type": ["integer", "null"]},
            "koty_videl": {"type": "boolean"},
            "confidence_0_100": {"type": "integer"},
            "poznamka": {"type": "string"},
        },
        "required": ["obvod_m", "pricky_m", "confidence_0_100", "poznamka"],
    },
}


def _rel_diff(a, b):
    """Relatívny rozdiel dvoch čísel (0 = zhoda). None ak sa nedá."""
    try:
        a, b = float(a), float(b)
    except (TypeError, ValueError):
        return None
    base = max(abs(a), abs(b))
    if base == 0:
        return 0.0
    return abs(a - b) / base


def _parse_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    return json.loads(m.group(0) if m else text)


def read_independently(images, gemini=None, model=None):
    """
    images: zoznam PNG bytes (z extract._pages_to_images).
    gemini: Geminiho extrakcia – použije sa LEN na porovnanie PO prečítaní,
            do promptu sa NEposiela (aby čítanie ostalo nezávislé).
    """
    key = claude_review._get_key()
    if not key:
        return {"available": False, "reason": "no_key", "summary": "Claude kľúč nenájdený."}
    if not images:
        return {"available": False, "reason": "no_image", "summary": "Žiadny obrázok."}

    content = []
    for img in images:
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png",
                       "data": base64.standard_b64encode(img).decode()},
        })
    content.append({"type": "text", "text": VISION_PROMPT})

    mdl = model or VISION_MODEL
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key, max_retries=0, timeout=90.0)
        resp = client.messages.create(
            model=mdl, max_tokens=1024,
            tools=[READING_TOOL],
            tool_choice={"type": "tool", "name": "report_reading"},
            messages=[{"role": "user", "content": content}],
        )
        read = next(b.input for b in resp.content if b.type == "tool_use")
        u = resp.usage
        in_rate, out_rate = _rates(mdl)
        cost = u.input_tokens / 1e6 * in_rate + u.output_tokens / 1e6 * out_rate
        out = {
            "available": True,
            "_model": mdl,
            "_cost_czk": round(cost * USD_CZK, 3),
            "_usage": {"in": u.input_tokens, "out": u.output_tokens},
            "read": read,
        }
        if gemini is not None:
            out["compare"] = _compare(gemini, read)
        return out
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        if "credit balance" in msg.lower():
            return {"available": False, "reason": "no_credit",
                    "summary": "Claude účet nemá kredit — doplň na console.anthropic.com."}
        return {"available": False, "reason": "error", "summary": f"Claude vízia chyba: {msg[:140]}"}


def _compare(gemini: dict, claude: dict) -> dict:
    """Porovná dva nezávislé čítania → zhody/rozdiely + agreement skóre."""
    checks = []
    flags = []

    def add(label, g, c, tol, unit=""):
        d = _rel_diff(g, c)
        agree = d is not None and d <= tol
        checks.append({"pole": label, "gemini": g, "claude": c,
                       "rozdiel_pct": round(d * 100, 1) if d is not None else None,
                       "zhoda": agree, "unit": unit})
        if d is not None and not agree:
            flags.append(f"{label}: Gemini {g}{unit} vs Claude {c}{unit} "
                         f"(rozdiel {d*100:.0f} %) — over.")

    add("obvod_m", gemini.get("obvod_m"), claude.get("obvod_m"), TOL_OBVOD, " m")
    add("pricky_m", gemini.get("pricky_m"), claude.get("pricky_m"), TOL_PRICKY, " m")
    add("obvod_tloustka_mm", gemini.get("obvod_tloustka_mm"),
        claude.get("obvod_tloustka_mm"), 0.20, " mm")
    add("pocet_oken", gemini.get("pocet_oken"), claude.get("pocet_oken"), 0.25)
    add("pocet_dveri", gemini.get("pocet_dveri"), claude.get("pocet_dveri"), 0.25)

    measurable = [c for c in checks if c["rozdiel_pct"] is not None]
    agree_n = sum(1 for c in measurable if c["zhoda"])
    score = round(100 * agree_n / len(measurable)) if measurable else 0

    # confidence boost/penalty pre pricing
    if score >= 80:
        verdict = "Modely sa zhodujú — odhad je dôveryhodný."
    elif score >= 50:
        verdict = "Čiastočná zhoda — over flagnuté polia."
    else:
        verdict = "Modely sa rozchádzajú — výkres je sporný, ručne over."

    return {"checks": checks, "flags": flags, "agreement_score": score, "verdict": verdict}


if __name__ == "__main__":
    import sys
    import extract
    path = sys.argv[1]
    print(f"== Gemini číta {path} ==")
    gem = extract.extract_from_plan(path)
    print(json.dumps({k: gem[k] for k in ("obvod_m", "pricky_m", "obvod_tloustka_mm",
                                           "pocet_oken", "pocet_dveri", "confidence_0_100")},
                     ensure_ascii=False))
    print("\n== Claude (nezávisle) číta ten istý výkres ==")
    imgs = extract._pages_to_images(path)
    res = read_independently(imgs, gem)
    print(json.dumps(res, ensure_ascii=False, indent=2))
