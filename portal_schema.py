"""
portal_schema.py — Transform DB records into patient portal JSON schemas.

All UI data flows through these builders so the React SPA never hardcodes
patient, visit, task, or tip content.
"""

from __future__ import annotations

import json
import os
import re
import calendar
from datetime import date, timedelta
from typing import Any

import db

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "portal_config.json")
_TIPS_PATH = os.path.join(os.path.dirname(__file__), "patient_portal_tips.json")

with open(_CONFIG_PATH) as _f:
    PORTAL_CONFIG: dict = json.load(_f)

with open(_TIPS_PATH) as _f:
    PORTAL_TIPS: list[dict] = json.load(_f)



def demo_portal_payload() -> dict:
    """Static example payload matching the Cursor system specification."""
    return {
        "token": "demo",
        "metadata": {
            "patient": {
                "id": "pat_9921",
                "firstName": "Margaret",
                "lastName": "Thompson",
            },
            "doctor": {
                **PORTAL_CONFIG["doctor"],
                "note": (
                    "Great seeing you today, Margaret. Let's really focus on tracking "
                    "that morning blood pressure before our next check-in."
                ),
            },
            "visit": {
                "lastDate": "2025-06-16",
                "nextDate": "2025-07-14",
                "metrics": {
                    "currentBP": {"systolic": 142, "diastolic": 88},
                    "targetBP": {"systolic": 130, "diastolic": 80},
                    "status": "warning",
                },
                "summaryPlain": [
                    "BP today was 142/88 — a little high; target below 130/80",
                    "Amlodipine increased from 5 mg → 10 mg once daily",
                    "Take every morning; don't stop without checking",
                    "Should notice it working in 1–2 weeks; next visit July 14",
                ],
            },
            "afterVisitReport": _margaret_demo_report(),
        },
        "tasks": [
            {
                "id": "task_1",
                "dbTaskId": None,
                "type": "checkbox",
                "title": "Measure your blood pressure each morning",
                "frequency": "daily",
                "isRecurring": True,
                "loggedInPeriod": False,
                "loggedDates": [],
                "streak": 0,
                "isCompleted": False,
            },
            {
                "id": "task_2",
                "dbTaskId": None,
                "type": "file_upload",
                "title": "Upload your cardiology report",
                "frequency": "once",
                "isRecurring": False,
                "loggedInPeriod": False,
                "loggedDates": [],
                "streak": 0,
                "isCompleted": False,
                "payload": None,
            },
            {
                "id": "task_3",
                "dbTaskId": None,
                "type": "bp_log",
                "title": "Add your blood pressure readings",
                "frequency": "daily",
                "isRecurring": True,
                "loggedInPeriod": False,
                "loggedDates": [],
                "streak": 0,
                "isCompleted": False,
                "payload": [],
            },
            {
                "id": "task_4",
                "dbTaskId": None,
                "type": "notes_textarea",
                "title": "Notes from another doctor's visit",
                "frequency": "once",
                "isRecurring": False,
                "loggedInPeriod": False,
                "loggedDates": [],
                "streak": 0,
                "isCompleted": False,
                "payload": {"text": "", "attachment": None},
            },
        ],
        "progressCalendar": {
            "month": "2025-06",
            "today": "2025-06-16",
            "stats": {"currentStreak": 0, "thisWeekCount": 0, "totalLogs": 0},
            "days": [
                {"date": f"2025-06-{d:02d}", "count": 0, "entries": []}
                for d in range(1, 31)
            ],
            "entriesByDate": {},
        },
        "tips": PORTAL_TIPS,
    }


# ---------------------------------------------------------------------------
# Live DB → schema builders
# ---------------------------------------------------------------------------

def _split_name(full_name: str) -> tuple[str, str]:
    parts = (full_name or "Patient").strip().split()
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _parse_bp(text: str) -> dict | None:
    """Extract systolic/diastolic from chart or summary text."""
    if not text:
        return None
    match = re.search(r"(\d{2,3})\s*/\s*(\d{2,3})", text)
    if match:
        return {"systolic": int(match.group(1)), "diastolic": int(match.group(2))}
    return None


