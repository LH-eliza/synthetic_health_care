"""
db.py — SQLite schema, connection helpers, and demo seed data.

Database file: gp_copilot.db (auto-created on first run, git-ignored).

All schema changes must be applied by calling init_db() which runs CREATE
TABLE IF NOT EXISTS — safe to call multiple times on an existing DB.
"""

import json
import os
import sqlite3
import secrets
from datetime import date, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "gp_copilot.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # rows accessible as dicts
    conn.execute("PRAGMA journal_mode=WAL")  # concurrent reads while portal writes
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create all tables if they do not exist."""
    conn = get_conn()
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS patients (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT NOT NULL,
                dob             TEXT NOT NULL,        -- ISO date YYYY-MM-DD
                sex             TEXT NOT NULL,        -- M / F / Other
                condition       TEXT,                 -- primary chronic condition
                risk_flags_json TEXT DEFAULT '[]'     -- JSON array of strings
            );

            CREATE TABLE IF NOT EXISTS visits (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id           INTEGER NOT NULL REFERENCES patients(id),
                visit_date           TEXT NOT NULL,   -- ISO date
                visit_reason         TEXT,
                chart_entry_text     TEXT,
                patient_summary_text TEXT
            );

            CREATE TABLE IF NOT EXISTS followup_tasks (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id     INTEGER NOT NULL REFERENCES patients(id),
                visit_id       INTEGER NOT NULL REFERENCES visits(id),
                description    TEXT NOT NULL,
                type           TEXT NOT NULL CHECK(type IN ('confirmation','recurring_input')),
                target_metric  TEXT,
                status         TEXT NOT NULL DEFAULT 'pending'
                                   CHECK(status IN ('pending','done','overdue','no_data')),
                due_date       TEXT NOT NULL,         -- ISO date
                created_at     TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS followup_responses (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id       INTEGER NOT NULL REFERENCES followup_tasks(id),
                submitted_at  TEXT NOT NULL,          -- ISO datetime
                response_type TEXT NOT NULL CHECK(response_type IN ('confirmation','reading')),
                value         TEXT,
                unit          TEXT
            );

            CREATE TABLE IF NOT EXISTS chart_snapshots (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id   INTEGER NOT NULL REFERENCES patients(id),
                visit_id     INTEGER,                 -- NULL for Flow A initial snapshot
                snapshot_json TEXT NOT NULL,
                created_at   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS secure_tokens (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL REFERENCES patients(id),
                visit_id   INTEGER REFERENCES visits(id),
                token      TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                used_at    TEXT
            );

            -- Demo-state: stores overrideable "today" date for demo date-advancing
            CREATE TABLE IF NOT EXISTS demo_state (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
    conn.close()


def _already_seeded() -> bool:
    conn = get_conn()
    row = conn.execute("SELECT COUNT(*) FROM patients").fetchone()
    conn.close()
    return row[0] > 0


def seed():
    """
    Insert demo patients and visit history.

    Patient 1 — Emma Chen: brand-new patient, zero visits → triggers Flow A.
    Patient 2 — Marcus Rivera: returning diabetic with visit N-1 containing
                 three follow-up tasks in mixed states (done / overdue / no_data).

    Safe to call multiple times — skips if data already present.
    """
    if _already_seeded():
        return
    conn = get_conn()
    with conn:

        # ---- Demo date default (today) ----
        conn.execute(
            "INSERT OR IGNORE INTO demo_state(key, value) VALUES (?, ?)",
            ("demo_date", date.today().isoformat()),
        )

        # ---- Patient 1: Emma Chen (new) ----
        conn.execute(
            "INSERT INTO patients(name, dob, sex, condition, risk_flags_json) VALUES (?,?,?,?,?)",
            ("Emma Chen", "1992-03-14", "F", None, json.dumps([])),
        )

        # ---- Patient 2: Marcus Rivera (returning, diabetic) ----
        conn.execute(
            "INSERT INTO patients(name, dob, sex, condition, risk_flags_json) VALUES (?,?,?,?,?)",
            (
                "Marcus Rivera",
                "1968-07-22",
                "M",
                "diabetes",
                json.dumps(["hypertension", "obesity"]),
            ),
        )

        # Retrieve Marcus's id
        marcus_id = conn.execute(
            "SELECT id FROM patients WHERE name='Marcus Rivera'"
        ).fetchone()["id"]

        # ---- Visit N-1 for Marcus (3 months ago) ----
        visit_n1_date = (date.today() - timedelta(days=90)).isoformat()
        conn.execute(
            """INSERT INTO visits(patient_id, visit_date, visit_reason,
               chart_entry_text, patient_summary_text)
               VALUES (?,?,?,?,?)""",
            (
                marcus_id,
                visit_n1_date,
                "Routine diabetes follow-up",
                # chart_entry (technical)
                (
                    "Patient presents for routine diabetes management. HbA1c result 8.2% (above target of 7.0%). "
                    "Current medications: Metformin 500mg BID. BP 138/88 mmHg. Weight stable at 94 kg. "
                    "Plan: increase Metformin to 1000mg BID, repeat HbA1c in 3 months, "
                    "request urine ACR, continue daily fasting glucose self-monitoring."
                ),
                # patient_summary (plain language)
                (
                    "Hi Marcus,\n\nHere's a summary from today's visit:\n\n"
                    "✓ Your blood sugar (HbA1c) was 8.2% — we want to get this below 7.0%.\n"
                    "✓ Your blood pressure was slightly high today.\n\n"
                    "Your tasks before the next visit:\n"
                    "[ ] Get bloodwork done (HbA1c + kidney test) at the lab\n"
                    "[ ] Increase your Metformin to 1000mg twice daily as discussed\n"
                    "[ ] Log your fasting blood sugar each morning and reply here with your readings\n\n"
                    "Your care team will review this with you at your next visit."
                ),
            ),
        )

        visit_n1_id = conn.execute(
            "SELECT id FROM visits WHERE patient_id=? ORDER BY id DESC LIMIT 1",
            (marcus_id,),
        ).fetchone()["id"]

        # ---- Follow-up tasks for visit N-1 ----
        now_iso = date.today().isoformat()

        # Task A: HbA1c bloodwork — DONE (response submitted on time)
        conn.execute(
            """INSERT INTO followup_tasks(patient_id, visit_id, description, type,
               target_metric, status, due_date, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                marcus_id,
                visit_n1_id,
                "HbA1c and urine ACR bloodwork",
                "confirmation",
                "HbA1c",
                "done",
                (date.today() - timedelta(days=60)).isoformat(),
                visit_n1_date,
            ),
        )
        task_a_id = conn.execute(
            "SELECT id FROM followup_tasks WHERE patient_id=? ORDER BY id DESC LIMIT 1",
            (marcus_id,),
        ).fetchone()["id"]

        # Task A response — bloodwork confirmed done
        conn.execute(
            """INSERT INTO followup_responses(task_id, submitted_at, response_type, value, unit)
               VALUES (?,?,?,?,?)""",
            (
                task_a_id,
                (date.today() - timedelta(days=58)).isoformat() + "T09:30:00",
                "confirmation",
                "Bloodwork completed at LifeLabs",
                None,
            ),
        )

        # Task B: Increase Metformin dose — OVERDUE (due date passed, no response)
        conn.execute(
            """INSERT INTO followup_tasks(patient_id, visit_id, description, type,
               target_metric, status, due_date, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                marcus_id,
                visit_n1_id,
                "Increase Metformin to 1000mg twice daily",
                "confirmation",
                None,
                "overdue",
                (date.today() - timedelta(days=75)).isoformat(),
                visit_n1_date,
            ),
        )

        # Task C: Daily fasting glucose logs — NO_DATA (due date not yet passed, no response)
        conn.execute(
            """INSERT INTO followup_tasks(patient_id, visit_id, description, type,
               target_metric, status, due_date, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                marcus_id,
                visit_n1_id,
                "Daily fasting glucose readings (log each morning)",
                "recurring_input",
                "fasting_glucose",
                "no_data",
                (date.today() + timedelta(days=7)).isoformat(),
                visit_n1_date,
            ),
        )

        # ---- Chart snapshot from visit N-1 ----
        snapshot = {
            "social_history": {
                "living_situation": "Lives with wife and two adult children",
                "occupation": "Retired bus driver",
                "alcohol_use": "Occasional, 1-2 drinks per week",
                "smoking": "Former smoker, quit 2012",
                "physical_activity": "Light walking 20 min/day",
            },
            "medical_history": {
                "conditions": ["Type 2 Diabetes (diagnosed 2015)", "Hypertension", "Asthma"],
                "past_surgeries": ["Appendectomy 2001"],
            },
            "medications": [
                {"name": "Metformin", "dose": "500mg", "frequency": "twice daily"},
                {"name": "Ramipril", "dose": "5mg", "frequency": "once daily"},
                {"name": "Rosuvastatin", "dose": "10mg", "frequency": "once daily"},
            ],
            "vaccines": [
                {"name": "Influenza", "date": "2025-10-15"},
                {"name": "COVID-19 booster", "date": "2024-09-01"},
            ],
            "allergies": ["Penicillin (hives)", "Sulfa drugs (rash)"],
            "family_history": ["Father: T2DM, MI at 62", "Mother: Hypertension"],
        }
        conn.execute(
            """INSERT INTO chart_snapshots(patient_id, visit_id, snapshot_json, created_at)
               VALUES (?,?,?,?)""",
            (marcus_id, visit_n1_id, json.dumps(snapshot), visit_n1_date),
        )

        # ---- Pending lab results for Marcus (for get_result_status) ----
        # Stored as risk_flags_json — simulating outstanding labs inline for demo
        # Real implementation would have a lab_results table; for hackathon this is sufficient
        conn.execute(
            "UPDATE patients SET risk_flags_json=? WHERE id=?",
            (
                json.dumps({
                    "risk_flags": ["hypertension", "obesity", "asthma"],
                    "ed_continuity": {
                        "severity": "critical",
                        "facility": "Ottawa Hospital ED",
                        "discharge_date": "2026-06-12",
                        "diagnosis": "Acute Shortness of Breath / Asthma Exacerbation",
                        "message": (
                            "Discharge Summary received from Ottawa Hospital ED (2026-06-12) "
                            "for 'Acute Shortness of Breath / Asthma Exacerbation'. Patient was "
                            "stabilized and discharged, but no post-hospitalization follow-up "
                            "visit or asthma titration review has been booked."
                        ),
                    },
                    "pending_labs": [
                        {
                            "test": "HbA1c",
                            "ordered_date": (date.today() - timedelta(days=10)).isoformat(),
                            "status": "resulted",
                            "value": "7.8",
                            "unit": "%",
                            "flag": "above_target",
                        },
                        {
                            "test": "urine_ACR",
                            "ordered_date": (date.today() - timedelta(days=10)).isoformat(),
                            "status": "resulted",
                            "value": "45",
                            "unit": "mg/mmol",
                            "flag": "elevated",
                        },
                        {
                            "test": "creatinine",
                            "ordered_date": (date.today() - timedelta(days=10)).isoformat(),
                            "status": "pending",
                            "value": None,
                            "unit": None,
                            "flag": None,
                        },
                    ],
                }),
                marcus_id,
            ),
        )

    conn.close()
    print("✓ DB seeded: Emma Chen (new patient) + Marcus Rivera (returning diabetic)")


