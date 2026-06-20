#!/usr/bin/env bash
# One-time setup for GP Copilot (doctor app + patient portal)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> GP Copilot setup"
echo "    Project: $ROOT"
echo

# Python dependencies
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found. Install Python 3.10+ first."
  exit 1
fi

echo "==> Installing Python packages..."
python3 -m pip install -r requirements.txt

# Environment file
if [[ ! -f .env ]]; then
  echo "==> Creating .env from .env.example"
  cp .env.example .env
  echo "    Edit .env and add your LLM API key before using note generation."
else
  echo "==> .env already exists (skipping)"
fi

# Patient portal React bundle
if ! command -v npm >/dev/null 2>&1; then
  echo "WARN: npm not found. Install Node.js 18+ to build the patient portal UI."
  echo "      You can still run the doctor app; portal UI may be missing until built."
else
  echo "==> Building patient portal (React)..."
  cd patient-portal
  npm install
  npm run build
  cd "$ROOT"
fi

# Initialize database + demo patient
echo "==> Initializing database and demo patient (Margaret Thompson)..."
python3 - <<'PY'
import db
db.init_db()
db.seed()
db.ensure_portal_demo()
print("    Database ready:", db.DB_PATH)
print("    Demo patient id:", db.get_demo_patient_id())
PY

echo
echo "Setup complete. Next step:"
echo "  ./scripts/start.sh"
echo
echo "Then open:"
echo "  Doctor app:      http://localhost:5100"
echo "  Patient portal:  http://localhost:5101/p/demo"
