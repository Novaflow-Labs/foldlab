# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A natural-language–driven protein workspace: load/edit/save sequences, run folding & co-folding
(via Rowan Scientific), interact with the 3D structure (Mol*), and batch-fold variants for
antibody optimization — all driven by an Anthropic chat assistant. The backend holds both API
keys server-side; **keys never reach the browser**. Folding is async (submit → poll → retrieve).
The default `MockProvider` runs the entire app with **zero API spend** and no keys.

## Commands

All backend commands must use the **venv's** Python directly (a bare `uvicorn`/`pytest` uses the
global Python, which lacks the deps → `ModuleNotFoundError: sqlmodel`). On Windows the venv Python
is `backend/.venv/Scripts/python.exe`; on macOS/Linux it is `backend/.venv/bin/python`.

```bash
# First-time setup
cd backend && python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt -r requirements-dev.txt   # Win Git-Bash
cd ../frontend && npm install

# Run both (from repo root)
bash scripts/dev.sh                                        # macOS/Linux/Git-Bash (Ctrl-C stops both)
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1   # Windows PowerShell

# Backend only — http://127.0.0.1:8000
cd backend && .venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
# Frontend only — http://localhost:5173 (Vite proxies /api -> 127.0.0.1:8000, so no CORS in dev)
cd frontend && npm run dev
```

```bash
# Backend tests (run from backend/; asyncio_mode=auto, so async tests need no decorator)
cd backend && .venv/Scripts/python.exe -m pytest
.venv/Scripts/python.exe -m pytest tests/test_nl.py                       # one file
.venv/Scripts/python.exe -m pytest tests/test_nl.py::test_chat_loop -q    # one test

# Backend lint (config in pyproject.toml; line-length 100, E501 ignored)
cd backend && .venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format .

# Frontend
cd frontend && npm run typecheck     # tsc --noEmit
npm run build                        # tsc --noEmit && vite build
```

There is no separate frontend lint/test runner — `typecheck` (and the `tsc` step inside `build`)
is the gate.

## Architecture

Two services that ship as **one Docker image** in production: the multi-stage `Dockerfile` builds
the Vite SPA, then FastAPI serves it as static files (mounted at `/` in `main.py`, only when
`FRONTEND_DIST` points at a real dir) alongside `/api` and the background poller — same origin, no
CORS. Local dev runs them separately and relies on the Vite proxy.

### The folding lifecycle (submit → poll → retrieve)

Folding is **never synchronous**. A submit returns a job id immediately; a background poller
reconciles state until the structure is ready.

1. `services/jobs.py::submit_fold` / `submit_batch` resolve chains, call the provider's `submit`,
   and persist a `FoldJob` row in `state=queued`. `_resolve_chains` is where complex/co-fold/
   homo-oligomer shapes are built: >1 protein chain = complex; `copies=N` replicates one chain into
   an N-mer; a `partner_sequence_id` is appended as an extra chain; `ligand_smiles` triggers co-folding.
2. `services/poller.py::Poller` runs a loop (interval `POLL_INTERVAL_SECONDS`, default 5s) started in
   `main.py`'s lifespan. Each pass, `reconcile` asks the provider for `status` on every
   queued/running job; on terminal completion it `fetch_result`s, writes the structure file to disk
   (`services/structures.py`), and stores scores. It is **idempotent and per-job fault-isolated** —
   one bad job never aborts the pass — so it survives restarts.
3. The frontend polls `GET /api/jobs` (React Query) and loads `GET /api/jobs/{id}/structure` (raw
   bytes + `X-Structure-Format` header) into Mol* only once a job is `completed` with a structure.

Structure files live on disk (`STRUCTURE_DIR`); only the path is stored in the DB. The SQLite DB
and structure dir are both gitignored and **ephemeral on Render's free tier** (reset on redeploy).

### The folding provider seam (the core swappable abstraction)

`providers/base.py::FoldingProvider` (ABC) decouples the app from any folding backend via
normalized dataclasses (`FoldRequest`/`FoldStatus`/`FoldResult`/`PerModelExtras`). Two impls:
`MockProvider` (default, deterministic, zero-cost) and `RowanProvider` (wraps `rowan-python`).
`providers/factory.py::get_provider()` returns a cached singleton chosen by `FOLDING_PROVIDER`;
the Rowan import is **lazy** so the app boots with the mock even if Rowan deps/keys are absent.
To add a backend, implement these four methods — nothing else needs to change. All provider
methods are synchronous (network I/O) and must be safe to call from a worker thread; async callers
wrap them in `anyio.to_thread.run_sync`.

