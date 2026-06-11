"""API request/response models, directive shape, and SSE event names.

FROZEN CONTRACT. The frontend `types.ts` mirrors these. Wire JSON uses snake_case
(Pydantic defaults) — the frontend types use the same snake_case keys.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from .constants import DEFAULT_FOLD_MODEL


# ---------------------------------------------------------------- Projects
class ProjectCreate(BaseModel):
    name: str


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    created_at: datetime


# ---------------------------------------------------------------- Sequences
class SequenceCreate(BaseModel):
    project_id: int
    name: str
    residues: str
    kind: Literal["protein", "antigen", "partner"] = "protein"
    parent_id: int | None = None


class SequenceUpdate(BaseModel):
    name: str | None = None
    residues: str | None = None
    kind: Literal["protein", "antigen", "partner"] | None = None


class SequenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    name: str
    residues: str
    length: int
    kind: str
    parent_id: int | None = None
    created_at: datetime


# ---------------------------------------------------------------- Folding
class FoldSubmitRequest(BaseModel):
    project_id: int
    # Provide either explicit chains OR a sequence_id (resolved server-side).
    protein_sequences: list[str] = []
    sequence_id: int | None = None
    partner_sequence_id: int | None = None  # appended as an extra chain
    ligand_smiles: list[str] = []
    affinity_ligand_index: int | None = None
    model: str = DEFAULT_FOLD_MODEL
    name: str = "fold"


class BatchFoldItem(BaseModel):
    label: str
    protein_sequences: list[str]
    ligand_smiles: list[str] = []
    affinity_ligand_index: int | None = None


class BatchFoldRequest(BaseModel):
    project_id: int
    batch_run_id: int | None = None
    name: str = "batch"
    items: list[BatchFoldItem]
    model: str = DEFAULT_FOLD_MODEL
    partner_sequence_id: int | None = None


class JobRef(BaseModel):
    """Returned immediately on submit; also the payload of the SSE `job` event."""
    job_id: int
    provider_job_id: str
    state: str
    label: str = ""


class BatchSubmitResponse(BaseModel):
    batch_run_id: int
    jobs: list[JobRef]


class FoldJobOut(BaseModel):
    id: int
    project_id: int
    batch_run_id: int | None = None
    sequence_id: int | None = None
    label: str
    provider: str
    provider_job_id: str
    model: str
    state: str
    raw_status: str | None = None
    scores: dict[str, Any] | None = None
    per_model: list[Any] | None = None
    structure_format: str | None = None
    has_structure: bool = False
    error: str | None = None
    rank_hint: float | None = None
    submitted_at: datetime
    updated_at: datetime


class BatchRunOut(BaseModel):
    id: int
    project_id: int
    name: str
    base_sequence_id: int | None = None
    partner_sequence_id: int | None = None
    strategy: str
    status: str
    counts: dict[str, int] = {}
    created_at: datetime


# ---------------------------------------------------------------- Variants
class VariantGenerateRequest(BaseModel):
    base_sequence_id: int
    strategy: Literal["positions_subs", "alanine_scan", "claude", "pasted"]
    params: dict[str, Any] = {}


class VariantOut(BaseModel):
    label: str
    residues: str
    mutations: list[str] = []  # e.g. ["K45A", "S31Y"]


class VariantGenerateResponse(BaseModel):
    base_sequence_id: int
    variants: list[VariantOut]


# ---------------------------------------------------------------- Directives
class DirectiveTarget(BaseModel):
    """Selector for a chain / residue / set / inclusive range."""
    chain: str | None = None
    residue: int | None = None
    residues: list[int] | None = None
    residue_range: list[int] | None = None  # [start, end] inclusive


class Directive(BaseModel):
    kind: Literal["color", "label", "representation", "focus", "select"]
    target: DirectiveTarget
    color: str | None = None  # hex, for kind="color"
    text: str | None = None   # for kind="label"
    repr: str | None = None   # for kind="representation"


# ---------------------------------------------------------------- Chat (SSE)
class ChatRequest(BaseModel):
    project_id: int
    message: str
    # Optional viewer context, e.g. {"job_id": 3, "selection": {"chain": "A", "residue": 45}}
    context: dict[str, Any] | None = None


class SSEEvent(str, Enum):
    """Event names emitted by POST /api/chat (text/event-stream)."""
    text = "text"            # {"delta": "..."}
    directive = "directive"  # <Directive>
    tool_result = "tool_result"  # {"tool": "...", "status": "ok", ...}
    job = "job"              # <JobRef>
    done = "done"            # {"stop_reason": "end_turn"}
    error = "error"          # {"message": "..."}
