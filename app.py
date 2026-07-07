"""
Cihlomat – Rozpočet hrubého zdiva z pôdorysu (lokálny prototyp).

Architektúra: Flask JSON API + React frontend (CDN, bez buildu).
  GET  /              -> React SPA (templates/app.html)
  POST /api/analyze   -> upload → Gemini extrakcia → Claude review → pricing (JSON)
  POST /api/calculate -> upravené parametre (JSON) → pricing (JSON)

Spustenie:  python3 app.py   (http://localhost:5005)
"""
import traceback
import uuid

from pathlib import Path

from flask import Flask, request, jsonify

import config
import extract
import komentar
import pricing
import claude_review
import claude_vision
import reconcile

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024   # 20 MB strop uploadu (Vercel má aj tak ~4.5)
ALLOWED = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}


@app.route("/")
def index():
    # servíruj React SPA staticky (NIE cez Jinja — JSX {{ }} by kolidoval)
    html = (Path(app.root_path) / "templates" / "app.html").read_text(encoding="utf-8")
    resp = app.make_response(html)
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    return resp


MAX_FLOORS = 5   # rozumný strop pre multi-fóto (počet podlaží)


def _save_upload(f):
    """Ulož nahraný súbor do UPLOAD_DIR; vráti (cesta, ext) alebo (None, ext) pri zlom formáte."""
    ext = "." + f.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED:
        return None, ext
    path = config.UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    f.save(path)
    return str(path), ext


def _aggregate_floors(floors):
    """Viac pôdorysov (1 = jedno podlažie) → SÚČET reálnej geometrie do jedného celku
    s pocet_podlazi=1 + _floors_summed=n (žiadne hádanie horného poschodia)."""
    n = len(floors)
    base = max(floors, key=lambda fl: int(fl.get("confidence_0_100") or 0))  # materiál/trieda z najistejšieho
    rooms = []
    for fl in floors:
        rooms += list(fl.get("plochy_mistnosti_m2") or [])

    def s(k):
        return sum(float(fl.get(k) or 0) for fl in floors)

    agg = dict(base)
    agg.update({
        "obvod_m": round(s("obvod_m"), 1),
        "vnitrni_nosne_m": round(s("vnitrni_nosne_m"), 1),
        "pricky_m": round(s("pricky_m"), 1),
        "pocet_oken": int(s("pocet_oken")),
        "pocet_dveri": int(s("pocet_dveri")),
        "uzitna_plocha_m2": round(s("uzitna_plocha_m2"), 1) or None,
        "zastavena_plocha_m2": None,        # cross-check ide z úžitnej (súčet podlaží); footprint by mátol
        "plochy_mistnosti_m2": rooms,
        "pocet_podlazi": 1,                 # už SÚČET reálnych podlaží → nenásobiť
        "_floors_summed": n,
        "confidence_0_100": min(int(fl.get("confidence_0_100") or 0) for fl in floors),  # najslabší článok
        "ma_zateplenie": any(fl.get("ma_zateplenie") for fl in floors),
        "ma_garaz": any(fl.get("ma_garaz") for fl in floors),
        "ma_schodiste": False,
    })
    return agg


