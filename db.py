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

DEMO_TOKEN = "demo"
MARGARET_NAME = "Margaret Thompson"


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
                type           TEXT NOT NULL CHECK(type IN ('confirmation','recurring_input','upload')),
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
    _migrate_upload_task_type()
    _migrate_task_frequency()


def _migrate_task_frequency():
    """Add frequency column for daily/weekly recurring tasks."""
    conn = get_conn()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(followup_tasks)").fetchall()}
    if "frequency" not in cols:
        with conn:
            conn.execute(
                "ALTER TABLE followup_tasks ADD COLUMN frequency TEXT NOT NULL DEFAULT 'once'"
            )
            conn.execute(
                "UPDATE followup_tasks SET frequency='daily' WHERE type='recurring_input'"
            )
            conn.execute(
                """UPDATE followup_tasks SET frequency='daily'
                   WHERE lower(description) LIKE '%daily%'
                      OR lower(description) LIKE '%each morning%'
                      OR lower(description) LIKE '%every day%'
                      OR lower(description) LIKE '%each day%'"""
            )
            conn.execute(
                """UPDATE followup_tasks SET frequency='weekly'
                   WHERE lower(description) LIKE '%weekly%'
                      OR lower(description) LIKE '%once a week%'
                      OR lower(description) LIKE '%each week%'"""
            )
    conn.close()


def _migrate_upload_task_type():
    """Add ``upload`` to followup_tasks type constraint on existing databases."""
    conn = get_conn()
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='followup_tasks'"
    ).fetchone()
    if not row or "upload" in (row[0] or ""):
        conn.close()
        return
    with conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.executescript("""
            CREATE TABLE followup_tasks_new (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id     INTEGER NOT NULL REFERENCES patients(id),
                visit_id       INTEGER NOT NULL REFERENCES visits(id),
                description    TEXT NOT NULL,
                type           TEXT NOT NULL CHECK(type IN ('confirmation','recurring_input','upload')),
                target_metric  TEXT,
                status         TEXT NOT NULL DEFAULT 'pending'
                                   CHECK(status IN ('pending','done','overdue','no_data')),
                due_date       TEXT NOT NULL,
                created_at     TEXT NOT NULL
            );
            INSERT INTO followup_tasks_new SELECT * FROM followup_tasks;
            DROP TABLE followup_tasks;
            ALTER TABLE followup_tasks_new RENAME TO followup_tasks;
        """)
        conn.execute("PRAGMA foreign_keys=ON")
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
                "conditions": ["Type 2 Diabetes (diagnosed 2015)", "Hypertension"],
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
                    "risk_flags": ["hypertension", "obesity"],
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


