# synthetic_health_care

AI in Healthcare Hackathon — Pending Items Worklist: consolidates overdue 
test results, screening reminders, medication titration checks, and 
auto-extracted follow-up tasks into one per-patient view for GPs.

Built for the June 20 2026 AI in Healthcare Co-Design Event (uOttawa DFM / TOH DFP / Bruyère).

## Stack
- Python + Streamlit
- Claude API (note extraction, structured task pulling)
- Synthetic data only (Synthea-derived patient records)

## Design principle
AI drafts, never sends. Screening/results/titration logic is deterministic 
(hardcoded rules), not LLM-judged — see pitch notes for why.