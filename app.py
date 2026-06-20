"""
app.py — GP Copilot doctor-facing Flask application.

Run: python app.py  (port 5000)

Routes:
  GET  /                          → patient selector
  GET  /patient/<id>              → routes to flow-a or flow-b
  GET  /flow-a/<id>               → new patient in-visit intake
  POST /flow-a/<id>/transcribe    → LLM structuring call
  POST /flow-a/<id>/confirm-bin   → confirm one bin → partial save
  POST /flow-a/<id>/confirm-all   → save complete baseline snapshot
  GET  /flow-b/<id>               → returning patient pre-visit + chips
  POST /flow-b/<id>/start-visit   → create visit record
  POST /flow-b/<id>/generate-note → LLM dual output generation
  POST /flow-b/<id>/confirm-note  → save visit + follow-up tasks
  POST /flow-b/<id>/send-portal   → generate secure token + mock send
  GET  /demo/advance-date         → advance demo date form
  POST /demo/advance-date         → advance demo date by N days
  GET  /dashboard                 → multi-patient secondary view
"""

import json
import os
from datetime import date, timedelta

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from flask_cors import CORS

load_dotenv()

import db
import rules_engine
from config import SOCIAL_HISTORY_CATEGORIES
from llm_components import generate_dual_output_note, transcribe_and_structure_intake

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "gp-copilot-demo-secret-2026")
CORS(app)

# Initialize DB on startup
db.init_db()
db.seed()
db.patch_marcus_demo_data()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patient_age(dob_str: str, today: date) -> int:
    from datetime import date as d
    dob = d.fromisoformat(dob_str)
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def _enrich_patient(p: dict, today: date) -> dict:
    """Add computed fields to patient dict."""
    p["age"] = _patient_age(p["dob"], today)
    snap = db.get_latest_snapshot(p["id"])
    p["snapshot_data"] = snap["data"] if snap else {}
    return p


# ---------------------------------------------------------------------------
# Root — patient selector
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    today = db.get_demo_date()
    patients = db.get_all_patients()
    for p in patients:
        p["age"] = _patient_age(p["dob"], today)
        visits = db.get_visits(p["id"])
        p["visit_count"] = len(visits)
        p["flow"] = "A" if not visits else "B"
    return render_template("index.html", patients=patients, today=today)


# ---------------------------------------------------------------------------
# Patient router
# ---------------------------------------------------------------------------

@app.route("/patient/<int:patient_id>")
def patient_router(patient_id: int):
    visits = db.get_visits(patient_id)
    if not visits:
        return redirect(url_for("flow_a", patient_id=patient_id))
    return redirect(url_for("flow_b", patient_id=patient_id))


# ---------------------------------------------------------------------------
# FLOW A — New patient in-visit intake
# ---------------------------------------------------------------------------

@app.route("/flow-a/<int:patient_id>")
def flow_a(patient_id: int):
    today = db.get_demo_date()
    patient = db.get_patient(patient_id)
    if not patient:
        return "Patient not found", 404
    patient = _enrich_patient(patient, today)

    visits = db.get_visits(patient_id)
    has_history = len(visits) > 0

    # Check if baseline already established
    snapshot = db.get_latest_snapshot(patient_id)

    return render_template(
        "flow_a.html",
        patient=patient,
        today=today,
        has_history=has_history,
        categories=SOCIAL_HISTORY_CATEGORIES,
        snapshot=snapshot,
    )