def ensure_portal_demo():
    """
    Ensure Margaret Thompson exists with a portal-ready visit, tasks, and a
    fixed ``demo`` secure token so /p/demo shares the same DB path as live links.
    Safe to call on every app startup.
    """
    conn = get_conn()
    with conn:
        row = conn.execute(
            "SELECT id FROM patients WHERE name=?", (MARGARET_NAME,)
        ).fetchone()
        if row:
            margaret_id = row["id"]
        else:
            cur = conn.execute(
                """INSERT INTO patients(name, dob, sex, condition, risk_flags_json)
                   VALUES (?,?,?,?,?)""",
                (
                    MARGARET_NAME,
                    "1958-04-12",
                    "F",
                    "hypertension",
                    json.dumps(["hypertension"]),
                ),
            )
            margaret_id = cur.lastrowid

        visit_row = conn.execute(
            """SELECT id FROM visits
               WHERE patient_id=? AND visit_reason='Portal demo — hypertension follow-up'
               ORDER BY id DESC LIMIT 1""",
            (margaret_id,),
        ).fetchone()

        if not visit_row:
            demo_today = get_demo_date()
            last_visit = (demo_today - timedelta(days=28)).isoformat()
            next_visit = (demo_today + timedelta(days=28)).isoformat()

            conn.execute(
                """INSERT INTO visits(patient_id, visit_date, visit_reason,
                   chart_entry_text, patient_summary_text)
                   VALUES (?,?,?,?,?)""",
                (
                    margaret_id,
                    last_visit,
                    "Portal demo — hypertension follow-up",
                    (
                        "Margaret Thompson presents for hypertension follow-up. "
                        "BP 142/88 mmHg (elevated; target <130/80). "
                        "Amlodipine increased from 5 mg to 10 mg once daily. "
                        f"Plan: home BP monitoring, cardiology report review, next visit {next_visit}."
                    ),
                    (
                        "Hi Margaret,\n\nHere's a summary from today's visit:\n\n"
                        "✓ BP today was 142/88 — a little high; target below 130/80\n"
                        "✓ Amlodipine increased from 5 mg → 10 mg once daily\n"
                        "✓ Take every morning; don't stop without checking\n"
                        "✓ Should notice it working in 1–2 weeks; next visit "
                        + next_visit
                        + "\n\n"
                        "Your tasks before the next visit:\n"
                        "[ ] Measure your blood pressure each morning\n"
                        "[ ] Upload your cardiology report\n"
                        "[ ] Add your blood pressure readings\n"
                        "[ ] Notes from another doctor's visit\n\n"
                        "Your care team will review this with you at your next visit."
                    ),
                ),
            )
            visit_id = conn.execute(
                "SELECT id FROM visits WHERE patient_id=? ORDER BY id DESC LIMIT 1",
                (margaret_id,),
            ).fetchone()["id"]

            due = next_visit
            portal_tasks = [
                (
                    "Measure your blood pressure each morning",
                    "confirmation",
                    None,
                    "daily",
                ),
                (
                    "Upload your cardiology report",
                    "upload",
                    None,
                    "once",
                ),
                (
                    "Add your blood pressure readings",
                    "recurring_input",
                    "blood_pressure",
                    "daily",
                ),
                (
                    "Notes from another doctor's visit",
                    "confirmation",
                    None,
                    "once",
                ),
            ]
            for desc, task_type, metric, frequency in portal_tasks:
                conn.execute(
                    """INSERT INTO followup_tasks(patient_id, visit_id, description, type,
                       target_metric, status, due_date, created_at, frequency)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        margaret_id,
                        visit_id,
                        desc,
                        task_type,
                        metric,
                        "pending",
                        due,
                        last_visit,
                        frequency,
                    ),
                )

            snapshot = {
                "medical_history": {
                    "conditions": ["Hypertension (diagnosed 2018)"],
                },
                "medications": [
                    {"name": "Amlodipine", "dose": "10mg", "frequency": "once daily"},
                ],
            }
            conn.execute(
                """INSERT INTO chart_snapshots(patient_id, visit_id, snapshot_json, created_at)
                   VALUES (?,?,?,?)""",
                (margaret_id, visit_id, json.dumps(snapshot), last_visit),
            )
        else:
            visit_id = visit_row["id"]

        token_row = conn.execute(
            "SELECT id FROM secure_tokens WHERE token=?", (DEMO_TOKEN,)
        ).fetchone()
        today_iso = date.today().isoformat()
        if token_row:
            conn.execute(
                """UPDATE secure_tokens SET patient_id=?, visit_id=?, used_at=NULL
                   WHERE token=?""",
                (margaret_id, visit_id, DEMO_TOKEN),
            )
        else:
            conn.execute(
                """INSERT INTO secure_tokens(patient_id, visit_id, token, created_at)
                   VALUES (?,?,?,?)""",
                (margaret_id, visit_id, DEMO_TOKEN, today_iso),
            )

    conn.close()


def get_demo_patient_id() -> int | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT id FROM patients WHERE name=?", (MARGARET_NAME,)
    ).fetchone()
    conn.close()
    return row["id"] if row else None


def get_token_for_visit(visit_id: int) -> str | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT token FROM secure_tokens WHERE visit_id=? ORDER BY id DESC LIMIT 1",
        (visit_id,),
    ).fetchone()
    conn.close()
    return row["token"] if row else None


def get_portal_url(token: str, base_url: str) -> str:
    return f"{base_url.rstrip('/')}/p/{token}"


def get_patient_portal_token(patient_id: int) -> str:
    """Stable portal token per patient (Margaret uses ``demo``)."""
    demo_id = get_demo_patient_id()
    token = DEMO_TOKEN if patient_id == demo_id else f"pat_{patient_id}"
    conn = get_conn()
    row = conn.execute(
        "SELECT id FROM secure_tokens WHERE token=?", (token,)
    ).fetchone()
    if not row:
        with conn:
            conn.execute(
                """INSERT INTO secure_tokens(patient_id, visit_id, token, created_at)
                   VALUES (?,?,?,?)""",
                (patient_id, None, token, date.today().isoformat()),
            )
    conn.close()
    return token


def publish_visit_to_portal(patient_id: int, visit_id: int) -> str:
    """Point the patient's stable portal token at this visit."""
    token = get_patient_portal_token(patient_id)
    conn = get_conn()
    with conn:
        conn.execute(
            """UPDATE secure_tokens SET patient_id=?, visit_id=?, used_at=NULL
               WHERE token=?""",
            (patient_id, visit_id, token),
        )
    conn.close()
    return token


def sync_followup_tasks(patient_id: int, visit_id: int, tasks: list[dict]) -> list[int]:
    """
    Replace unpublished tasks for a visit with the doctor-approved list.
    Tasks the patient already completed (has responses) are kept.
    """
    conn = get_conn()
    with conn:
        stale = conn.execute(
            """SELECT ft.id FROM followup_tasks ft
               LEFT JOIN followup_responses fr ON fr.task_id = ft.id
               WHERE ft.visit_id=? AND fr.id IS NULL""",
            (visit_id,),
        ).fetchall()
        for row in stale:
            conn.execute("DELETE FROM followup_tasks WHERE id=?", (row["id"],))
    conn.close()
    if not tasks:
        return []
    return create_followup_tasks(patient_id, visit_id, tasks)


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


def get_task(task_id: int) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM followup_tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def _infer_task_frequency(task: dict) -> str:
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


def create_followup_tasks(patient_id: int, visit_id: int, tasks: list[dict]) -> list[int]:
    conn = get_conn()
    ids = []
    with conn:
        for t in tasks:
            cur = conn.execute(
                """INSERT INTO followup_tasks(patient_id, visit_id, description, type,
                   target_metric, status, due_date, created_at, frequency)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    patient_id,
                    visit_id,
                    t["description"],
                    t.get("type", "confirmation"),
                    t.get("target_metric"),
                    "pending",
                    t["due_date"],
                    date.today().isoformat(),
                    _infer_task_frequency(t),
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

    task = get_task(task_id)
    frequency = (task or {}).get("frequency") or "once"

    conn = get_conn()
    with conn:
        conn.execute(
            """INSERT INTO followup_responses(task_id, submitted_at, response_type, value, unit)
               VALUES (?,?,?,?,?)""",
            (task_id, datetime.now().isoformat(), response_type, value, unit),
        )
        if frequency == "once":
            conn.execute(
                "UPDATE followup_tasks SET status='done' WHERE id=?",
                (task_id,),
            )
        elif task and task.get("status") == "done":
            conn.execute(
                "UPDATE followup_tasks SET status='pending' WHERE id=?",
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
