# 🧱 CihloMat — Kalkulačka hrubého zdiva z půdorysu

Nahraješ půdorys RD → **Gemini** přečte obvod, vnitřní stěny, příčky, tloušťky a otvory →
spočítá se **cena hrubého zdiva ±rozsah** (materiál + práce) + cross-check celé hrubé stavby.
Nezávislé, **bez preference výrobce** (brand-agnostic cenové třídy levné/střední/dražší).

## Architektura

```
React SPA (templates/app.html, CDN bez buildu)
   │  POST /api/analyze (upload)        POST /api/calculate (úpravy)
   ▼
Flask app.py
   ├─ extract.py        AI vízia → JSON (obvod, nosné, příčky, tloušťky, otvory)
   │    └ providers.py  model-agnostické: Gemini 3.1-pro (default) ↔ Claude Fable
   │                    přepnutí = env EXTRACTOR_PROVIDER, žádná změna kódu
   ├─ reconcile.py      quality_gate (přijmout/odmítnout) · needs_escalation · merge
   ├─ claude_review.py  Claude text kontrola (jen když Gemini nejistý) — graceful
   ├─ claude_vision.py  Opus 4.8 vízia — JEN při eskalaci (nízká jistota)
   └─ pricing.py        výkaz výměr + cena (cihly.json) + ±band + cross-check
```

**Ceny: `cihly.json`** (editovatelné, bez zásahu do kódu). Materiál = Kč/m³ × naměřená
tloušťka zdiva; práce = sadzba rostoucí s tloušťkou; vše bez DPH, **jen zdivo bez zateplení**.
Kalibrováno na trh 2025/26 (DEK, cenikyremesel) + ověřeno proti reálné Ytong nabídce.

## Lokální spuštění

```bash
export GEMINI_API_KEY=...            # povinné
export ANTHROPIC_API_KEY=...         # volitelné (jinak Gemini-only)
pip install -r requirements.txt
python3 app.py                       # → http://localhost:5005
```

## Deploy na Vercel

1. `git init && git add . && git commit -m "init"` → push na GitHub
2. Na Vercelu **Import** repo (Python se detekuje sám přes `requirements.txt` + `api/index.py`)
3. **Environment Variables:** `GEMINI_API_KEY` (povinné), `ANTHROPIC_API_KEY` (volitelné)
4. Deploy. `vercel.json` směruje vše na funkci + `maxDuration: 60 s`.

### ⚠️ Důležité pro produkci
- **Timeout:** Gemini ~4–13 s; Opus eskalace (nízká jistota) +20–40 s. `maxDuration` je 60 s
  (Vercel Hobby/Pro). U velmi pomalých případů zvyš plán/limit.
- **Velikost uploadu:** Vercel má limit těla requestu ~4,5 MB — velké PDF zmenši.
- **API klíče** nikdy do gitu (jsou v `.gitignore`); nastav je jen jako env na Vercelu.

## Soubory

| Runtime | Dev/test (mimo deploy) |
|---------|------------------------|
| app.py, config.py, extract.py, providers.py | batch_test.py, batch_ensemble.py |
| pricing.py, reconcile.py | eval.py + ground_truth/ (merací etalón) |
| claude_review.py, claude_vision.py | gate_test.py, threeway.py, cv_walls.py |
| cihly.json, templates/app.html | shot.js (puppeteer screenshoty) |
| api/index.py, requirements.txt | scrapers/, test_podorysy/, PLAN_PRESNOST.md, ZNALOSTI_ROZPOCTAR.md |

> ⚠️ Orientační odhad, ceny bez DPH. „Hrubé zdivo" = obvod + nosné + příčky + překlady +
> věnec + práce — **ne** celá hrubá stavba (viz cross-check). Před objednávkou ověř s rozpočtářem.
