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

## Deploy (single service on Render)

The repo ships a multi-stage `Dockerfile` (builds the SPA, then FastAPI serves it + `/api`
+ the poller — same origin, no CORS) and a `render.yaml` Blueprint.

1. Render dashboard → **New → Blueprint** → pick this repo → Render reads `render.yaml`.
2. Set the three secret env vars when prompted:
   - `ANTHROPIC_API_KEY` — chat assistant
   - `ROWAN_API_KEY` — live folding (`FOLDING_PROVIDER` is preset to `rowan`)
   - `GATE_PASSWORD` — turns on the HTTP Basic gate (username `foldlab`); visitors are
     prompted once. Leave it unset to make the URL fully open.
3. Deploy. Health check is `/api/health` (gate-exempt); `MAX_CREDITS=50` caps Rowan spend per fold.

Run the same image locally:
```bash
docker build -t foldlab .
docker run -p 8000:8000 -e GATE_PASSWORD=secret -e ANTHROPIC_API_KEY=… -e ROWAN_API_KEY=… foldlab
# open http://127.0.0.1:8000  (login: foldlab / secret)
```

> Render's free tier has an **ephemeral** filesystem (the SQLite DB + saved structures reset on
> restart/redeploy — fine for a demo) and spins down after inactivity. For persistence, add a
> Render disk or point `DB_URL`/`STRUCTURE_DIR` at durable storage.