def _analyze_multifloor(files):
    """Multi-fóto: každý súbor = jedno podlažie. Zmeraj zvlášť, sčítaj, naceň."""
    floors, skipped = [], []
    for i, f in enumerate(files):
        label = f"Podlažie {i + 1}"
        path, ext = _save_upload(f)
        if not path:
            skipped.append({"podlazi": label, "reason": f"Nepodporovaný formát {ext}."})
            continue
        try:
            ex = extract.extract_from_plan(path)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            skipped.append({"podlazi": label, "reason": f"Extrakcia zlyhala: {e}"})
            continue
        dec, msg = reconcile.quality_gate(ex)
        if dec == "REFUSE":
            skipped.append({"podlazi": label, "reason": msg})
            continue
        ex["_floor_label"] = label
        floors.append(ex)

    if not floors:
        return jsonify({"ok": False, "gate": "REFUSE", "skipped": skipped,
                        "error": "Z nahraných pôdorysov sme nezmerali ani jeden. "
                                 + (skipped[0]["reason"] if skipped else "")}), 200

    agg = _aggregate_floors(floors)
    result = pricing.calculate(agg)
    # DUPLIKÁT: 2× ten istý pôdorys (≈zhodný obvod aj plocha) = cena ~2× nadhodnotená
    for i in range(len(floors)):
        for j in range(i + 1, len(floors)):
            oi, oj = float(floors[i].get("obvod_m") or 0), float(floors[j].get("obvod_m") or 0)
            ui, uj = (float(floors[i].get("uzitna_plocha_m2") or 0),
                      float(floors[j].get("uzitna_plocha_m2") or 0))
            if oi and oj and abs(oi - oj) / max(oi, oj) < 0.03 \
                    and ui and uj and abs(ui - uj) / max(ui, uj) < 0.03:
                result["warnings"].insert(0, (
                    f"⚠ {floors[i]['_floor_label']} a {floors[j]['_floor_label']} vypadají jako "
                    f"STEJNÝ půdorys (obvod ~{oi:.0f} m, plocha ~{ui:.0f} m²). Pokud jste stejné "
                    "podlaží nahráli dvakrát, cena je ~2× nadhodnocená — nahrajte každé podlaží "
                    "jen jednou."))
    kom = komentar.compose(result, agg)
    # INTEGRACE (cihlomat): lead-capture rovnako ako pri single (result + _from_project).
    return jsonify({
        "ok": True, "gate": "ACCEPT", "gate_msg": None, "multifloor": True,
        "extraction": agg,
        "floors": [{"label": fl["_floor_label"], "obvod_m": fl.get("obvod_m"),
                    "pricky_m": fl.get("pricky_m"), "uzitna_plocha_m2": fl.get("uzitna_plocha_m2"),
                    "confidence_0_100": fl.get("confidence_0_100")} for fl in floors],
        "skipped": skipped,
        "vision": {"available": False, "reason": "multifloor", "escalated": False},
        "claude": {"available": False, "reason": "multifloor"},
        "reconcile": None,
        "komentar": kom,
        "pricing": result, "params": result["used_params"],
    })


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    # INTEGRACE (cihlomat): zde přidat rate-limit / auth — veřejné API volá metrovaný
    # Gemini, na produkci chraň proti zneužití (IP/den, token, …).
    files = [f for f in request.files.getlist("plan") if f and f.filename]
    if not files:
        return jsonify({"ok": False, "error": "Nahraj prosím pôdorys (PDF/PNG/JPG)."}), 400
    if len(files) > MAX_FLOORS:
        return jsonify({"ok": False, "error": f"Naraz max {MAX_FLOORS} podlaží."}), 400
    if len(files) > 1:
        return _analyze_multifloor(files)

    # ===== JEDEN súbor: pôvodný flow (Claude review + Opus eskalácia) =====
    f = files[0]
    ext = "." + f.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED:
        return jsonify({"ok": False, "error": f"Nepodporovaný formát {ext}."}), 400

    save_path = config.UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    f.save(save_path)

    try:
        extraction = extract.extract_from_plan(str(save_path))
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        return jsonify({"ok": False, "error": f"Extrakcia zlyhala: {e}"}), 500

    # === INPUT-QUALITY GATE: má výkres kóty na čom merať? ===
    decision, gate_msg = reconcile.quality_gate(extraction)
    if decision == "REFUSE":
        return jsonify({"ok": False, "error": gate_msg, "gate": "REFUSE",
                        "confidence": extraction.get("confidence_0_100")}), 200

    params = dict(extraction)

    # === PD DEEP-MINING: klasifikácia našla v dokumentácii aj pôdorys 2.NP → zmeraj ho
    # zvlášť a SČÍTAJ reálnu geometriu (namiesto "horné podlažie = kópia prízemia").
    floors_info = None
    extra_idx = extraction.get("_extra_floor_page_idx")
    if extra_idx is not None:
        try:
            ex2 = extract.extract_page(str(save_path), extra_idx)
            dec2, _ = reconcile.quality_gate(ex2)
            if dec2 != "REFUSE" and float(ex2.get("obvod_m") or 0) > 0:
                extraction["_floor_label"] = "1.NP"
                ex2["_floor_label"] = "2.NP"
                agg = _aggregate_floors([extraction, ex2])
                agg["_from_project"] = True
                agg["_page_idx"] = extraction.get("_page_idx")
                agg["_pages_total"] = extraction.get("_pages_total")
                params = dict(agg)
                floors_info = [{"label": fl["_floor_label"], "obvod_m": fl.get("obvod_m"),
                                "pricky_m": fl.get("pricky_m"),
                                "uzitna_plocha_m2": fl.get("uzitna_plocha_m2"),
                                "confidence_0_100": fl.get("confidence_0_100")}
                               for fl in (extraction, ex2)]
        except Exception:  # noqa: BLE001
            traceback.print_exc()   # 2.NP sa nepodarilo — pokračuj s 1.NP (graceful)

    # === Claude TEXT vrstva: len keď treba (Gemini nedal otvory / nízka conf) — šetrí čas+náklad.
    # Tichý pomocník: dopĺňa chýbajúce otvory; jeho výstup sa userovi NEzobrazuje (technický).
    need_claude = (not params.get("pocet_oken") or not params.get("pocet_dveri")
                   or int(params.get("confidence_0_100") or 0) < 70)
    claude = (claude_review.review(params) if need_claude
              else {"available": False, "reason": "not_needed",
                    "summary": "Gemini čítanie postačujúce — Claude kontrola netreba."})
    if claude.get("available"):
        for k, v in (claude.get("suggestions") or {}).items():
            if k in ("pocet_oken", "pocet_dveri") and (not params.get(k)):
                params[k] = v  # doplň len keď Gemini nič nedal

    # === ESKALÁCIA na Opus víziu LEN keď sa to oplatí (nízka conf / zlá geometria) ===
    # Gemini je na obvode dôveryhodný (≈ pravda); Opus voláme len keď je dôvod (drahé).
    escalate, esc_reasons = reconcile.needs_escalation(params)
    vision = {"available": False, "reason": "not_needed",
              "summary": "Gemini dôveryhodný — Opus vízia netreba."}
    merged = None
    if escalate:
        try:
            only = extraction.get("_page_idx") if extraction.get("_from_project") else None
            images = extract._pages_to_images(str(save_path), only_page=only)
            vision = claude_vision.read_independently(
                images, params, model=reconcile.ESCALATE_MODEL)
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            vision = {"available": False, "reason": "error", "summary": "Vízia zlyhala."}
        if vision.get("available"):
            merged = reconcile.merge(params, vision["read"])
            params.update(merged["params"])
            params["model_uncertainty"] = merged["model_uncertainty"]
    vision["escalated"] = escalate
    vision["escalation_reasons"] = esc_reasons

    result = pricing.calculate(params)

    # Komentár rozpočtára — súvislý ľudský odsek z čísel a varovaní (graceful bez kľúča).
    kom = komentar.compose(result, params)

    # INTEGRACE (cihlomat): zde se napojí lead-capture + ukládání do Railway.
    # K dispozici: result (výpočet) + extraction["_from_project"] (= projektová dokumentace
    # = silný lead). Až přibude kontakt (e-mail/telefon), POST {kontakt + result + _from_project}
    # do cihlomat lead-pipeline / Railway Postgres. Engine je jinak stateless (nic neukládá).

    return jsonify({
        "ok": True,
        "gate": decision,
        "gate_msg": gate_msg,
        "extraction": extraction,
        "multifloor": bool(floors_info),
        "floors": floors_info,
        "vision": vision,
        "reconcile": merged,
        "claude": claude,
        "komentar": kom,
        "pricing": result,
        "params": result["used_params"],
    })


@app.route("/api/calculate", methods=["POST"])
def api_calculate():
    p = request.get_json(force=True, silent=True) or {}
    try:
        result = pricing.calculate(p)
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify({"ok": True, "pricing": result, "params": result["used_params"]})


if __name__ == "__main__":
    print("Cihlomat rozpočet -> http://localhost:5005")
    app.run(host="0.0.0.0", port=5005, debug=True)
