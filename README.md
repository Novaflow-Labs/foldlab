# Protein Visualization & Folding Demo

Natural-language–driven protein workspace: load/edit/save sequences, run folding & co-folding
(Rowan Scientific), interact with the 3D structure (Mol\*), color/label parts, ask how to
optimize, and batch-fold variants for antibody optimization — driven by an Anthropic
chat assistant with explicit UI fallbacks.

## Architecture

- **frontend/** — React + Vite + TypeScript SPA (Mol\* viewer, sequence editor, chat).
- **backend/** — FastAPI (Python ≥3.12). Holds both API keys server-side, wraps Rowan via a
  modular `FoldingProvider`, runs the Anthropic tool-use loop, persists to SQLite + on-disk PDB.

API keys never reach the browser. Folding is async (submit → poll → retrieve). A `MockProvider`
(default) runs the whole app with **zero Rowan spend**.

## Run locally

Requires **Python ≥ 3.12** and **Node ≥ 18**. The default `MockProvider` runs the whole app
with **zero API spend** — no keys needed to see it working.

### First-time setup
```bash
# backend — create the venv and install into it (no activation needed)
cd backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt -r requirements-dev.txt   # Git-Bash
#   PowerShell:    .\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
#   macOS/Linux:   .venv/bin/python          -m pip install -r requirements.txt -r requirements-dev.txt
cd ../frontend && npm install
```

### Start both (one command, from the repo root)
```bash
bash scripts/dev.sh                                  # macOS/Linux/Git-Bash (Ctrl-C stops both)
```
```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1   # Windows PowerShell
```

### …or start manually (two terminals)
Call the **venv's** Python directly — a bare `uvicorn` uses your *global* Python, which lacks
the deps (`ModuleNotFoundError: sqlmodel`).
```bash
# terminal 1 — backend
cd backend && .venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
#   PowerShell:    .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
#   macOS/Linux:   .venv/bin/python          -m uvicorn app.main:app --reload --port 8000

# terminal 2 — frontend
cd frontend && npm run dev        # http://localhost:5173  (proxies /api -> 127.0.0.1:8000)
```

### Keys (optional)
Copy `.env.example` → `backend/.env` and fill in as needed:
- `ANTHROPIC_API_KEY` — enables the chat assistant.
- `ROWAN_API_KEY` + `FOLDING_PROVIDER=rowan` — enables **real** folding (leave `mock` for the zero-cost demo).
