# 📌 STAV PROJEKTU — Kalkulačka rozpočtu (archív 2026-07-07)

> Práca pozastavená 2026-07-07 po veľkom refaktore. Tento súbor = návod na návrat.
> Kontext: PLAN_PRESNOST.md (plán ±10 %) · ZNALOSTI_ROZPOCTAR.md (konštanty+citácie)
> · ground_truth/README.md (merací etalón) · eval_history/ (baseline).

## Kde sme skončili (commit 5dbea1d + gate_test_refuse.py)

7 commitov refaktoru (ced429b..5dbea1d), **NEPUSHNUTÉ na main** (push = auto-deploy
na Vercel test-pudorys.vercel.app — vedomé rozhodnutie počkať na overenie čísel).
Záloha commitov: vetva `archiv/2026-07-07-refaktor` na GitHube.

**Hotové:**
- Model-agnostická architektúra: `providers.py`, `EXTRACTOR_PROVIDER=gemini|anthropic`
  (Fable pripravený — tool-use schéma; budúcnosť = Fable API extractor)
- ÚRS metodika: murivo netto (−veniec 0.25 m), práca priečok 283+0.90×mm,
  garážový preklad 18k + odpočet vrát; itemizované otvory → preklady podľa rozponu
- Bbox polygon check (worst outlier 44→57.9 m = presne GT), PD deep-mining
  (rez+výpis otvorov+2.NP), duplikát-detektor podlaží, self-consistency (`EXTRACT_RUNS`)
- Komentár rozpočtára (komentar.py, Haiku, graceful) + karta v UI
- Robustný JSON parser + retry; gate test 8/8 (`python3 gate_test_refuse.py` cez PYTHONPATH=.)
- eval.py harness; baseline PRED zmenami: obvod MAPE 6.5 %, úžitná 0 %,
  slabiny nosné/priečky 164 % a okná 59 % (eval_history/eval_20260706_174916.json)

## ⚠️ Známe nedostatky (priznané, neopravené)

1. **Zmeny po baseline NEZMERANÉ** — re-eval nebežal; zhoda s Ytong ponukou vedome
   rozbitá (odstránené kompenzujúce sa chyby) a nová presnosť nepotvrdená
2. Nosné vs. priečky klasifikácia 164 % MAPE (najhoršie číslo, nedotknuté)
3. Ceny materiálu: MOC vs. reálne zľavy nedoriešené; NEN mining nespravený
4. Frontend zmeny (komentár karta, PD 2.NP flow) NEotestované v prehliadači
   (pravidlo projektu: puppeteer test po každej frontend zmene!)
5. Self-consistency default vypnutá; celková latencia PD flow vs Vercel 60 s nemeraná
6. claude_review nevie o itemizovaných otvoroch; README tabuľka súborov mierne neaktuálna

## ▶️ AKO POKRAČOVAŤ (presné poradie)

1. **Browser test** — `python3 app.py` → :5005, puppeteer/ručne preklikať:
   upload pôdorysu, komentár karta, PD s 2.NP (1–2 Gemini volania)
2. **Robert overí GT drafty** — ground_truth/README.md checklist, prepnúť verified=true
3. **Re-eval po zmenách** — `python3 eval.py --all --label "po refaktore"` (9 volaní ~2 Kč)
   → porovnať s baseline v eval_history/
4. **A/B Fable** — kľúč: `ANTHROPIC_ENV_FILE="$HOME/Desktop/Influencer Report Generator/app/.env.local"`
   + `EXTRACTOR_PROVIDER=anthropic python3 eval.py --all --label "Fable A/B"` (9 volaní ~25–35 Kč)
5. **Rozhodnúť push→Vercel** (main = produkčný deploy)
6. Potom: rate-limit (NUTNÉ pred Meta Ads), lead capture cez Ecomail + feedback
   otázka „máte už ponuku? materiál/komplet?", PDF export, NEN kalibrácia

## Pravidlá (Robert)

- API volania hlásiť VOPRED (metrované API vadí, subscription tokeny nie)
- Konštanty LEN z primárnych zdrojov (ÚRS/výrobcovia/cenníky), žiadne študentské práce
- Žiadna kompenzácia chýb; LLM číta, Python počíta; zmena promptu = regresný beh
- Rozsah = materiál+práca zdiva (bez lešenia/réžie), bez DPH
