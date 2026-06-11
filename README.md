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

### Backend (Python ≥3.12)
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
copy ..\.env.example .env               # then edit keys (optional in mock mode)
uvicorn app.main:app --reload --port 8000
```

### Frontend
```powershell
cd frontend
npm install
npm run dev                              # http://localhost:5173 (proxies /api -> :8000)
```

Set `FOLDING_PROVIDER=rowan` in `backend/.env` (with `ROWAN_API_KEY`) to run real folding;
leave it `mock` for a zero-cost demo. The chat assistant needs `ANTHROPIC_API_KEY`.

See `docs`/the implementation plan for module ownership and contracts.
