"""
Komentár rozpočtára — jeden lacný textový AI call na záver analýzy.

Zo šablónových varovaní a čísel zloží SÚVISLÝ ľudský odsek pre majiteľa domu:
čo je isté, kde je najväčšia neistota, na čo si dať pozor. Z kalkulačky robí poradcu.

GRACEFUL: bez ANTHROPIC_API_KEY vráti {"available": False} a appka beží ďalej
(frontend komentár jednoducho nezobrazí). Náklad: Haiku, ~0,05 Kč/analýzu.
"""
import json
import os

import claude_review  # zdieľame _get_key()

MODEL = os.environ.get("KOMENTAR_MODEL", "claude-haiku-4-5-20251001")

PROMPT = """Jsi zkušený stavební rozpočtář a píšeš krátký komentář pro majitele domu,
který si právě nechal spočítat orientační cenu hrubého zdiva z půdorysu.

Data výpočtu (JSON):
{data}

Napiš 3-5 vět česky, přátelsky ale věcně:
- co z výpočtu je spolehlivé a co je největší zdroj nejistoty (podle band_zdroje),
- 1-2 konkrétní postřehy k TOMUTO domu (členitost, garáž, tloušťka/třída zdiva, podlaží),
- co může majitel udělat pro zpřesnění (potvrdit délky, nahrát další podlaží/řez…).
ŽÁDNÉ vymyšlené údaje — jen to, co je v datech. Nepiš nadpisy ani odrážky, jen souvislý text.
Nezmiňuj interní názvy polí. Ceny neopakuj (vidí je v tabulce)."""


def compose(result: dict, extraction: dict) -> dict:
    key = claude_review._get_key()
    if not key:
        return {"available": False, "reason": "no_key"}

    data = {
        "zdivo_total": result.get("zdivo_total"),
        "band_pct": result.get("band_pct"),
        "band_zdroje": result.get("band_zdroje"),
        "tier_popis": result.get("tier_popis"),
        "warnings": result.get("warnings"),
        "crosscheck_podiel_pct": (result.get("crosscheck") or {}).get("zdivo_podiel_pct"),
        "obvod_m": extraction.get("obvod_m"),
        "obvod_tloustka_mm": extraction.get("obvod_tloustka_mm"),
        "pricky_m": extraction.get("pricky_m"),
        "pocet_podlazi": extraction.get("pocet_podlazi"),
        "ma_garaz": extraction.get("ma_garaz"),
        "ma_zateplenie": extraction.get("ma_zateplenie"),
        "confidence": extraction.get("confidence_0_100"),
        "poznamka_ai": extraction.get("note"),
    }
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key, max_retries=0, timeout=10.0)
        resp = client.messages.create(
            model=MODEL, max_tokens=400,
            messages=[{"role": "user",
                       "content": PROMPT.format(data=json.dumps(data, ensure_ascii=False))}])
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
        if not text:
            return {"available": False, "reason": "empty"}
        return {"available": True, "text": text, "_model": MODEL}
    except Exception as e:  # noqa: BLE001
        return {"available": False, "reason": "error", "detail": str(e)[:120]}