def patch_marcus_demo_data():
    """Backfill ED continuity + asthma demo data for existing Marcus records."""
    conn = get_conn()
    row = conn.execute(
        "SELECT id, risk_flags_json FROM patients WHERE name='Marcus Rivera'"
    ).fetchone()
    if not row:
        conn.close()
        return
    try:
        flags = json.loads(row["risk_flags_json"] or "{}")
    except json.JSONDecodeError:
        flags = {}
    if flags.get("ed_continuity"):
        conn.close()
        return
    flags["ed_continuity"] = {
        "severity": "critical",
        "facility": "Ottawa Hospital ED",
        "discharge_date": "2026-06-12",
        "diagnosis": "Acute Shortness of Breath / Asthma Exacerbation",
        "message": (
            "Discharge Summary received from Ottawa Hospital ED (2026-06-12) "
            "for 'Acute Shortness of Breath / Asthma Exacerbation'. Patient was "
            "stabilized and discharged, but no post-hospitalization follow-up "
            "visit or asthma titration review has been booked."
        ),
    }
    risk_list = flags.setdefault("risk_flags", ["hypertension", "obesity"])
    if "asthma" not in risk_list:
        risk_list.append("asthma")
    with conn:
        conn.execute(
            "UPDATE patients SET risk_flags_json=? WHERE id=?",
            (json.dumps(flags), row["id"]),
        )
        snap_row = conn.execute(
            "SELECT id, snapshot_json FROM chart_snapshots WHERE patient_id=? ORDER BY id DESC LIMIT 1",
            (row["id"],),
        ).fetchone()
        if snap_row:
            snap = json.loads(snap_row["snapshot_json"])
            conds = snap.get("medical_history", {}).get("conditions", [])
            if not any("asthma" in c.lower() for c in conds):
                conds.append("Asthma")
                snap.setdefault("medical_history", {})["conditions"] = conds
                conn.execute(
                    "UPDATE chart_snapshots SET snapshot_json=? WHERE id=?",
                    (json.dumps(snap), snap_row["id"]),
                )
    conn.close()