def _bp_status(current: dict, target: dict) -> str:
    if not current:
        return "neutral"
    if (
        current["systolic"] <= target["systolic"]
        and current["diastolic"] <= target["diastolic"]
    ):
        return "good"
    if current["systolic"] <= target["systolic"] + 15:
        return "warning"
    return "critical"


def _summary_lines(summary_text: str) -> list[str]:
    if not summary_text:
        return []
    lines = []
    for raw in summary_text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        line = re.sub(r"^[\[✓✔]\s*\]?\s*", "", line)
        line = re.sub(r"^[-•*]\s*", "", line)
        if line.lower().startswith("hi ") and len(lines) == 0:
            continue
        if "here's a summary" in line.lower() or "your tasks before" in line.lower():
            continue
        if line.startswith("Your care team"):
            continue
        lines.append(line)
    return lines[:8]


def _margaret_demo_report() -> dict:
    """Rich after-visit report for Margaret Thompson demo."""
    precautions = PORTAL_CONFIG.get("conditionPrecautions", {}).get("hypertension", [])
    return {
        "title": "After-Visit Report",
        "visitReason": "Hypertension follow-up",
        "keyFindings": [
            "Blood pressure today was 142/88 mmHg — above target of 130/80",
            "Home morning BP monitoring recommended before next check-in",
        ],
        "medicationChanges": [
            "Amlodipine increased from 5 mg to 10 mg once daily",
            "Take every morning with water; do not stop without calling the clinic",
            "Full effect may take 1–2 weeks",
        ],
        "precautions": precautions,
        "doctorRemarks": (
            "Great seeing you today, Margaret. Let's really focus on tracking "
            "that morning blood pressure before our next check-in."
        ),
        "followUpTasks": [
            "Measure your blood pressure each morning",
            "Upload your cardiology report",
            "Add your blood pressure readings",
            "Notes from another doctor's visit",
        ],
        "lifestyleGuidance": [
            {"title": t["title"], "detail": t["detail"]}
            for t in PORTAL_TIPS[:4]
        ],
        "emergencyNotice": PORTAL_CONFIG.get(
            "emergencyNotice",
            "If you are experiencing a medical emergency, call 911.",
        ),
    }


def _extract_medication_changes(summary_lines: list[str], chart_text: str) -> list[str]:
    changes = []
    for line in summary_lines:
        lower = line.lower()
        if any(
            k in lower
            for k in ("mg", "increased", "decreased", "started", "stopped", "dose", "→", "prescribed")
        ):
            if line.strip() not in changes:
                changes.append(line.strip())
    if not changes and chart_text:
        for sentence in re.split(r"[.!?]\s+", chart_text):
            lower = sentence.lower()
            if any(k in lower for k in ("mg", "increased", "medication", "amlodipine", "metformin")):
                changes.append(sentence.strip())
                if len(changes) >= 3:
                    break
    return changes[:6]


def _extract_precautions_from_summary(summary_lines: list[str]) -> list[str]:
    found = []
    for line in summary_lines:
        lower = line.lower()
        if any(k in lower for k in ("don't", "do not", "avoid", "call", "warning", "without", "stop", "limit")):
            found.append(line.strip())
    return found


