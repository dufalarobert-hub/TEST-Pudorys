"""
Claude reasoning/validačná vrstva (hybrid: Gemini číta → Claude kontroluje).

GRACEFUL: ak nie je kľúč alebo účet nemá kredit, vráti {"available": False, ...}
a appka pokračuje Gemini-only. Aktivuje sa automaticky keď bude kredit.

Claude dostane extrahované parametre (text, žiadny obrázok = lacné) a:
  - skontroluje geometriu (obvod vs plocha),
  - doplní chýbajúce otvory (okná/dvere) ak ich Gemini nenašiel,
  - upozorní na nezrovnalosti, navrhne opravené hodnoty + confidence.
"""
import json
import os
import re

MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")  # text validácia: Sonnet stačí

# orientačné ceny Sonnet (USD/1M), len pre report nákladu
USD_IN, USD_OUT, USD_CZK = 3.0, 15.0, 23.0


def _get_key():
    """ANTHROPIC_API_KEY z env (produkcia). Voliteľne lokálny .env súbor cez
    ANTHROPIC_ENV_FILE (dev). Ak nič → None a Claude vrstva sa graceful preskočí."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key.strip()
    env_file = os.environ.get("ANTHROPIC_ENV_FILE")
    if env_file and os.path.exists(env_file):
        for line in open(env_file, encoding="utf-8"):
            if line.startswith("ANTHROPIC_API_KEY"):
                v = line.split("=", 1)[1].strip().strip('"').strip("'")
                if v:
                    return v
    return None


PROMPT = """Jsi stavební rozpočtář. Z půdorysu RD AI (Gemini) vyčetla tyto parametry:
{data}

Zkontroluj je a vrať POUZE validní JSON:
{{
  "issues": ["konkrétní nesrovnalosti, max 4; prázdné pokud OK"],
  "suggestions": {{ "pole": nová_hodnota }},   // jen pole která bys změnil (pocet_oken, pocet_dveri, obvod_tloustka_mm, pricky_tloustka_mm, pricky_m), jinak prázdný objekt
  "refined_confidence_0_100": <číslo>,
  "summary": "1-2 věty hodnocení pro majitele domu"
}}
Pravidla: obvod by měl ~odpovídat 2*(šířka+délka) z plochy; pokud okna=0 nebo dvere=0 u domu s plochou, odhadni realisticky (~1 okno/12 m², 1 dveře/místnost). Tloušťky: obvodové 300-450, příčky 80-150 mm. Neměň obvod_m pokud sedí s kótami."""


def review(extraction: dict) -> dict:
    key = _get_key()
    if not key:
        return {"available": False, "reason": "no_key", "summary": "Claude kľúč nenájdený."}

    # pošli len relevantné polia (lacné, žiadny obrázok)
    fields = ["obvod_m", "obvod_tloustka_mm", "pricky_m", "pricky_tloustka_mm",
              "uzitna_plocha_m2", "zastavena_plocha_m2", "pocet_podlazi",
              "pocet_oken", "pocet_dveri", "pocet_mistnosti", "confidence_0_100"]
    data = {k: extraction.get(k) for k in fields}

    try:
        import anthropic
        # max_retries=0 + timeout: keď nie je kredit, padni HNEĎ (žiadne 60s retry)
        client = anthropic.Anthropic(api_key=key, max_retries=0, timeout=8.0)
        resp = client.messages.create(
            model=MODEL, max_tokens=600,
            messages=[{"role": "user", "content": PROMPT.format(data=json.dumps(data, ensure_ascii=False))}],
        )
        text = resp.content[0].text
        m = re.search(r"\{.*\}", text, re.DOTALL)
        out = json.loads(m.group(0) if m else text)
        u = resp.usage
        cost = u.input_tokens / 1e6 * USD_IN + u.output_tokens / 1e6 * USD_OUT
        out["available"] = True
        out["_model"] = MODEL
        out["_cost_czk"] = round(cost * USD_CZK, 3)
        return out
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        if "credit balance" in msg.lower():
            return {"available": False, "reason": "no_credit",
                    "summary": "Claude účet nemá kredit — doplň na console.anthropic.com (Plans & Billing)."}
        return {"available": False, "reason": "error", "summary": f"Claude chyba: {msg[:120]}"}


if __name__ == "__main__":
    print(json.dumps(review({"obvod_m": 56, "obvod_tloustka_mm": 300, "pricky_m": 42,
                             "pricky_tloustka_mm": 115, "uzitna_plocha_m2": 121,
                             "zastavena_plocha_m2": 150, "pocet_podlazi": 1,
                             "pocet_oken": 0, "pocet_dveri": 0, "pocet_mistnosti": 11,
                             "confidence_0_100": 80}), ensure_ascii=False, indent=2))
