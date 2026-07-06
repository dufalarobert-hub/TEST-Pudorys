"""
Provider vrstva pre AI víziu — JEDINÉ miesto v kóde, kde žije konkrétny model/SDK.

Architektonický princíp (2026-07-06): model je vymeniteľný dielec, nie základ.
Extrakcia, reconcile, pricing aj UI konzumujú normalizovaný JSON — výmena
Gemini ↔ Claude (Fable) je env premenná, nie zásah do kódu:

    EXTRACTOR_PROVIDER = "gemini" (default) | "anthropic"

Kontrakt providera:
    generate(images, prompt, cheap=False, schema=None) -> (text, usage {"in","out"}, model)
      images: list[bytes]  (PNG)
      cheap=True  → lacný/rýchly model (výber strany pôdorysu a pod.)
      schema      → JSON Schema (dict): vynúti ŠTRUKTÚROVANÝ výstup
                    (Gemini = JSON-mode + response_schema; Claude = forced tool-use)
                    → text je garantovane čistý JSON, žiadne regex parsovanie
Fallback reťazec modelov rieši provider sám (volajúci ho nevidí).
"""
import base64
import os

import config


class GeminiVision:
    """Google Gemini (SDK google-genai)."""
    name = "gemini"

    def __init__(self):
        from google import genai
        from google.genai import types
        self._genai, self._types = genai, types
        self._client = genai.Client(api_key=config.get_gemini_key())

    def generate(self, images, prompt, cheap=False, schema=None):
        t = self._types
        parts = [t.Part.from_bytes(data=img, mime_type="image/png") for img in images]
        parts.append(prompt)
        kw = {"thinking_config": t.ThinkingConfig(
            thinking_budget=256 if cheap else config.GEMINI_THINKING_BUDGET)}
        if schema:
            # JSON-mode: model MUSÍ vrátiť čistý JSON (žiadne ```obaly```). Samotnú schému
            # nesie prompt — response_schema NEposielame (nullable únie sú medzi verziami
            # google-genai SDK krehké; Claude/Fable má plnú schému cez tool-use).
            kw["response_mime_type"] = "application/json"
        cfg = t.GenerateContentConfig(**kw)
        models = ([config.GEMINI_PICK_MODEL] if cheap
                  else [config.GEMINI_VISION_MODEL, config.GEMINI_VISION_FALLBACK])
        last_err = None
        for model in models:
            try:
                resp = self._client.models.generate_content(model=model, contents=parts, config=cfg)
                um = getattr(resp, "usage_metadata", None)
                usage = {"in": getattr(um, "prompt_token_count", 0) or 0,
                         "out": getattr(um, "candidates_token_count", 0) or 0} if um else {"in": 0, "out": 0}
                return resp.text, usage, model
            except Exception as e:  # noqa: BLE001
                last_err = e
        raise RuntimeError(f"Gemini generate zlyhal: {last_err}")


class AnthropicVision:
    """Anthropic Claude (Fable/Opus) — rovnaký kontrakt ako Gemini."""
    name = "anthropic"

    def __init__(self):
        import anthropic
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("EXTRACTOR_PROVIDER=anthropic vyžaduje ANTHROPIC_API_KEY.")
        # timeout < Vercel maxDuration 60 s → pri probléme graceful chyba, nie zabitá funkcia
        self._client = anthropic.Anthropic(api_key=key, timeout=55.0, max_retries=1)

    def generate(self, images, prompt, cheap=False, schema=None):
        import json as _json
        model = (config.ANTHROPIC_PICK_MODEL if cheap else config.ANTHROPIC_VISION_MODEL)
        content = [{"type": "image",
                    "source": {"type": "base64", "media_type": "image/png",
                               "data": base64.b64encode(img).decode()}} for img in images]
        content.append({"type": "text", "text": prompt})
        kw = {}
        if schema:
            # forced tool-use = validácia štruktúry na úrovni API (Claude silná stránka)
            kw["tools"] = [{"name": "report", "description": "Nahlás vyčítané hodnoty.",
                            "input_schema": schema}]
            kw["tool_choice"] = {"type": "tool", "name": "report"}
        resp = self._client.messages.create(
            model=model, max_tokens=4096,
            messages=[{"role": "user", "content": content}], **kw)
        if schema:
            data = next(b.input for b in resp.content if getattr(b, "type", "") == "tool_use")
            text = _json.dumps(data, ensure_ascii=False)
        else:
            text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        usage = {"in": getattr(resp.usage, "input_tokens", 0) or 0,
                 "out": getattr(resp.usage, "output_tokens", 0) or 0}
        return text, usage, model


_PROVIDERS = {"gemini": GeminiVision, "anthropic": AnthropicVision}
_instance = None


def get_provider():
    """Vráti (cache-ovaný) provider podľa env EXTRACTOR_PROVIDER."""
    global _instance
    name = os.environ.get("EXTRACTOR_PROVIDER", "gemini").lower()
    if name not in _PROVIDERS:
        raise RuntimeError(f"Neznámy EXTRACTOR_PROVIDER='{name}' (podporované: {list(_PROVIDERS)})")
    if _instance is None or _instance.name != name:
        _instance = _PROVIDERS[name]()
    return _instance