def _build_after_visit_report(
    *,
    visit: dict | None,
    doctor: dict,
    summary_lines: list[str],
    chart_text: str,
    tasks: list[dict],
    tips: list[dict],
    condition: str,
) -> dict:
    visit_reason = (visit or {}).get("visit_reason") or "Follow-up visit"
    if "portal demo" in visit_reason.lower():
        visit_reason = "Hypertension follow-up"

    med_changes = _extract_medication_changes(summary_lines, chart_text)
    summary_precautions = _extract_precautions_from_summary(summary_lines)
    condition_precautions = PORTAL_CONFIG.get("conditionPrecautions", {}).get(
        condition,
        PORTAL_CONFIG.get("conditionPrecautions", {}).get("default", []),
    )
    precautions = list(dict.fromkeys(summary_precautions + condition_precautions))

    key_findings = [ln for ln in summary_lines if ln not in med_changes and ln not in summary_precautions]
    if not key_findings:
        key_findings = list(summary_lines)

    return {
        "title": "After-Visit Report",
        "visitReason": visit_reason,
        "keyFindings": key_findings[:6],
        "medicationChanges": med_changes,
        "precautions": precautions,
        "doctorRemarks": doctor.get("note") or "",
        "followUpTasks": [t.get("title") or t.get("description", "") for t in tasks],
        "lifestyleGuidance": [
            {"title": t["title"], "detail": t["detail"]} for t in tips[:6]
        ],
        "emergencyNotice": PORTAL_CONFIG.get(
            "emergencyNotice",
            "If you are experiencing a medical emergency, call 911.",
        ),
    }


def _doctor_note(patient_first: str, visit: dict | None) -> str:
    reason = (visit or {}).get("visit_reason") or ""
    if "portal demo" in reason.lower():
        return (
            f"Great seeing you today, {patient_first}. Let's really focus on tracking "
            "that morning blood pressure before our next check-in."
        )
    if visit and visit.get("visit_reason"):
        return (
            f"Thanks for coming in today, {patient_first}. "
            f"We'll follow up on {visit['visit_reason'].lower()} before your next check-in."
        )
    return (
        f"Great seeing you today, {patient_first}. "
        "Please complete the tasks below so we can review your progress at your next visit."
    )


def _response_date(submitted_at: str) -> str:
    return (submitted_at or "")[:10]


def _infer_frequency(task: dict) -> str:
    freq = (task.get("frequency") or "").lower()
    if freq in ("daily", "weekly", "once"):
        return freq
    desc = (task.get("description") or "").lower()
    if task.get("type") == "recurring_input":
        return "daily"
    if any(k in desc for k in ("weekly", "once a week", "each week")):
        return "weekly"
    if any(
        k in desc
        for k in ("daily", "each morning", "every day", "each day", "log each")
    ):
        return "daily"
    return "once"


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _logged_in_period(frequency: str, logged_dates: set[str], today: date) -> bool:
    if frequency == "daily":
        return today.isoformat() in logged_dates
    if frequency == "weekly":
        ws = _week_start(today)
        for i in range(7):
            if (ws + timedelta(days=i)).isoformat() in logged_dates:
                return True
    return False


def _current_streak(logged_dates: set[str], today: date) -> int:
    streak = 0
    d = today
    while d.isoformat() in logged_dates:
        streak += 1
        d -= timedelta(days=1)
    return streak


def _global_streak(active_dates: set[str], today: date) -> int:
    streak = 0
    d = today
    while d.isoformat() in active_dates:
        streak += 1
        d -= timedelta(days=1)
    return streak


def _build_progress_calendar(
    patient_id: int, tasks_mapped: list[dict], today: date
) -> dict:
    all_responses = db.get_responses_for_patient_tasks(patient_id)
    task_titles = {t.get("dbTaskId"): t.get("title", "Task") for t in tasks_mapped}

    entries_by_date: dict[str, list[dict]] = {}
    for r in all_responses:
        d = _response_date(r["submitted_at"])
        entries_by_date.setdefault(d, []).append(
            {
                "taskId": f"task_{r['task_id']}",
                "title": task_titles.get(r["task_id"], "Task"),
                "value": r.get("value") or "",
                "time": r["submitted_at"][11:16] if len(r["submitted_at"]) > 16 else "",
            }
        )

    active_dates = set(entries_by_date.keys())
    week_start = _week_start(today)
    this_week_count = sum(
        1
        for d in active_dates
        if week_start <= date.fromisoformat(d) <= today
    )

    year, month = today.year, today.month
    _, num_days = calendar.monthrange(year, month)
    days = []
    for day in range(1, num_days + 1):
        d = date(year, month, day).isoformat()
        entries = entries_by_date.get(d, [])
        days.append({"date": d, "count": len(entries), "entries": entries})

    return {
        "month": today.strftime("%Y-%m"),
        "today": today.isoformat(),
        "stats": {
            "currentStreak": _global_streak(active_dates, today),
            "thisWeekCount": this_week_count,
            "totalLogs": len(all_responses),
        },
        "days": days,
        "entriesByDate": entries_by_date,
    }


