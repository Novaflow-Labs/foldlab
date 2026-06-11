"""SQLModel tables (FROZEN CONTRACT — Phase-1 agents import, never edit).

JSON-typed columns hold provider-shaped blobs (inputs, scores, per-model extras,
directive payloads). Structure files live on disk; only their path is stored.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from .constants import DEFAULT_FOLD_MODEL, JobState


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Project(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    created_at: datetime = Field(default_factory=_utcnow)


class Sequence(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    name: str
    residues: str
    kind: str = "protein"  # protein | antigen | partner
    parent_id: int | None = Field(default=None, foreign_key="sequence.id")
    created_at: datetime = Field(default_factory=_utcnow)


class BatchRun(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    name: str
    base_sequence_id: int | None = Field(default=None, foreign_key="sequence.id")
    partner_sequence_id: int | None = Field(default=None, foreign_key="sequence.id")
    strategy: str = "pasted"
    params_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = "pending"  # pending | running | done | partial
    created_at: datetime = Field(default_factory=_utcnow)


class FoldJob(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    batch_run_id: int | None = Field(
        default=None, foreign_key="batchrun.id", index=True
    )
    sequence_id: int | None = Field(default=None, foreign_key="sequence.id")
    label: str = ""
    provider: str = "mock"
    provider_job_id: str = Field(index=True)
    model: str = DEFAULT_FOLD_MODEL
    inputs_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    state: str = Field(default=JobState.QUEUED.value, index=True)
    raw_status: str | None = None
    scores_json: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON)
    )
    per_model_json: list[Any] | None = Field(
        default=None, sa_column=Column(JSON)
    )
    structure_path: str | None = None
    structure_format: str | None = None  # "pdb" | "mmcif"
    error: str | None = None
    submitted_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class Directive(SQLModel, table=True):
    """A persisted viewer directive (color/label/representation/focus/select)."""

    id: int | None = Field(default=None, primary_key=True)
    project_id: int | None = Field(
        default=None, foreign_key="project.id", index=True
    )
    job_id: int | None = Field(default=None, foreign_key="foldjob.id", index=True)
    kind: str
    payload_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    source: str = "chat"  # chat | ui
    created_at: datetime = Field(default_factory=_utcnow)
