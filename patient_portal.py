"""
patient_portal.py — Secure patient-facing pre-visit portal Flask app.

Run: python patient_portal.py  (port 5101)

Routes:
  GET  /p/<token>              → React SPA shell
  GET  /p/demo                   → Demo SPA (Margaret Thompson spec data)
  GET  /p/<token>/api/data       → Portal JSON schema
  POST /p/<token>/api/task/<id>  → Submit task completion
  POST /p/<token>/api/send       → Patient sends summary to doctor
"""

import os
from datetime import date

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

load_dotenv()

import db
from portal_schema import (
    build_portal_payload,
    demo_portal_payload,
    persist_task_submission,
)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("FLASK_SECRET", "gp-copilot-portal-secret-2026")
CORS(app)


def _mark_token_used(token: str, token_data: dict):
    if token == db.DEMO_TOKEN:
        return
    if not token_data.get("used_at"):
        conn = db.get_conn()
        with conn:
            conn.execute(
                "UPDATE secure_tokens SET used_at=? WHERE token=?",
                (date.today().isoformat(), token),
            )
        conn.close()


def _resolve_token(token: str):
    if token == db.DEMO_TOKEN:
        token_data = db.get_token_data(db.DEMO_TOKEN)
        if token_data:
            payload = build_portal_payload(db.DEMO_TOKEN, token_data)
            if payload:
                return token_data, payload
        return {"demo": True}, demo_portal_payload()
    token_data = db.get_token_data(token)
    if not token_data:
        return None, None
    payload = build_portal_payload(token, token_data)
    return token_data, payload


# ---------------------------------------------------------------------------
# SPA shell
# ---------------------------------------------------------------------------

@app.route("/p/demo")
def portal_demo():
    return render_template("patient_portal_spa.html", token="demo")


@app.route("/p/<token>")
def portal_view(token: str):
    token_data, payload = _resolve_token(token)
    if not payload:
        return render_template(
            "portal_error.html", message="This link is invalid or has expired."
        ), 404
    if token_data and not token_data.get("demo"):
        _mark_token_used(token, token_data)
    return render_template("patient_portal_spa.html", token=token)


# ---------------------------------------------------------------------------
# API — portal data
# ---------------------------------------------------------------------------

@app.route("/p/<token>/api/data")
def portal_api_data(token: str):
    token_data, payload = _resolve_token(token)
    if not payload:
        return jsonify({"error": "Invalid or expired token"}), 404
    return jsonify(payload)


# ---------------------------------------------------------------------------
# API — task submission
# ---------------------------------------------------------------------------

@app.route("/p/<token>/api/task/<task_id>", methods=["POST"])
def portal_api_task(token: str, task_id: str):
    token_data = (
        db.get_token_data(db.DEMO_TOKEN)
        if token == db.DEMO_TOKEN
        else db.get_token_data(token)
    )
    if not token_data:
        return jsonify({"error": "Invalid token"}), 404

    body = request.get_json() or {}
    portal_type = body.get("type")
    payload = body.get("payload", {})
    db_task_id = body.get("dbTaskId")

    if db_task_id is None:
        match = task_id.replace("task_", "")
        try:
            db_task_id = int(match)
        except ValueError:
            return jsonify({"error": "Invalid task id"}), 400

    try:
        persist_task_submission(int(db_task_id), portal_type, payload)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    updated = build_portal_payload(token, token_data)
    return jsonify({
        "success": True,
        "tasks": updated["tasks"] if updated else [],
        "progressCalendar": updated.get("progressCalendar") if updated else None,
    })


# ---------------------------------------------------------------------------
# API — send to doctor
# ---------------------------------------------------------------------------

@app.route("/p/<token>/api/send", methods=["POST"])
def portal_api_send(token: str):
    token_data = (
        db.get_token_data(db.DEMO_TOKEN)
        if token == db.DEMO_TOKEN
        else db.get_token_data(token)
    )
    if not token_data:
        return jsonify({"error": "Invalid token"}), 404
    return jsonify({"success": True, "message": "Summary sent to your care team."})


if __name__ == "__main__":
    db.init_db()
    db.seed()
    db.ensure_portal_demo()
    print("Patient Pre-Visit Portal → http://localhost:5101/p/demo")
    app.run(debug=True, port=5101, host="0.0.0.0")
