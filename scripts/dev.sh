#!/usr/bin/env bash
# Start the backend (FastAPI) + frontend (Vite) together. Ctrl-C stops both.
# Works in macOS/Linux and Windows Git-Bash. Uses the venv's Python directly —
# no activation needed.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -x "$ROOT/backend/.venv/Scripts/python.exe" ]; then
  PY="$ROOT/backend/.venv/Scripts/python.exe"   # Windows Git-Bash
elif [ -x "$ROOT/backend/.venv/bin/python" ]; then
  PY="$ROOT/backend/.venv/bin/python"           # macOS/Linux
else
  echo "No backend venv found. First-time setup:"
  echo "  cd backend && python -m venv .venv"
  echo "  .venv/Scripts/python.exe -m pip install -r requirements.txt -r requirements-dev.txt   # (or .venv/bin/python on macOS/Linux)"
  exit 1
fi

echo "Backend  -> http://127.0.0.1:8000"
echo "Frontend -> http://localhost:5173"

( cd "$ROOT/backend" && "$PY" -m uvicorn app.main:app --reload --port 8000 ) &
BACK=$!
trap 'kill "$BACK" 2>/dev/null || true' EXIT INT TERM

( cd "$ROOT/frontend" && npm run dev )