# ---------------------------------------------------------------------------
# Query helpers used by app.py and rules_engine.py
# ---------------------------------------------------------------------------

def get_patient(patient_id: int) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM patients WHERE id=?", (patient_id,)).fetchone()
    conn.close()
    if not row:
        return None
    p = dict(row)
    try:
        p["risk_flags_data"] = json.loads(p["risk_flags_json"] or "{}")
    except Exception:
        p["risk_flags_data"] = {}
    return p


def get_all_patients() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM patients ORDER BY name").fetchall()
    conn.close()
    patients = []
    for row in rows:
        p = dict(row)
        try:
            p["risk_flags_data"] = json.loads(p["risk_flags_json"] or "{}")
        except Exception:
            p["risk_flags_data"] = {}
        patients.append(p)
    return patients


def get_visits(patient_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM visits WHERE patient_id=? ORDER BY visit_date DESC",
        (patient_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_latest_visit(patient_id: int) -> dict | None:
    visits = get_visits(patient_id)
    return visits[0] if visits else None


def get_visit(visit_id: int) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM visits WHERE id=?", (visit_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_tasks_for_visit(visit_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM followup_tasks WHERE visit_id=? ORDER BY id",
        (visit_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_responses_for_task(task_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM followup_responses WHERE task_id=? ORDER BY submitted_at",
        (task_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_responses_for_patient_tasks(patient_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT fr.* FROM followup_responses fr
           JOIN followup_tasks ft ON fr.task_id = ft.id
           WHERE ft.patient_id = ?""",
        (patient_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_latest_snapshot(patient_id: int) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM chart_snapshots WHERE patient_id=? ORDER BY id DESC LIMIT 1",
        (patient_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    snap = dict(row)
    snap["data"] = json.loads(snap["snapshot_json"])
    return snap


def get_demo_date() -> date:
    conn = get_conn()
    row = conn.execute("SELECT value FROM demo_state WHERE key='demo_date'").fetchone()
    conn.close()
    if row:
        return date.fromisoformat(row["value"])
    return date.today()


def set_demo_date(d: date):
    conn = get_conn()
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO demo_state(key, value) VALUES (?, ?)",
            ("demo_date", d.isoformat()),
        )
    conn.close()


def create_visit(patient_id: int, visit_date: str, visit_reason: str) -> int:
    conn = get_conn()
    with conn:
        cur = conn.execute(
            "INSERT INTO visits(patient_id, visit_date, visit_reason) VALUES (?,?,?)",
            (patient_id, visit_date, visit_reason),
        )
        vid = cur.lastrowid
    conn.close()
    return vid


def update_visit_notes(visit_id: int, chart_entry: str, patient_summary: str):
    conn = get_conn()
    with conn:
        conn.execute(
            "UPDATE visits SET chart_entry_text=?, patient_summary_text=? WHERE id=?",
            (chart_entry, patient_summary, visit_id),
        )
    conn.close()


def create_followup_tasks(patient_id: int, visit_id: int, tasks: list[dict]) -> list[int]:
    conn = get_conn()
    ids = []
    with conn:
        for t in tasks:
            cur = conn.execute(
                """INSERT INTO followup_tasks(patient_id, visit_id, description, type,
                   target_metric, status, due_date, created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    patient_id,
                    visit_id,
                    t["description"],
                    t.get("type", "confirmation"),
                    t.get("target_metric"),
                    "pending",
                    t["due_date"],
                    date.today().isoformat(),
                ),
            )
            ids.append(cur.lastrowid)
    conn.close()
    return ids


def create_snapshot(patient_id: int, visit_id: int | None, snapshot_data: dict):
    conn = get_conn()
    with conn:
        conn.execute(
            """INSERT INTO chart_snapshots(patient_id, visit_id, snapshot_json, created_at)
               VALUES (?,?,?,?)""",
            (patient_id, visit_id, json.dumps(snapshot_data), date.today().isoformat()),
        )
    conn.close()


def create_secure_token(patient_id: int, visit_id: int) -> str:
    token = secrets.token_urlsafe(24)
    conn = get_conn()
    with conn:
        conn.execute(
            """INSERT INTO secure_tokens(patient_id, visit_id, token, created_at)
               VALUES (?,?,?,?)""",
            (patient_id, visit_id, token, date.today().isoformat()),
        )
    conn.close()
    return token


def get_token_data(token: str) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM secure_tokens WHERE token=?", (token,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def submit_followup_response(task_id: int, response_type: str, value: str, unit: str | None):
    from datetime import datetime
    conn = get_conn()
    with conn:
        conn.execute(
            """INSERT INTO followup_responses(task_id, submitted_at, response_type, value, unit)
               VALUES (?,?,?,?,?)""",
            (task_id, datetime.now().isoformat(), response_type, value, unit),
        )
        # Update task status to done
        conn.execute(
            "UPDATE followup_tasks SET status='done' WHERE id=?",
            (task_id,),
        )
    conn.close()


def get_pending_tasks_for_visit(visit_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM followup_tasks WHERE visit_id=? AND status != 'done' ORDER BY due_date",
        (visit_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_flow_a_bins(patient_id: int, bins: dict):
    """Save confirmed Flow A bins as a chart snapshot (baseline record)."""
    create_snapshot(patient_id, None, bins)
