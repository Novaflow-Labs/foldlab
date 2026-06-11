"""FoldingProvider abstraction (FROZEN CONTRACT — the core swappable seam).

Normalized dataclasses decouple the app from any specific folding backend.
RowanProvider and MockProvider implement this; a future provider only needs to
satisfy these signatures and return a (format-agnostic) FoldResult.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ..constants import DEFAULT_FOLD_MODEL, JobState


@dataclass
class FoldRequest:
    """One folding job. >1 protein chain = complex; SMILES present = co-folding."""
    protein_sequences: list[str]
    ligand_smiles: list[str] = field(default_factory=list)
    affinity_ligand_index: int | None = None
    model: str = DEFAULT_FOLD_MODEL
    name: str = "fold"
    use_msa_server: bool = True
    num_samples: int | None = None
    max_credits: int | None = None
    do_pose_refinement: bool = False


@dataclass
class FoldStatus:
    provider_job_id: str
    state: JobState
    raw_status: str | None = None


@dataclass
class PerModelExtras:
    """Per-returned-sample metrics (model-specific; affinity is Boltz-2 only)."""
    ptm: float | None = None
    iptm: float | None = None
    avg_lddt: float | None = None
    confidence: float | None = None
    affinity_pred_value: float | None = None   # ~pIC50 (Boltz-2)
    affinity_probability: float | None = None  # binder probability (Boltz-2)
    strain: float | None = None
    posebusters_valid: bool | None = None


@dataclass
class FoldResult:
    provider_job_id: str
    structure_bytes: bytes
    structure_format: str  # "pdb" | "mmcif"
    scores: dict[str, Any] = field(default_factory=dict)
    per_model: list[PerModelExtras] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)


class FoldingProvider(ABC):
    """Submit/poll/retrieve. Implementations must be safe to call from a thread."""

    name: str = "base"

    @abstractmethod
    def submit(self, req: FoldRequest) -> FoldStatus:
        ...

    @abstractmethod
    def batch_submit(self, reqs: list[FoldRequest]) -> list[FoldStatus]:
        ...

    @abstractmethod
    def status(self, provider_job_id: str) -> FoldStatus:
        ...

    @abstractmethod
    def fetch_result(self, provider_job_id: str) -> FoldResult:
        ...
