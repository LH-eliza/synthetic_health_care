#!/usr/bin/env bash
# Start doctor app (5100) and patient portal (5101)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DOCTOR_PORT=5100
PORTAL_PORT=5101

kill_port() {
  local port=$1
  if lsof -ti:"$port" >/dev/null 2>&1; then
    echo "    Stopping existing process on port $port..."
    kill $(lsof -t -i:"$port") 2>/dev/null || true
    sleep 0.5
  fi
}

echo "==> GP Copilot — starting both apps"
echo

# Ensure DB + Margaret demo patient exist
python3 - <<'PY'
import db
db.init_db()
db.seed()
db.ensure_portal_demo()
PY

kill_port "$DOCTOR_PORT"
kill_port "$PORTAL_PORT"

if [[ ! -f static/patient-portal/assets/index.js ]]; then
  echo "WARN: Patient portal UI not built. Run ./scripts/setup.sh first."
fi

echo "==> Doctor app       → http://localhost:$DOCTOR_PORT"
python3 app.py &
DOCTOR_PID=$!

echo "==> Patient portal   → http://localhost:$PORTAL_PORT/p/demo"
python3 patient_portal.py &
PORTAL_PID=$!

cleanup() {
  echo
  echo "==> Shutting down..."
  kill "$DOCTOR_PID" "$PORTAL_PID" 2>/dev/null || true
  exit 0
}
trap cleanup INT TERM

echo
echo "Both servers running. Press Ctrl+C to stop."
echo
echo "  Doctor home:     http://localhost:$DOCTOR_PORT"
echo "  Portal demo:     http://localhost:$PORTAL_PORT/p/demo"
echo "  Margaret (demo): http://localhost:$DOCTOR_PORT/patient/$(python3 -c 'import db; db.ensure_portal_demo(); print(db.get_demo_patient_id())')"
echo

wait
