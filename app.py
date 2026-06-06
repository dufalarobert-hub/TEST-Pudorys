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
import pricing
import claude_review
import claude_vision
import reconcile

app = Flask(__name__)
ALLOWED = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}


@app.route("/")
def index():
    # servíruj React SPA staticky (NIE cez Jinja — JSX {{ }} by kolidoval)
    html = (Path(app.root_path) / "templates" / "app.html").read_text(encoding="utf-8")
    resp = app.make_response(html)
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    return resp


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    # INTEGRACE (cihlomat): zde přidat rate-limit / auth — veřejné API volá metrovaný
    # Gemini, na produkci chraň proti zneužití (IP/den, token, …).
    f = request.files.get("plan")
    if not f or not f.filename:
        return jsonify({"ok": False, "error": "Nahraj prosím pôdorys (PDF/PNG/JPG)."}), 400
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

    # === Claude TEXT vrstva: len keď treba (Gemini nedal otvory / nízka conf) — šetrí čas ===
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

    # INTEGRACE (cihlomat): zde se napojí lead-capture + ukládání do Railway.
    # K dispozici: result (výpočet) + extraction["_from_project"] (= projektová dokumentace
    # = silný lead). Až přibude kontakt (e-mail/telefon), POST {kontakt + result + _from_project}
    # do cihlomat lead-pipeline / Railway Postgres. Engine je jinak stateless (nic neukládá).

    return jsonify({
        "ok": True,
        "gate": decision,
        "gate_msg": gate_msg,
        "extraction": extraction,
        "vision": vision,
        "reconcile": merged,
        "claude": claude,
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