def _infer_task_type(task: dict, responses: list[dict]) -> str:
    desc = (task.get("description") or "").lower()
    metric = (task.get("target_metric") or "").lower()
    task_type = task.get("type", "confirmation")

    if task_type == "upload":
        return "file_upload"
    if any(k in desc for k in ("upload", "report", "document", "file")):
        return "file_upload"
    if any(k in desc for k in ("notes from", "another doctor", "specialist note")):
        return "notes_textarea"
    if task_type == "recurring_input" and any(
        k in metric or k in desc
        for k in ("bp", "blood pressure", "glucose", "reading", "weight")
    ):
        return "bp_log"
    if task_type == "recurring_input":
        return "bp_log"
    if task_type == "confirmation" and any(k in desc for k in ("note", "specialist")):
        return "notes_textarea"
    return "checkbox"


def _task_payload(task_type: str, responses: list[dict]) -> Any:
    if task_type == "file_upload":
        if responses:
            return responses[-1].get("value")
        return None
    if task_type == "bp_log":
        readings = []
        for r in responses:
            val = r.get("value") or ""
            bp = _parse_bp(val)
            if bp:
                readings.append({**bp, "note": val})
            else:
                readings.append({"raw": val})
        return readings
    if task_type == "notes_textarea":
        text = ""
        attachment = None
        for r in responses:
            val = r.get("value") or ""
            if val.startswith("attachment:"):
                attachment = val.replace("attachment:", "", 1).strip()
            else:
                text = val
        return {"text": text, "attachment": attachment}
    return None


def _map_db_task(task: dict, today: date | None = None) -> dict:
    today = today or db.get_demo_date()
    responses = db.get_responses_for_task(task["id"])
    portal_type = _infer_task_type(task, responses)
    frequency = _infer_frequency(task)
    is_recurring = frequency in ("daily", "weekly")

    logged_dates = {_response_date(r["submitted_at"]) for r in responses}
    logged_in_period = _logged_in_period(frequency, logged_dates, today)
    streak = _current_streak(logged_dates, today) if is_recurring else 0

    if is_recurring:
        is_done = logged_in_period
    else:
        is_done = task.get("status") == "done" or len(responses) > 0

    mapped: dict = {
        "id": f"task_{task['id']}",
        "dbTaskId": task["id"],
        "type": portal_type,
        "title": task["description"],
        "frequency": frequency,
        "isRecurring": is_recurring,
        "loggedInPeriod": logged_in_period,
        "loggedDates": sorted(logged_dates),
        "streak": streak,
        "isCompleted": is_done,
    }

    if portal_type == "file_upload":
        mapped["payload"] = _task_payload(portal_type, responses)
    elif portal_type == "bp_log":
        mapped["payload"] = _task_payload(portal_type, responses)
    elif portal_type == "notes_textarea":
        mapped["payload"] = _task_payload(portal_type, responses) or {
            "text": "",
            "attachment": None,
        }

    return mapped


