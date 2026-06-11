"""Deterministic, zero-cost folding provider for development and demos.

COMPLETE — Agent A should NOT rewrite this; it is the offline path that makes the
whole app demoable without Rowan credits. Simulates ~3s of in-flight time, then
returns a bundled PDB fixture (monomer vs complex by chain count) and scores
seeded by a hash of the inputs (so variants rank deterministically).
"""
from __future__ import annotations

import hashlib
import threading
import time
from pathlib import Path

from ..constants import JobState
from .base import FoldingProvider, FoldRequest, FoldResult, FoldStatus, PerModelExtras

_FIXTURES = Path(__file__).resolve().parent.parent / "data" / "fixtures"
_MOCK_DELAY_SECONDS = 3.0


def _seed(parts: list[str]) -> int:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _unit(seed: int, salt: int) -> float:
    """Deterministic pseudo-random float in [0, 1) from (seed, salt)."""
    return ((seed ^ (salt * 2654435761)) % 1000) / 1000.0


class MockProvider(FoldingProvider):
    name = "mock"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, dict] = {}
        self._counter = 0

    def submit(self, req: FoldRequest) -> FoldStatus:
        with self._lock:
            self._counter += 1
            job_id = f"mock-{self._counter:06d}"
            self._jobs[job_id] = {"req": req, "t0": time.monotonic()}
        return FoldStatus(provider_job_id=job_id, state=JobState.QUEUED, raw_status="QUEUED")

    def batch_submit(self, reqs: list[FoldRequest]) -> list[FoldStatus]:
        return [self.submit(r) for r in reqs]

    def status(self, provider_job_id: str) -> FoldStatus:
        with self._lock:
            job = self._jobs.get(provider_job_id)
        if job is None:
            # Unknown (e.g. after a restart): report completed so the demo resolves.
            return FoldStatus(provider_job_id, JobState.COMPLETED, "COMPLETED_OK")
        elapsed = time.monotonic() - job["t0"]
        if elapsed < _MOCK_DELAY_SECONDS:
            return FoldStatus(provider_job_id, JobState.RUNNING, "RUNNING")
        return FoldStatus(provider_job_id, JobState.COMPLETED, "COMPLETED_OK")

    def fetch_result(self, provider_job_id: str) -> FoldResult:
        with self._lock:
            job = self._jobs.get(provider_job_id)
        req: FoldRequest = job["req"] if job else FoldRequest(protein_sequences=["A"])

        n_chains = max(1, len(req.protein_sequences))
        fixture = _FIXTURES / ("complex.pdb" if n_chains > 1 else "monomer.pdb")
        data = fixture.read_bytes()

        seed = _seed(list(req.protein_sequences) + list(req.ligand_smiles))
        ptm = round(0.60 + 0.39 * _unit(seed, 1), 3)
        iptm = round(0.50 + 0.45 * _unit(seed, 2), 3) if n_chains > 1 else None
        avg_lddt = round(60.0 + 39.0 * _unit(seed, 3), 1)
        confidence = round(0.50 + 0.49 * _unit(seed, 4), 3)

        extras = PerModelExtras(
            ptm=ptm, iptm=iptm, avg_lddt=avg_lddt, confidence=confidence, posebusters_valid=True
        )
        scores: dict = {"ptm": ptm, "iptm": iptm, "avg_lddt": avg_lddt, "confidence": confidence}

        if req.ligand_smiles or req.affinity_ligand_index is not None:
            affinity = round(2.0 + 6.0 * _unit(seed, 5), 2)  # ~pIC50
            probability = round(_unit(seed, 6), 3)
            extras.affinity_pred_value = affinity
            extras.affinity_probability = probability
            scores["affinity_pred_value"] = affinity
            scores["affinity_probability"] = probability

        return FoldResult(
            provider_job_id=provider_job_id,
            structure_bytes=data,
            structure_format="pdb",
            scores=scores,
            per_model=[extras],
            messages=["mock provider result"],
        )
