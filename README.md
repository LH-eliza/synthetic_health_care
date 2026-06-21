## GP Copilot 

AI in Healthcare Hackathon — GP Copilot consolidates overdue test results, screening reminders, medication titration checks, and auto-extracted follow-up tasks into one per-patient view for GPs, with a correlated patient pre-visit portal.

Built for the June 20 2026 AI in Healthcare Co-Design Event (uOttawa DFM / TOH DFP / Bruyère).

## Stack
- Python + Flask (doctor app + patient portal)
- React SPA (patient pre-visit portal — data-driven, no hardcoded patient content)
- Claude / Gemini API (note extraction, structured task pulling)
- Synthetic data only

## Run locally

**Doctor app** (port 5100):
```bash
python3 app.py
```

**Patient portal** (port 5101):
```bash
python3 patient_portal.py
```

- Demo patient (Margaret Thompson spec): http://localhost:5101/p/demo
- Live portal links are generated from Flow B → “Send secure link” (e.g. `http://localhost:5101/p/<token>`)

**Rebuild patient portal** (after editing React source in `patient-portal/`):
```bash
cd patient-portal && npm install && npm run build
```

## Data architecture

Patient portal UI reads JSON schemas only — swap data without touching React:

| Schema | Source |
|--------|--------|
| Patient & visit metadata | `portal_schema.py` ← SQLite via secure token |
| Pre-visit tasks | DB `followup_tasks` mapped to checkbox / file_upload / bp_log / notes_textarea |
| Tips | `patient_portal_tips.json` |
| Clinic / doctor defaults | `portal_config.json` |

## Patient ↔ Doctor integration

**Margaret Thompson** is the portal demo patient (auto-created on startup). She appears on the doctor home screen with a **Portal Demo** badge.

| Step | Doctor app (5100) | Patient portal (5101) |
|------|-------------------|------------------------|
| 1 | Open **Margaret Thompson** → Flow B | — |
| 2 | Sidebar shows prior tasks + **Open Patient Portal** link | — |
| 3 | — | Open http://localhost:5101/p/demo |
| 4 | — | Complete tasks (saved to DB) |
| 5 | Refresh Margaret's Flow B → task dots update to **done** | — |
| 6 | Start visit → generate note → approve tasks → **Send to Patient** | Portal updates instantly (no secure link sent) |

Live visits follow the same path: AI suggests tasks → doctor approves/edits → **Send to Patient** pushes only approved tasks to the portal. Each patient has a stable portal URL (Margaret: `/p/demo`, others: `/p/pat_<id>`).

Both apps share `gp_copilot.db` — portal task completions appear on the doctor side immediately.

AI drafts, never sends. Screening/results/titration logic is deterministic (hardcoded rules), not LLM-judged.
