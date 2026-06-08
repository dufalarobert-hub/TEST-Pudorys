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


PROMPT = """Jsi zkušený stavební rozpočtář a děláš KRITICKOU kontrolu (druhý názor) odhadu,
který z půdorysu RD vytvořila jiná AI (Gemini). Tvůj úkol NENÍ potvrdit — ale NAJÍT systémové
chyby, které rychlé čtení často udělá. Buď konkrétní a smíš říct „nevím / ověřit".

Gemini vyčetla tyto parametry:
{data}

PROJDI tenhle checklist (to jsou nejčastější chyby):
1. OTVORY podceněné? Spočítej hrubě očekávaný počet oken (~1 okno / 12–15 m² podlahy) a dveří
   (~1 / místnost). Když je pocet_oken/pocet_dveri výrazně NÍŽ, je to podcenění → víc otvorů =
   míň zdiva = nižší cena. POZOR na GARÁŽ: garážová vrata (~10–12 m²) a velká prosklení obýváku
   se do otvorů často nezapočítají.
2. GARÁŽ / nevytápěné prostory: má dům garáž nebo technickou místnost (napovídá velká plocha
   nebo nízký počet oken na plochu)? Jejich stěny bývají tenčí / bez zateplení — počítat je jako
   plné vytápěné obvodové zdivo cenu nadhodnotí. Upozorni na ověření.
3. SKLADBA STĚNY: je ma_zateplenie=true a zdivo_zdroj NENÍ "legenda"? Pak je rozdělení stěny na
   zdivo+zateplení jen ODHAD (ne čtení) — pokud je to plné zdivo, cena bude vyšší. Připomeň to.
4. PODLAŽÍ: ma_schodiste=true ale pocet_podlazi=1? Pak dům má nejspíš víc podlaží → podcenění.
5. GEOMETRIE: obvod_m ~ 2*(šířka+délka) z plochy (zastavěná/užitná)? Velký nesoulad = chyba čtení.
6. TLOUŠŤKY: obvodové zdivo 240–450 mm, vnitřní nosné 175–300, příčky 80–150 mm. Mimo rozsah = flag.

Vrať POUZE validní JSON:
{{
  "issues": ["konkrétní nálezy z checklistu, max 5; prázdné [] jen když je vážně vše OK"],
  "suggestions": {{ "pole": nová_hodnota }},   // jen pole která bys SKUTEČNĚ změnil (pocet_oken, pocet_dveri, obvod_tloustka_mm, pricky_tloustka_mm, pricky_m), jinak prázdný objekt {{}}
  "refined_confidence_0_100": <číslo 0-100>,
  "summary": "1-2 věty pro majitele domu: nakolik odhadu věřit a co hlavně ověřit"
}}
Neměň obvod_m pokud ~sedí s kótami. Když si polem nejsi jistý, NEDÁVEJ ho do suggestions — radši to napiš do issues."""


def review(extraction: dict) -> dict:
    key = _get_key()
    if not key:
        return {"available": False, "reason": "no_key", "summary": "Claude kľúč nenájdený."}

    # pošli relevantné polia (lacné, žiadny obrázok) — vrátane skladby steny, nosných a schodiska,
    # aby kritik vedel posúdiť garáž/zateplenie/podlažia, nielen holé rozmery.
    fields = ["typ_stavby", "obvod_m", "obvod_tloustka_mm", "ma_zateplenie", "zdivo_zdroj",
              "obvod_material", "vnitrni_nosne_m", "vnitrni_nosne_tloustka_mm",
              "pricky_m", "pricky_tloustka_mm",
              "uzitna_plocha_m2", "zastavena_plocha_m2", "pocet_podlazi", "ma_schodiste",
              "vyska_podlazi_m", "pocet_oken", "pocet_dveri", "pocet_mistnosti", "confidence_0_100"]
    data = {k: extraction.get(k) for k in fields}

    try:
        import anthropic
        # timeout dosť veľký na serverless cold-start + reálne volanie (kritik beží vždy),
        # ale pod vercel maxDuration 60 s (Gemini časť už čosi zožerie). 1 retry na sieťový blip.
        # Bez kreditu padne rýchlo na auth chybu (nie na timeout), takže to appku nezdrží.
        client = anthropic.Anthropic(api_key=key, max_retries=1, timeout=25.0)
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
        # APIConnectionError má prázdne/generické str ("Connection error.") — vytiahni REÁLNu
        # príčinu z reťazca výnimiek (httpx ConnectError/ReadTimeout/SSLError), nech vieme diagnostikovať.
        cause = getattr(e, "__cause__", None)
        detail = f"{type(e).__name__}: {msg}"
        if cause is not None:
            detail += f" | príčina: {type(cause).__name__}: {str(cause)[:160]}"
        return {"available": False, "reason": "error", "summary": f"Claude chyba: {detail[:260]}"}


if __name__ == "__main__":
    print(json.dumps(review({"obvod_m": 56, "obvod_tloustka_mm": 300, "pricky_m": 42,
                             "pricky_tloustka_mm": 115, "uzitna_plocha_m2": 121,
                             "zastavena_plocha_m2": 150, "pocet_podlazi": 1,
                             "pocet_oken": 0, "pocet_dveri": 0, "pocet_mistnosti": 11,
                             "confidence_0_100": 80}), ensure_ascii=False, indent=2))