### The NL chat loop (Anthropic tool-use → SSE)

`POST /api/chat` returns `text/event-stream`. `nl/loop.py::run_chat` is an async generator yielding
SSE events. Key mechanics:

- **Two tool classes** (`nl/tools.py`): **backend-action tools** (`submit_fold`, `edit_sequence`,
  `generate_variants`, `list_jobs`, …) execute server-side via `nl/handlers.py::dispatch_tool` and
  return real `tool_result` data; **UI-directive tools** (`color_selection`, `add_label`,
  `set_representation`, `focus_camera`, `select_region`) are "executed" by recording a `Directive`
  row and emitting a `directive` SSE event — `directive_from_tool` is the canonical tool→Directive
  conversion. The model never returns `{applied:true}` for a directive by itself; the loop fabricates it.
- **Threading model**: the Anthropic SDK's `messages.stream(...)` is a *synchronous, blocking*
  context manager. To keep deltas flowing without blocking the event loop, the whole streaming +
  tool loop runs in a worker thread (`anyio.to_thread.run_sync`) and pushes events through an anyio
  memory object stream that the async generator drains. Tool dispatch is async and is bounced back
  onto the event loop with `anyio.from_thread.run`. Don't "simplify" this to a plain async call —
  it would block the server.
- **No-id-asking contract**: `_build_initial_messages` prepends a `<system-reminder>` with a compact
  project summary (saved sequences + recent jobs) and any viewer context (e.g. the picked residue),
  so the assistant resolves "this"/"the selected residue" and never asks the user for a project or
  sequence id. The `SYSTEM` prompt is a single cached block (static, no timestamps → cache stays warm).
- The loop is capped at `MAX_ITERATIONS=8`; it never raises out of the generator — failures become
  `error` + `done` events.

The frontend SSE consumer is `frontend/src/api/client.ts::streamChat` (a POST-based reader, since
native `EventSource` is GET-only). **It splits events on `/\r?\n\r?\n/`** — sse-starlette emits
CRLF, and a plain `\n\n` split would deliver zero events. Directive events flow into
`useJobsStore.directives`; `MolstarViewer` applies only the newly-appended directives incrementally
(tracked by `appliedCountRef`) and reloads the structure only when it changes or the directive list
shrinks.

### Frontend shape

React + Vite + TS SPA, 3-pane workspace (`App.tsx`): left = sequence editor / fold controls /
variant panel (tabbed); center = Mol* viewer (`viewer/`) + results gallery; right = chat panel.
State is Zustand (`state/useJobsStore.ts` for project/selected-job/directives/pick-context,
`useChatStore.ts` for chat) plus React Query for server data. All HTTP goes through the helpers in
`api/client.ts` — don't hand-roll `fetch` elsewhere.

## Conventions that matter

- **"FROZEN CONTRACT" files.** This codebase was built by parallel agents against shared contracts;
  files whose docstrings say *FROZEN CONTRACT* — `models.py`, `constants.py`, `schemas.py`,
  `providers/base.py`, `nl/tools.py`, the frozen service signatures in `services/jobs.py`, and on the
  frontend `api/client.ts`, `types.ts`, `MolstarViewer`'s prop interface — define the seam between
  layers. Treat their shapes/signatures as an API: changing one means updating every caller on both
  sides. `frontend/src/types.ts` mirrors `backend/app/schemas.py`.
- **Wire format is snake_case** end to end (Pydantic defaults); the frontend types use the same
  snake_case keys, so no case translation happens at the boundary.
- **Normalized job states** (`constants.py::JobState`: queued/running/completed/failed/stopped) are
  provider-agnostic; `ROWAN_STATUS_MAP` maps Rowan's enum names in, and anything unmapped is treated
  as still-running. The canonical UI model list is `FOLD_MODELS` (`boltz_2` default).
- **Secrets/config** live in `backend/.env` (copy from `.env.example`), read only via
  `config.py::get_settings()` (cached). `ANTHROPIC_API_KEY` enables chat; `ROWAN_API_KEY` +
  `FOLDING_PROVIDER=rowan` enables real folding; an empty key string is treated as "missing".
- **Optional HTTP Basic gate** for public deploys: set `GATE_PASSWORD` to turn on the gate in
  `main.py`'s middleware (`/api/health` stays exempt for platform health checks). `MAX_CREDITS`
  caps Rowan spend per job.
