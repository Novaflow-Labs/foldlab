"""FastAPI app: CORS, router registration, DB init, default project, poller.

This file is owned by Phase 0 / integration (it is the glue). Phase-1 agents do
NOT edit it — they own their own routers/services, which are wired here.
"""
from __future__ import annotations

import base64
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select

from .api import chat, folding, projects, sequences, variants
from .config import get_settings
from .db import engine, init_db
from .models import Project
from .services.poller import Poller

settings = get_settings()
poller = Poller()


def _ensure_default_project() -> None:
    with Session(engine) as session:
        if session.exec(select(Project)).first() is None:
            session.add(Project(name="Demo"))
            session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _ensure_default_project()
    await poller.start()
    try:
        yield
    finally:
        await poller.stop()


app = FastAPI(title="Protein Visualization & Folding API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (projects, sequences, folding, variants, chat):
    app.include_router(module.router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "provider": settings.folding_provider}


@app.middleware("http")
async def _access_gate(request: Request, call_next):
    """Optional HTTP Basic gate for public deploys. Off unless gate_password is
    set; /api/health stays open for platform health checks."""
    password = settings.gate_password
    if password and request.url.path != "/api/health":
        ok = False
        header = request.headers.get("authorization", "")
        if header.startswith("Basic "):
            try:
                user, _, supplied = (
                    base64.b64decode(header[6:]).decode("utf-8").partition(":")
                )
                ok = secrets.compare_digest(user, settings.gate_user) and (
                    secrets.compare_digest(supplied, password)
                )
            except Exception:  # noqa: BLE001
                ok = False
        if not ok:
            return Response(
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="FOLDLAB"'},
            )
    return await call_next(request)


# Serve the built SPA (production single-service deploy). Mounted last so the
# /api routes take precedence; skipped in local dev (frontend_dist empty).
if settings.frontend_dist and Path(settings.frontend_dist).is_dir():
    app.mount(
        "/", StaticFiles(directory=settings.frontend_dist, html=True), name="spa"
    )