def build_portal_payload(token: str, token_data: dict) -> dict | None:
    """Assemble full portal JSON from secure token context."""
    patient = db.get_patient(token_data["patient_id"])
    if not patient:
        return None

    visit_id = token_data.get("visit_id")
    visit = db.get_visit(visit_id) if visit_id else None
    if not visit:
        latest = db.get_latest_visit(token_data["patient_id"])
        visit = latest

    first, last = _split_name(patient["name"])
    today = db.get_demo_date()

    chart_text = (visit or {}).get("chart_entry_text") or ""
    summary_text = (visit or {}).get("patient_summary_text") or ""
    current_bp = _parse_bp(chart_text) or _parse_bp(summary_text)

    condition = (patient.get("condition") or "default").lower()
    target_bp = PORTAL_CONFIG["bpTargets"].get(
        condition, PORTAL_CONFIG["bpTargets"]["default"]
    )

    tasks_raw = db.get_tasks_for_visit(visit["id"]) if visit else []
    if not tasks_raw and visit:
        tasks_raw = db.get_pending_tasks_for_visit(visit["id"])

    tasks = [_map_db_task(t, today) for t in tasks_raw]

    last_date = visit["visit_date"] if visit else today.isoformat()
    next_days = PORTAL_CONFIG.get("nextVisitDaysDefault", 28)
    if tasks_raw:
        due_dates = [date.fromisoformat(t["due_date"]) for t in tasks_raw]
        next_date = max(due_dates).isoformat()
    else:
        next_date = (date.fromisoformat(last_date) + timedelta(days=next_days)).isoformat()

    doctor = dict(PORTAL_CONFIG["doctor"])
    doctor["note"] = _doctor_note(first, visit)

    after_visit_report = _build_after_visit_report(
        visit=visit,
        doctor=doctor,
        summary_lines=_summary_lines(summary_text),
        chart_text=chart_text,
        tasks=tasks,
        tips=_tips_for_condition(condition),
        condition=condition,
    )

    return {
        "token": token,
        "metadata": {
            "patient": {
                "id": f"pat_{patient['id']}",
                "firstName": first,
                "lastName": last,
            },
            "doctor": doctor,
            "visit": {
                "lastDate": last_date,
                "nextDate": next_date,
                "metrics": {
                    "currentBP": current_bp or {"systolic": 0, "diastolic": 0},
                    "targetBP": target_bp,
                    "status": _bp_status(current_bp or {}, target_bp)
                    if current_bp
                    else "neutral",
                },
                "summaryPlain": _summary_lines(summary_text),
            },
            "afterVisitReport": after_visit_report,
        },
        "tasks": tasks,
        "progressCalendar": _build_progress_calendar(
            token_data["patient_id"], tasks, today
        ),
        "tips": _tips_for_condition(condition),
    }


def _tips_for_condition(condition: str) -> list[dict]:
    """Return tips; diabetes gets diet-focused subset ordering."""
    if condition == "diabetes":
        order = ["tip_1", "tip_4", "tip_2", "tip_3", "tip_5", "tip_6"]
        by_id = {t["id"]: t for t in PORTAL_TIPS}
        return [by_id[i] for i in order if i in by_id]
    return list(PORTAL_TIPS)


def persist_task_submission(db_task_id: int, portal_type: str, payload: dict) -> None:
    """Write patient portal task completion back to followup_responses."""
    if portal_type == "checkbox":
        db.submit_followup_response(
            task_id=db_task_id,
            response_type="confirmation",
            value=payload.get("note") or "Patient confirmed task completed",
            unit=None,
        )
    elif portal_type == "file_upload":
        filename = payload.get("filename") or "uploaded file"
        db.submit_followup_response(
            task_id=db_task_id,
            response_type="confirmation",
            value=f"Uploaded: {filename}",
            unit=None,
        )
    elif portal_type == "bp_log":
        reading = payload.get("reading") or {}
        sys_val = reading.get("systolic")
        dia_val = reading.get("diastolic")
        note = reading.get("note", "")
        value = f"{sys_val}/{dia_val} mmHg"
        if note:
            value += f" — {note}"
        db.submit_followup_response(
            task_id=db_task_id,
            response_type="reading",
            value=value,
            unit="mmHg",
        )
    elif portal_type == "notes_textarea":
        text = (payload.get("text") or "").strip()
        attachment = payload.get("attachment")
        if attachment:
            db.submit_followup_response(
                task_id=db_task_id,
                response_type="confirmation",
                value=f"attachment:{attachment}",
                unit=None,
            )
        if text:
            db.submit_followup_response(
                task_id=db_task_id,
                response_type="confirmation",
                value=text,
                unit=None,
            )
        elif not attachment:
            db.submit_followup_response(
                task_id=db_task_id,
                response_type="confirmation",
                value="Notes saved",
                unit=None,
            )
