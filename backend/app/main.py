"""FastAPI app: CORS, router registration, DB init, default project, poller.

This file is owned by Phase 0 / integration (it is the glue). Phase-1 agents do
NOT edit it — they own their own routers/services, which are wired here.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