@app.route("/flow-a/<int:patient_id>/transcribe", methods=["POST"])
def flow_a_transcribe(patient_id: int):
    """Call LLM to structure conversation into bins. Returns JSON."""
    data = request.get_json()
    conversation_text = data.get("conversation_text", "").strip()
    if not conversation_text:
        return jsonify({"error": "No conversation text provided"}), 400

    try:
        result = transcribe_and_structure_intake(
            conversation_text=conversation_text,
            category_hints=SOCIAL_HISTORY_CATEGORIES,
        )
        return jsonify({"success": True, "bins": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/flow-a/<int:patient_id>/confirm-all", methods=["POST"])
def flow_a_confirm_all(patient_id: int):
    """Save confirmed bins as baseline chart snapshot."""
    data = request.get_json()
    bins = data.get("bins", {})
    if not bins:
        return jsonify({"error": "No bins to save"}), 400

    db.save_flow_a_bins(patient_id, bins)
    return jsonify({"success": True, "message": "Baseline record established."})


# ---------------------------------------------------------------------------
# FLOW B — Returning patient pre-visit + visit
# ---------------------------------------------------------------------------

@app.route("/flow-b/<int:patient_id>")
def flow_b(patient_id: int):
    today = db.get_demo_date()
    patient = db.get_patient(patient_id)
    if not patient:
        return "Patient not found", 404
    patient = _enrich_patient(patient, today)

    # Get N-1 visit data
    latest_visit = db.get_latest_visit(patient_id)
    prior_tasks = []
    responses = []
    chips = {}

    if latest_visit:
        prior_tasks = db.get_tasks_for_visit(latest_visit["id"])
        responses = db.get_responses_for_patient_tasks(patient_id)
        chips = rules_engine.build_previsit_chips(patient, prior_tasks, responses, today)

    executive_brief = rules_engine.build_executive_brief(
        patient, chips, latest_visit, today
    ) if chips else None

    ed_continuity_alert = rules_engine.get_ed_continuity_alert(patient, today)

    snap = db.get_latest_snapshot(patient_id)

    # Check if there's already a new visit started in session
    active_visit_id = session.get(f"active_visit_{patient_id}")
    active_visit = None
    if active_visit_id:
        conn = db.get_conn()
        row = conn.execute("SELECT * FROM visits WHERE id=?", (active_visit_id,)).fetchone()
        conn.close()
        active_visit = dict(row) if row else None

    return render_template(
        "flow_b.html",
        patient=patient,
        today=today,
        latest_visit=latest_visit,
        prior_tasks=prior_tasks,
        chips=chips,
        executive_brief=executive_brief,
        ed_continuity_alert=ed_continuity_alert,
        snapshot=snap,
        active_visit=active_visit,
    )


@app.route("/flow-b/<int:patient_id>/start-visit", methods=["POST"])
def flow_b_start_visit(patient_id: int):
    """Create a new visit record for today."""
    today = db.get_demo_date()
    data = request.get_json()
    visit_reason = data.get("visit_reason", "").strip() or "Unspecified"

    visit_id = db.create_visit(patient_id, today.isoformat(), visit_reason)
    session[f"active_visit_{patient_id}"] = visit_id
    return jsonify({"success": True, "visit_id": visit_id})


@app.route("/flow-b/<int:patient_id>/generate-note", methods=["POST"])
def flow_b_generate_note(patient_id: int):
    """Call LLM to generate dual chart/patient note from visit text."""
    patient = db.get_patient(patient_id)
    if not patient:
        return jsonify({"error": "Patient not found"}), 404

    data = request.get_json()
    visit_notes = data.get("visit_notes", "").strip()
    if not visit_notes:
        return jsonify({"error": "No visit notes provided"}), 400

    visit_id = session.get(f"active_visit_{patient_id}")
    visit_reason = ""
    if visit_id:
        visit = db.get_visit(visit_id)
        if visit:
            visit_reason = visit.get("visit_reason") or ""

    try:
        result = generate_dual_output_note(
            visit_notes_text=visit_notes,
            patient_context={
                "name": patient["name"].split()[0],  # first name for patient summary
                "condition": patient.get("condition") or "chronic condition",
                "visit_reason": visit_reason,
            },
        )
        return jsonify({"success": True, "output": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/flow-b/<int:patient_id>/confirm-note", methods=["POST"])
def flow_b_confirm_note(patient_id: int):
    """Save confirmed visit notes + follow-up tasks to DB."""
    data = request.get_json()
    visit_id = data.get("visit_id") or session.get(f"active_visit_{patient_id}")
    chart_entry = data.get("chart_entry", "")
    patient_summary = data.get("patient_summary", "")
    tasks = data.get("tasks", [])  # list of {description, type, due_date, target_metric}

    if not visit_id:
        return jsonify({"error": "No active visit found"}), 400

    db.update_visit_notes(visit_id, chart_entry, patient_summary)

    task_ids = []
    if tasks:
        task_ids = db.create_followup_tasks(patient_id, visit_id, tasks)

    session[f"active_visit_{patient_id}"] = None
    return jsonify({
        "success": True,
        "visit_id": visit_id,
        "task_count": len(task_ids),
        "message": "Visit saved. Follow-up tasks created. Loop closed for next visit.",
    })


@app.route("/flow-b/<int:patient_id>/send-portal", methods=["POST"])
def flow_b_send_portal(patient_id: int):
    """Generate secure token and mock-send patient portal link."""
    data = request.get_json()
    visit_id = data.get("visit_id")
    if not visit_id:
        return jsonify({"error": "visit_id required"}), 400

    token = db.create_secure_token(patient_id, visit_id)

    # In production this would call OceanMD / SMS gateway. We log + return URL.
    portal_url = f"http://localhost:5101/p/{token}"

    return jsonify({
        "success": True,
        "token": token,
        "portal_url": portal_url,
        "message": "Secure link generated. Patient notified via secure message.",
        "ocean_analog": {
            "secure_message": True,
            "allow_patient_reply": True,
            "notify_on_view": True,
        },
    })


# ---------------------------------------------------------------------------
# Date settings
# ---------------------------------------------------------------------------

@app.route("/settings/date", methods=["GET", "POST"])
def demo_advance_date():
    today = db.get_demo_date()
    if request.method == "POST":
        days = int(request.form.get("days", 0))
        new_date = today + timedelta(days=days)
        db.set_demo_date(new_date)
        _recompute_all_task_statuses(new_date)
        return redirect(url_for("index"))
    return render_template("demo_date.html", today=today)


def _recompute_all_task_statuses(today: date):
    """Recompute and persist task statuses after demo date advance."""
    patients = db.get_all_patients()
    conn = db.get_conn()
    with conn:
        for p in patients:
            tasks_rows = conn.execute(
                "SELECT ft.*, COUNT(fr.id) as resp_count FROM followup_tasks ft "
                "LEFT JOIN followup_responses fr ON fr.task_id = ft.id "
                "WHERE ft.patient_id=? GROUP BY ft.id",
                (p["id"],),
            ).fetchall()
            for task_row in tasks_rows:
                task = dict(task_row)
                if task["resp_count"] > 0:
                    new_status = "done"
                elif date.fromisoformat(task["due_date"]) < today:
                    new_status = "overdue"
                else:
                    new_status = "no_data"
                conn.execute(
                    "UPDATE followup_tasks SET status=? WHERE id=?",
                    (new_status, task["id"]),
                )
    conn.close()


# ---------------------------------------------------------------------------
# Dashboard (secondary multi-patient view)
# ---------------------------------------------------------------------------

@app.route("/dashboard")
def dashboard():
    today = db.get_demo_date()
    patients = db.get_all_patients()
    enriched = []
    for p in patients:
        p["age"] = _patient_age(p["dob"], today)
        visits = db.get_visits(p["id"])
        p["visit_count"] = len(visits)
        p["flow"] = "A" if not visits else "B"
        p["snapshot_data"] = {}
        snap = db.get_latest_snapshot(p["id"])
        if snap:
            p["snapshot_data"] = snap["data"]
        if visits:
            latest = visits[0]
            tasks = db.get_tasks_for_visit(latest["id"])
            p["open_tasks"] = [t for t in tasks if t["status"] != "done"]
            p["done_tasks"] = [t for t in tasks if t["status"] == "done"]
        else:
            p["open_tasks"] = []
            p["done_tasks"] = []
        enriched.append(p)
    return render_template("dashboard.html", patients=enriched, today=today)


# ---------------------------------------------------------------------------
# API endpoint for dashboard data refresh
# ---------------------------------------------------------------------------

@app.route("/api/patient/<int:patient_id>/chips")
def api_chips(patient_id: int):
    today = db.get_demo_date()
    patient = db.get_patient(patient_id)
    if not patient:
        return jsonify({"error": "Not found"}), 404
    patient = _enrich_patient(patient, today)
    latest_visit = db.get_latest_visit(patient_id)
    if not latest_visit:
        return jsonify({"error": "No visits on record"}), 404
    prior_tasks = db.get_tasks_for_visit(latest_visit["id"])
    responses = db.get_responses_for_patient_tasks(patient_id)
    chips = rules_engine.build_previsit_chips(patient, prior_tasks, responses, today)
    return jsonify(chips)


if __name__ == "__main__":
    print("🏥 GP Copilot — Doctor App starting on http://localhost:5100")
    app.run(debug=True, port=5100, host="0.0.0.0")
