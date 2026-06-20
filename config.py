"""
config.py — static lookup tables for condition-specific logic.

Adding a new condition: add an entry to CONDITION_TEST_MAP.
The rules engine uses this to filter lab alerts to only tests
relevant to a patient's known condition(s). No hardcoded inline
logic — all condition-specific wiring lives here.
"""

import json
import os

# ---------------------------------------------------------------------------
# Condition → relevant lab tests mapping
# Used by rules_engine.get_relevant_lab_alerts() to filter get_result_status()
# output to only tests clinically meaningful for a given condition.
# ---------------------------------------------------------------------------
CONDITION_TEST_MAP: dict[str, list[str]] = {
    "diabetes": [
        "HbA1c",
        "fasting_glucose",
        "creatinine",
        "urine_ACR",
        "LDL",
        "eGFR",
        "urine_albumin",
    ],
    "hypertension": [
        "creatinine",
        "potassium",
        "eGFR",
        "sodium",
        "urine_ACR",
    ],
    "asthma": [
        "spirometry",
        "peak_flow",
        "eosinophil_count",
    ],
    "hyperlipidemia": [
        "LDL",
        "HDL",
        "total_cholesterol",
        "triglycerides",
    ],
    "ckd": [
        "creatinine",
        "eGFR",
        "potassium",
        "urine_ACR",
        "urine_albumin",
        "hemoglobin",
    ],
    "depression": [
        "TSH",
        "B12",
        "folate",
        "CBC",
    ],
}

# ---------------------------------------------------------------------------
# Screening interval parameters (used by rules_engine screening functions)
# ---------------------------------------------------------------------------
SCREENING_INTERVALS = {
    "cst": {
        "start_age": 21,
        "interval_years": 3,
        "display_name": "Cervical Screening Test",
    },
    "mammogram": {
        "start_age": 40,
        "interval_years": 2,
        "display_name": "Mammogram",
    },
    "colonoscopy": {
        "start_age": 50,
        "interval_years": 10,
        "display_name": "Colonoscopy",
    },
}

# ---------------------------------------------------------------------------
# Social history categories — loaded from external JSON so non-developers
# can edit without touching Python.
# ---------------------------------------------------------------------------
_categories_path = os.path.join(os.path.dirname(__file__), "social_history_categories.json")
with open(_categories_path) as _f:
    SOCIAL_HISTORY_CATEGORIES: list[str] = json.load(_f)

# ---------------------------------------------------------------------------
# Follow-up task types
# ---------------------------------------------------------------------------
TASK_TYPES = ["confirmation", "recurring_input", "upload"]

# Task statuses — stored in DB and computed by rules engine
TASK_STATUSES = ["pending", "done", "overdue", "no_data"]
