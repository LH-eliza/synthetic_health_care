"""
rules_engine.py — ALL deterministic clinical logic. Zero LLM calls.

Every function here is pure Python: deterministic, unit-testable, auditable.
The LLM never computes task status, screening due-dates, or lab relevance —
those classifications are performed here and handed to llm_components.py
as already-structured data for language generation only.

Functions:
  get_cst_status(patient, today)           -> ScreeningResult
  get_mammogram_status(patient, today)     -> ScreeningResult
  get_colonoscopy_status(patient, today)   -> ScreeningResult
  get_result_status(patient)               -> list[LabResult]
  compute_task_diff(prior_tasks, followup_responses, today) -> list[TaskDiff]
  get_relevant_lab_alerts(patient, result_statuses, condition_test_map) -> list[LabResult]
  get_condition_monitoring_alert(patient, today) -> ConditionAlert | None
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from config import CONDITION_TEST_MAP, SCREENING_INTERVALS


# ---------------------------------------------------------------------------
# Return types — plain dataclasses, serializable to dict for JSON responses
# ---------------------------------------------------------------------------

@dataclass
class ScreeningResult:
    name: str
    status: str          # "due" | "overdue" | "up_to_date" | "not_applicable"
    reasoning: str       # plain string, matches existing get_cst_status pattern
    next_due: Optional[str] = None   # ISO date or None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "reasoning": self.reasoning,
            "next_due": self.next_due,
        }


@dataclass
class LabResult:
    test: str
    status: str          # "resulted" | "pending" | "overdue_pending"
    value: Optional[str]
    unit: Optional[str]
    flag: Optional[str]  # "above_target" | "elevated" | "normal" | None
    reasoning: str

    def to_dict(self) -> dict:
        return {
            "test": self.test,
            "status": self.status,
            "value": self.value,
            "unit": self.unit,
            "flag": self.flag,
            "reasoning": self.reasoning,
        }


@dataclass
class TaskDiff:
    task_id: int
    task_description: str
    status: str          # "done" | "overdue" | "no_data"
    reasoning: str       # plain string — same discipline as ScreeningResult.reasoning

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "task_description": self.task_description,
            "status": self.status,
            "reasoning": self.reasoning,
        }


@dataclass
class ConditionAlert:
    condition: str
    alert_type: str      # e.g. "monitoring_due" | "lab_flag"
    description: str
    reasoning: str

    def to_dict(self) -> dict:
        return {
            "condition": self.condition,
            "alert_type": self.alert_type,
            "description": self.description,
            "reasoning": self.reasoning,
        }


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _age(dob_str: str, today: date) -> int:
    dob = date.fromisoformat(dob_str)
    return (
        today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    )


# ---------------------------------------------------------------------------
# Screening functions
# ---------------------------------------------------------------------------

def get_cst_status(patient: dict, today: date | None = None) -> ScreeningResult:
    """
    Cervical Screening Test — recommended every 3 years starting at age 21 (female patients).
    Checks snapshot for last_cst date; if not present, patient is overdue from age 21.
    """
    if today is None:
        today = date.today()

    name = "Cervical Screening Test (CST)"
    cfg = SCREENING_INTERVALS["cst"]

    if patient.get("sex", "").upper() not in ("F", "FEMALE"):
        return ScreeningResult(
            name=name,
            status="not_applicable",
            reasoning="CST not applicable: patient sex is not recorded as female.",
        )

    age = _age(patient["dob"], today)
    if age < cfg["start_age"]:
        return ScreeningResult(
            name=name,
            status="not_applicable",
            reasoning=f"CST not applicable: patient is {age} years old (screening starts at {cfg['start_age']}).",
        )

    # Pull last CST from snapshot (chart_snapshots.data.last_cst)
    snap_data = patient.get("snapshot_data", {})
    last_cst_str = snap_data.get("last_cst")

    if not last_cst_str:
        return ScreeningResult(
            name=name,
            status="overdue",
            reasoning=f"No CST on record. Patient is {age} years old; screening should have started at age {cfg['start_age']}.",
        )

    last_cst = date.fromisoformat(last_cst_str)
    next_due = last_cst + timedelta(days=cfg["interval_years"] * 365)

    if today >= next_due:
        days_overdue = (today - next_due).days
        return ScreeningResult(
            name=name,
            status="overdue",
            reasoning=f"Last CST was {last_cst.isoformat()}. Next due {next_due.isoformat()} — {days_overdue} days overdue.",
            next_due=next_due.isoformat(),
        )
    elif (next_due - today).days <= 90:
        return ScreeningResult(
            name=name,
            status="due",
            reasoning=f"Last CST was {last_cst.isoformat()}. Next due {next_due.isoformat()} — due within 90 days.",
            next_due=next_due.isoformat(),
        )
    else:
        return ScreeningResult(
            name=name,
            status="up_to_date",
            reasoning=f"Last CST was {last_cst.isoformat()}. Next due {next_due.isoformat()}.",
            next_due=next_due.isoformat(),
        )


def get_mammogram_status(patient: dict, today: date | None = None) -> ScreeningResult:
    """
    Mammogram — recommended every 2 years starting at age 40 (female patients).
    """
    if today is None:
        today = date.today()

    name = "Mammogram"
    cfg = SCREENING_INTERVALS["mammogram"]

    if patient.get("sex", "").upper() not in ("F", "FEMALE"):
        return ScreeningResult(
            name=name,
            status="not_applicable",
            reasoning="Mammogram not applicable: patient sex is not recorded as female.",
        )

    age = _age(patient["dob"], today)
    if age < cfg["start_age"]:
        return ScreeningResult(
            name=name,
            status="not_applicable",
            reasoning=f"Mammogram not applicable: patient is {age} years old (screening starts at {cfg['start_age']}).",
        )

    snap_data = patient.get("snapshot_data", {})
    last_mammo_str = snap_data.get("last_mammogram")

    if not last_mammo_str:
        return ScreeningResult(
            name=name,
            status="overdue",
            reasoning=f"No mammogram on record. Patient is {age} years old; screening should have started at age {cfg['start_age']}.",
        )

    last_mammo = date.fromisoformat(last_mammo_str)
    next_due = last_mammo + timedelta(days=cfg["interval_years"] * 365)

    if today >= next_due:
        days_overdue = (today - next_due).days
        return ScreeningResult(
            name=name,
            status="overdue",
            reasoning=f"Last mammogram {last_mammo.isoformat()}. Next due {next_due.isoformat()} — {days_overdue} days overdue.",
            next_due=next_due.isoformat(),
        )
    elif (next_due - today).days <= 90:
        return ScreeningResult(
            name=name,
            status="due",
            reasoning=f"Last mammogram {last_mammo.isoformat()}. Next due {next_due.isoformat()} — due within 90 days.",
            next_due=next_due.isoformat(),
        )
    else:
        return ScreeningResult(
            name=name,
            status="up_to_date",
            reasoning=f"Last mammogram {last_mammo.isoformat()}. Next due {next_due.isoformat()}.",
            next_due=next_due.isoformat(),
        )


def get_colonoscopy_status(patient: dict, today: date | None = None) -> ScreeningResult:
    """
    Colonoscopy — recommended every 10 years starting at age 50.
    """
    if today is None:
        today = date.today()

    name = "Colonoscopy"
    cfg = SCREENING_INTERVALS["colonoscopy"]
    age = _age(patient["dob"], today)

    if age < cfg["start_age"]:
        return ScreeningResult(
            name=name,
            status="not_applicable",
            reasoning=f"Colonoscopy not applicable: patient is {age} years old (screening starts at {cfg['start_age']}).",
        )

    snap_data = patient.get("snapshot_data", {})
    last_col_str = snap_data.get("last_colonoscopy")

    if not last_col_str:
        return ScreeningResult(
            name=name,
            status="overdue",
            reasoning=f"No colonoscopy on record. Patient is {age} years old; screening should have started at age {cfg['start_age']}.",
        )

    last_col = date.fromisoformat(last_col_str)
    next_due = last_col + timedelta(days=cfg["interval_years"] * 365)

    if today >= next_due:
        days_overdue = (today - next_due).days
        return ScreeningResult(
            name=name,
            status="overdue",
            reasoning=f"Last colonoscopy {last_col.isoformat()}. Next due {next_due.isoformat()} — {days_overdue} days overdue.",
            next_due=next_due.isoformat(),
        )
    elif (next_due - today).days <= 180:
        return ScreeningResult(
            name=name,
            status="due",
            reasoning=f"Last colonoscopy {last_col.isoformat()}. Next due {next_due.isoformat()} — due within 6 months.",
            next_due=next_due.isoformat(),
        )
    else:
        return ScreeningResult(
            name=name,
            status="up_to_date",
            reasoning=f"Last colonoscopy {last_col.isoformat()}. Next due {next_due.isoformat()}.",
            next_due=next_due.isoformat(),
        )


def get_result_status(patient: dict) -> list[LabResult]:
    """
    Parse pending_labs from patient risk_flags_data and return structured LabResult list.
    Input format mirrors what db.py stores in risk_flags_json for seeded patients.
    """
    risk_data = patient.get("risk_flags_data", {})
    if isinstance(risk_data, list):
        # Old format — no lab data
        return []

    pending_labs = risk_data.get("pending_labs", [])
    results = []
    for lab in pending_labs:
        test = lab.get("test", "Unknown")
        status = lab.get("status", "pending")
        value = lab.get("value")
        unit = lab.get("unit")
        flag = lab.get("flag")

        if status == "resulted" and flag and flag != "normal":
            reasoning = (
                f"{test} resulted: {value} {unit or ''}. "
                f"Flag: {flag.replace('_', ' ')}. Review required."
            )
        elif status == "pending":
            ordered = lab.get("ordered_date", "unknown date")
            reasoning = f"{test} ordered {ordered}, result not yet received."
        else:
            reasoning = f"{test} resulted: {value} {unit or ''} (within normal range)."

        results.append(LabResult(
            test=test,
            status=status,
            value=value,
            unit=unit,
            flag=flag,
            reasoning=reasoning,
        ))

    return results


# ---------------------------------------------------------------------------
# Task diff (NEW — Challenge 4 / Flow B step 3)
# ---------------------------------------------------------------------------

def compute_task_diff(
    prior_tasks: list[dict],
    followup_responses: list[dict],
    today: date,
) -> list[TaskDiff]:
    """
    For each task in prior_tasks, determine completion status deterministically.

    Rules (applied in order):
      1. If any followup_response exists for this task_id with submitted_at <= today:
         → status = "done"
         reasoning: "Response received on <date>: <value>"
      2. Else if task.due_date < today:
         → status = "overdue"
         reasoning: "Due <date> — no response received as of <today>"
      3. Else:
         → status = "no_data"
         reasoning: "No response yet; due date <date> not yet passed"

    Returns list of TaskDiff — one entry per task, deterministic, zero LLM.
    """
    # Index responses by task_id for O(1) lookup
    responses_by_task: dict[int, list[dict]] = {}
    for resp in followup_responses:
        tid = resp["task_id"]
        responses_by_task.setdefault(tid, []).append(resp)

    diffs = []
    for task in prior_tasks:
        task_id = task["id"]
        task_due = date.fromisoformat(task["due_date"])
        desc = task["description"]

        task_responses = responses_by_task.get(task_id, [])
        # Filter to responses submitted on or before today
        valid_responses = [
            r for r in task_responses
            if r["submitted_at"][:10] <= today.isoformat()
        ]

        if valid_responses:
            # Earliest valid response
            resp = sorted(valid_responses, key=lambda r: r["submitted_at"])[0]
            resp_date = resp["submitted_at"][:10]
            resp_value = resp.get("value") or "confirmed"
            reasoning = f"Response received {resp_date}: {resp_value}"
            status = "done"
        elif task_due < today:
            days_overdue = (today - task_due).days
            reasoning = f"Due {task_due.isoformat()} — no response received as of {today.isoformat()} ({days_overdue} days overdue)"
            status = "overdue"
        else:
            days_remaining = (task_due - today).days
            reasoning = f"No response yet; due {task_due.isoformat()} ({days_remaining} days remaining)"
            status = "no_data"

        diffs.append(TaskDiff(
            task_id=task_id,
            task_description=desc,
            status=status,
            reasoning=reasoning,
        ))

    return diffs


# ---------------------------------------------------------------------------
# Lab alert filtering (NEW — Flow B chip 3)
# ---------------------------------------------------------------------------

def get_relevant_lab_alerts(
    patient: dict,
    all_result_statuses: list[LabResult],
    condition_test_map: dict[str, list[str]] | None = None,
) -> list[LabResult]:
    """
    Filter get_result_status() output to only tests relevant to patient.condition.
    Uses CONDITION_TEST_MAP from config.py — no logic hardcoded here.

    If patient has no condition or condition not in map, returns flagged results only
    (safe fallback: never hide a flagged result, just don't add noise).
    """
    if condition_test_map is None:
        condition_test_map = CONDITION_TEST_MAP

    condition = (patient.get("condition") or "").lower()
    relevant_tests = condition_test_map.get(condition, [])

    if relevant_tests:
        return [r for r in all_result_statuses if r.test in relevant_tests]
    else:
        # No condition map entry — fall back to flagged results only
        return [r for r in all_result_statuses if r.flag and r.flag != "normal"]


# ---------------------------------------------------------------------------
# Condition monitoring alert (Flow B chip 1)
# ---------------------------------------------------------------------------

def get_condition_monitoring_alert(
    patient: dict,
    today: date | None = None,
) -> ConditionAlert | None:
    """
    For a known chronic condition, determine if routine monitoring is due.
    Rules-based: uses last visit date and condition-specific monitoring intervals.

    Returns ConditionAlert or None (if no condition, or monitoring up to date).
    """
    if today is None:
        today = date.today()

    condition = (patient.get("condition") or "").lower()
    if not condition:
        return None

    # Condition-specific monitoring intervals (in days)
    monitoring_intervals = {
        "diabetes": {
            "label": "HbA1c monitoring",
            "interval_days": 90,
            "description": "Diabetic patient — HbA1c due every 3 months",
        },
        "hypertension": {
            "label": "BP + renal panel",
            "interval_days": 180,
            "description": "Hypertensive patient — renal panel and BP review due every 6 months",
        },
        "asthma": {
            "label": "Spirometry / peak flow review",
            "interval_days": 365,
            "description": "Asthma patient — annual spirometry review due",
        },
        "hyperlipidemia": {
            "label": "Lipid panel",
            "interval_days": 365,
            "description": "Hyperlipidemia patient — annual lipid panel due",
        },
        "ckd": {
            "label": "eGFR + urine ACR",
            "interval_days": 90,
            "description": "CKD patient — quarterly eGFR and urine ACR monitoring due",
        },
    }

    cfg = monitoring_intervals.get(condition)
    if not cfg:
        return ConditionAlert(
            condition=condition,
            alert_type="monitoring_due",
            description=f"Chronic condition: {condition}",
            reasoning=f"Patient has chronic condition '{condition}'. Review condition-specific monitoring at this visit.",
        )

    # Check last visit date vs interval
    snap_data = patient.get("snapshot_data", {})
    last_monitoring_str = snap_data.get(f"last_{condition}_monitoring")

    if not last_monitoring_str:
        return ConditionAlert(
            condition=condition,
            alert_type="monitoring_due",
            description=cfg["description"],
            reasoning=f"No prior {cfg['label']} date on record for this patient. Due now.",
        )

    last_monitoring = date.fromisoformat(last_monitoring_str)
    next_due = last_monitoring + timedelta(days=cfg["interval_days"])

    if today >= next_due:
        days_overdue = (today - next_due).days
        return ConditionAlert(
            condition=condition,
            alert_type="monitoring_due",
            description=cfg["description"],
            reasoning=f"{cfg['label']} last done {last_monitoring.isoformat()}. Due {next_due.isoformat()} — {days_overdue} days overdue.",
        )

    return None


# ---------------------------------------------------------------------------
# Aggregate pre-visit chips for Flow B
# ---------------------------------------------------------------------------

def build_previsit_chips(patient: dict, prior_tasks: list[dict], responses: list[dict], today: date) -> dict:
    """
    Compute all three Flow B pre-visit chips in one call.
    Returns dict with keys: condition_alert, task_diff, lab_alerts
    All deterministic — no LLM involved.
    """
    # Chip 1: Condition trigger
    condition_alert = get_condition_monitoring_alert(patient, today)

    # Chip 2: Follow-up status (task diff)
    task_diffs = compute_task_diff(prior_tasks, responses, today)

    # Chip 3: Lab alerts filtered by condition
    all_results = get_result_status(patient)
    relevant_labs = get_relevant_lab_alerts(patient, all_results)

    # Also get relevant screenings
    screenings = []
    for fn in [get_cst_status, get_mammogram_status, get_colonoscopy_status]:
        s = fn(patient, today)
        if s.status in ("due", "overdue"):
            screenings.append(s.to_dict())

    return {
        "condition_alert": condition_alert.to_dict() if condition_alert else None,
        "task_diffs": [t.to_dict() for t in task_diffs],
        "lab_alerts": [r.to_dict() for r in relevant_labs],
        "screenings": screenings,
    }


def get_ed_continuity_alert(patient: dict, today: date) -> dict | None:
    """
    Unresolved ED discharge with no downstream follow-up booked.
    Deterministic demo data for continuity-of-care presentation (Marcus Rivera).
    """
    flags = patient.get("risk_flags_data") or {}
    stored = flags.get("ed_continuity")
    if stored:
        return {
            "severity": stored.get("severity", "critical"),
            "title": "Unresolved Emergency Department Continuity Alert",
            "facility": stored.get("facility", "Ottawa Hospital ED"),
            "discharge_date": stored.get("discharge_date"),
            "diagnosis": stored.get("diagnosis"),
            "message": stored.get("message"),
        }

    if patient.get("name") != "Marcus Rivera":
        return None

    discharge_date = "2026-06-12"
    diagnosis = "Acute Shortness of Breath / Asthma Exacerbation"
    return {
        "severity": "critical",
        "title": "Unresolved Emergency Department Continuity Alert",
        "facility": "Ottawa Hospital ED",
        "discharge_date": discharge_date,
        "diagnosis": diagnosis,
        "message": (
            f"Discharge Summary received from Ottawa Hospital ED ({discharge_date}) "
            f"for '{diagnosis}'. Patient was stabilized and discharged, but no "
            f"post-hospitalization follow-up visit or asthma titration review has been booked."
        ),
    }


def get_patient_intake_message(visit_reason: str, patient: dict) -> str:
    """Simulated patient self-report from kiosk check-in, keyed to visit reason."""
    reason = (visit_reason or "").lower()
    name = patient.get("name", "Patient").split()[0]

    if "mental" in reason or "stress" in reason or "check-in" in reason:
        return (
            "I am here for a mental health check-in because work has been super stressful, "
            "but also my asthma has been playing up again since I got out of the hospital last week."
        )
    if "asthma" in reason or "breath" in reason or "ed" in reason or "hospital" in reason:
        return (
            "My breathing got really bad after I left the ER last week. I have my rescue inhaler "
            "but I am not sure my asthma plan is right anymore."
        )
    if "diabetes" in reason or "metformin" in reason or "medication" in reason:
        return (
            f"I'm here about my diabetes meds — the Metformin dose change didn't happen and "
            f"my sugars have been all over the place."
        )
    return (
        f"Hi, I'm {name}. I'm here today because: {visit_reason or 'follow-up as scheduled'}."
    )


def build_executive_brief(
    patient: dict,
    chips: dict,
    latest_visit: dict | None,
    today: date,
) -> dict:
    """
    Condensed physician-facing executive brief derived from pre-visit chips.
    Deterministic — no LLM.
    """
    condition = (patient.get("condition") or "chronic condition").replace("_", " ")
    priority_actions: list[str] = []
    breakdown: list[dict] = []

    overdue = [t for t in chips.get("task_diffs", []) if t.get("status") == "overdue"]
    pending = [t for t in chips.get("task_diffs", []) if t.get("status") in ("pending", "no_data")]
    labs = chips.get("lab_alerts", [])
    alert = chips.get("condition_alert")
    ed_alert = get_ed_continuity_alert(patient, today)

    if ed_alert:
        priority_actions.insert(0, (
            f"Reconcile ED discharge ({ed_alert['discharge_date']}): "
            f"book post-hospitalization follow-up and asthma titration review"
        ))
        breakdown.insert(0, {
            "category": "ED Continuity — Unresolved",
            "detail": ed_alert["message"],
            "status": "overdue",
        })

    for t in overdue:
        priority_actions.append(f"Address overdue care plan item: {t['task_description']}")
        breakdown.append({
            "category": "Care Plan — Overdue",
            "detail": t.get("reasoning") or t["task_description"],
            "status": "overdue",
        })

    for lab in labs:
        val = f" {lab['value']}{lab.get('unit') or ''}" if lab.get("value") else ""
        priority_actions.append(f"Review abnormal result: {lab['test']}{val}")
        breakdown.append({
            "category": f"Laboratory — {lab['test']}",
            "detail": lab.get("reasoning", "Result flagged for clinical review"),
            "status": "overdue",
        })

    if alert:
        priority_actions.append(alert.get("description", "Condition monitoring alert active"))
        breakdown.append({
            "category": "Condition Monitoring",
            "detail": alert.get("reasoning", alert.get("description", "")),
            "status": "pending",
        })

    for t in pending[:2]:
        breakdown.append({
            "category": "Care Plan — Pending",
            "detail": t.get("reasoning") or t["task_description"],
            "status": t.get("status", "pending"),
        })

    if latest_visit:
        breakdown.append({
            "category": "Prior Encounter",
            "detail": f"{latest_visit.get('visit_date', 'N/A')} — {latest_visit.get('visit_reason') or 'No chief complaint recorded'}",
            "status": "done",
        })

    if overdue:
        impression = (
            f"Returning patient with {condition}; {len(overdue)} overdue care plan item(s) "
            f"require reconciliation at today's encounter."
        )
    elif ed_alert:
        impression = (
            f"Returning patient with {condition}; recent ED discharge without booked "
            f"post-hospitalization follow-up — continuity gap requires closure today."
        )
    elif labs:
        impression = (
            f"Returning patient with {condition}; abnormal laboratory values identified "
            f"requiring physician review."
        )
    elif alert:
        impression = f"Returning patient with {condition}; active monitoring alert on file."
    else:
        impression = f"Returning patient with {condition}; care plan current — routine continuity visit."

    if not priority_actions:
        priority_actions.append("No critical flags — proceed with interval history and examination.")

    return {
        "impression": impression,
        "priority_actions": priority_actions[:4],
        "breakdown": breakdown,
        "patient_label": patient.get("name", "Patient"),
        "condition": condition,
        "ed_alert": ed_alert,
    }
