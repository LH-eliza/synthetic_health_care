"""
patient_portal.py — Secure patient-facing link Flask app.

Run: python patient_portal.py  (port 5001)

Separate from doctor app — patients access via token-in-URL.
No real authentication: token-in-URL is sufficient for hackathon.

Routes:
  GET  /p/<token>         → patient reads their plain-language summary
  POST /p/<token>/confirm → patient confirms a task done
  POST /p/<token>/submit  → patient submits a reading (number + optional note)
  GET  /p/<token>/done    → confirmation receipt page
"""

import os
import json
from datetime import date

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, jsonify

load_dotenv()

import db

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("FLASK_SECRET", "gp-copilot-portal-secret-2026")


# ---------------------------------------------------------------------------
# Patient portal — read summary
# ---------------------------------------------------------------------------

@app.route("/p/<token>")
def portal_view(token: str):
    token_data = db.get_token_data(token)
    if not token_data:
        return render_template("portal_error.html", message="This link is invalid or has expired."), 404

    patient = db.get_patient(token_data["patient_id"])
    if not patient:
        return render_template("portal_error.html", message="Patient record not found."), 404

    visit_id = token_data["visit_id"]
    visit = None
    tasks = []
    patient_summary = ""

    if visit_id:
        conn = db.get_conn()
        row = conn.execute("SELECT * FROM visits WHERE id=?", (visit_id,)).fetchone()
        conn.close()
        if row:
            visit = dict(row)
            patient_summary = visit.get("patient_summary_text") or ""

        tasks = db.get_pending_tasks_for_visit(visit_id)

    # Mark token as used (first access)
    if not token_data.get("used_at"):
        conn = db.get_conn()
        with conn:
            conn.execute(
                "UPDATE secure_tokens SET used_at=? WHERE token=?",
                (date.today().isoformat(), token),
            )
        conn.close()

    return render_template(
        "patient_portal.html",
        patient=patient,
        visit=visit,
        tasks=tasks,
        patient_summary=patient_summary,
        token=token,
    )


# ---------------------------------------------------------------------------
# Patient confirms a task done
# ---------------------------------------------------------------------------

@app.route("/p/<token>/confirm", methods=["POST"])
def portal_confirm(token: str):
    token_data = db.get_token_data(token)
    if not token_data:
        return jsonify({"error": "Invalid token"}), 404

    task_id = request.form.get("task_id")
    note = request.form.get("note", "")

    if not task_id:
        return jsonify({"error": "task_id required"}), 400

    db.submit_followup_response(
        task_id=int(task_id),
        response_type="confirmation",
        value=note or "Patient confirmed task completed",
        unit=None,
    )

    return redirect(url_for("portal_done", token=token, action="confirmed"))


# ---------------------------------------------------------------------------
# Patient submits a reading
# ---------------------------------------------------------------------------

@app.route("/p/<token>/submit", methods=["POST"])
def portal_submit(token: str):
    token_data = db.get_token_data(token)
    if not token_data:
        return jsonify({"error": "Invalid token"}), 404

    task_id = request.form.get("task_id")
    value = request.form.get("value", "").strip()
    unit = request.form.get("unit", "").strip()
    note = request.form.get("note", "").strip()

    if not task_id or not value:
        return jsonify({"error": "task_id and value required"}), 400

    full_value = f"{value} {unit}".strip()
    if note:
        full_value += f" — {note}"

    db.submit_followup_response(
        task_id=int(task_id),
        response_type="reading",
        value=full_value,
        unit=unit or None,
    )

    return redirect(url_for("portal_done", token=token, action="submitted"))


# ---------------------------------------------------------------------------
# Confirmation receipt
# ---------------------------------------------------------------------------

@app.route("/p/<token>/done")
def portal_done(token: str):
    action = request.args.get("action", "submitted")
    token_data = db.get_token_data(token)
    patient = None
    if token_data:
        patient = db.get_patient(token_data["patient_id"])
    return render_template("portal_done.html", patient=patient, action=action)


if __name__ == "__main__":
    print("🔒 GP Copilot — Patient Portal starting on http://localhost:5101")
    app.run(debug=True, port=5101, host="0.0.0.0")
