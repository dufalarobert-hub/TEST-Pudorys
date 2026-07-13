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

## Struktura projektu

```
KOŘEN — runtime (jde do deploye na Vercel)
├─ app.py                Flask server + agregace podlaží
├─ extract.py            AI vízia → JSON  ·  providers.py  Gemini↔Claude přepínač
├─ pricing.py            výkaz výměr + cena  ·  reconcile.py  quality gate
├─ claude_review.py / claude_vision.py / komentar.py   Claude kontroly + komentář
├─ config.py · cihly.json (ceník) · templates/app.html (React UI přes CDN, bez buildu)
├─ api/index.py          Vercel WSGI entry  ·  vercel.json · requirements.txt
│
├─ eval.py               merací harness (MAPE vs ground_truth/, história eval_history/)
├─ ground_truth/         etalón měření (16 výkresů)  ·  test_podorysy/  jpg vzorky
│
├─ testy/                gate_test.py · gate_test_refuse.py · batch_test.py
│                        (spouštět z kořene: python3 testy/gate_test_refuse.py)
├─ fable_testy/          manuální testy čtení půdorysů Fable modelem + verifikace vs PD
├─ docs/                 STAV_PROJEKTU.md (RESUME!) · PLAN_PRESNOST.md
│                        · ZNALOSTI_ROZPOCTAR.md · GUIDELINE_PODORYS.md
├─ scrapers/ · shot.js   pomocné (scraping, puppeteer screenshoty)
└─ test_projekty/        reálné PD na testování (NENÍ v gitu, ~128 MB)
```

> ⚠️ Orientační odhad, ceny bez DPH. „Hrubé zdivo" = obvod + nosné + příčky + překlady +
> věnec + práce — **ne** celá hrubá stavba (viz cross-check). Před objednávkou ověř s rozpočtářem.
