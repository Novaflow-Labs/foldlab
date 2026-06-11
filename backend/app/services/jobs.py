"""Folding job orchestration: submit, batch, query, and DB<->API mapping.

FROZEN SIGNATURES — Agent A (Phase 1A) implements the bodies; do NOT change the
signatures (api/folding.py and nl/handlers.py call these).

Threading: `submit_fold`/`submit_batch` invoke the provider (sync, network I/O).
Async callers (the chat loop) must wrap them in `anyio.to_thread.run_sync`.
Sync FastAPI route handlers may call them directly (FastAPI runs `def` routes
in a worker thread).
"""
from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from ..config import get_settings
from ..constants import TERMINAL_STATES
from ..models import BatchRun, FoldJob, Sequence
from ..providers.base import FoldRequest
from ..providers.factory import get_provider
from ..schemas import (
    BatchFoldRequest,
    BatchRunOut,
    FoldJobOut,
    FoldSubmitRequest,
)


def _resolve_chains(
    session: Session,
    *,
    protein_sequences: list[str],
    sequence_id: int | None,
    partner_sequence_id: int | None,
) -> list[str]:
    """Resolve the protein chains for a job.

    Explicit `protein_sequences` win; otherwise read residues straight from the
    DB by id (kept decoupled from services.sequences). A partner sequence is
    appended as an extra chain.
    """
    chains: list[str] = list(protein_sequences or [])
    if not chains and sequence_id is not None:
        seq = session.get(Sequence, sequence_id)
        if seq is not None:
            chains = [seq.residues]
    if partner_sequence_id is not None:
        partner = session.get(Sequence, partner_sequence_id)
        if partner is not None:
            chains.append(partner.residues)
    return chains


def submit_fold(session: Session, req: FoldSubmitRequest) -> FoldJob:
    """Resolve sequences, build a FoldRequest, call provider.submit, persist a
    queued FoldJob, and return it. Does NOT wait for the result."""
    chains = _resolve_chains(
        session,
        protein_sequences=req.protein_sequences,
        sequence_id=req.sequence_id,
        partner_sequence_id=req.partner_sequence_id,
    )
    freq = FoldRequest(
        protein_sequences=chains,
        ligand_smiles=list(req.ligand_smiles or []),
        affinity_ligand_index=req.affinity_ligand_index,
        model=req.model,
        name=req.name,
        max_credits=get_settings().max_credits,
    )
    provider = get_provider()
    st = provider.submit(freq)

    job = FoldJob(
        project_id=req.project_id,
        sequence_id=req.sequence_id,
        label="",
        provider=provider.name,
        provider_job_id=st.provider_job_id,
        model=req.model,
        inputs_json=req.model_dump(),
        state=st.state.value,
        raw_status=st.raw_status,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def submit_batch(
    session: Session,
    req: BatchFoldRequest,
    *,
    base_sequence_id: int | None = None,
    strategy: str = "pasted",
    params: dict[str, Any] | None = None,
) -> tuple[BatchRun, list[FoldJob]]:
    """Create a BatchRun (recording provenance) and submit every item via
    provider.batch_submit, persisting one queued FoldJob per item."""
    batch = BatchRun(
        project_id=req.project_id,
        name=req.name,
        base_sequence_id=base_sequence_id,
        partner_sequence_id=req.partner_sequence_id,
        strategy=strategy,
        params_json=params or {},
        status="running",
    )
    session.add(batch)
    session.commit()
    session.refresh(batch)

    partner_residues: str | None = None
    if req.partner_sequence_id is not None:
        partner = session.get(Sequence, req.partner_sequence_id)
        if partner is not None:
            partner_residues = partner.residues

    max_credits = get_settings().max_credits
    freqs: list[FoldRequest] = []
    for item in req.items:
        chains = list(item.protein_sequences)
        if partner_residues is not None:
            chains.append(partner_residues)
        freqs.append(
            FoldRequest(
                protein_sequences=chains,
                ligand_smiles=list(item.ligand_smiles or []),
                affinity_ligand_index=item.affinity_ligand_index,
                model=req.model,
                name=item.label or req.name,
                max_credits=max_credits,
            )
        )

    provider = get_provider()
    statuses = provider.batch_submit(freqs)

    jobs: list[FoldJob] = []
    for item, st in zip(req.items, statuses, strict=True):
        job = FoldJob(
            project_id=req.project_id,
            batch_run_id=batch.id,
            sequence_id=base_sequence_id,
            label=item.label,
            provider=provider.name,
            provider_job_id=st.provider_job_id,
            model=req.model,
            inputs_json=item.model_dump(),
            state=st.state.value,
            raw_status=st.raw_status,
        )
        session.add(job)
        jobs.append(job)
    session.commit()
    for job in jobs:
        session.refresh(job)
    return batch, jobs


def list_jobs(
    session: Session, project_id: int, batch_run_id: int | None = None
) -> list[FoldJob]:
    stmt = select(FoldJob).where(FoldJob.project_id == project_id)
    if batch_run_id is not None:
        stmt = stmt.where(FoldJob.batch_run_id == batch_run_id)
    stmt = stmt.order_by(FoldJob.id)
    return list(session.exec(stmt).all())


def get_job(session: Session, job_id: int) -> FoldJob | None:
    return session.get(FoldJob, job_id)


def list_batches(session: Session, project_id: int) -> list[BatchRunOut]:
    batches = session.exec(
        select(BatchRun)
        .where(BatchRun.project_id == project_id)
        .order_by(BatchRun.id)
    ).all()
    out: list[BatchRunOut] = []
    for batch in batches:
        jobs = session.exec(
            select(FoldJob).where(FoldJob.batch_run_id == batch.id)
        ).all()
        counts: dict[str, int] = {}
        for job in jobs:
            counts[job.state] = counts.get(job.state, 0) + 1
        out.append(
            BatchRunOut(
                id=batch.id,
                project_id=batch.project_id,
                name=batch.name,
                base_sequence_id=batch.base_sequence_id,
                partner_sequence_id=batch.partner_sequence_id,
                strategy=batch.strategy,
                status=_rollup_status(jobs),
                counts=counts,
                created_at=batch.created_at,
            )
        )
    return out


def _rollup_status(jobs: list[FoldJob]) -> str:
    """Roll a batch's job states up to done | partial | running."""
    if not jobs:
        return "running"
    terminal_values = {s.value for s in TERMINAL_STATES}
    terminal = [j for j in jobs if j.state in terminal_values]
    if len(terminal) == len(jobs):
        return "done"
    if terminal:
        return "partial"
    return "running"


def to_job_out(job: FoldJob) -> FoldJobOut:
    """Map a FoldJob row to the API shape (scores from json, has_structure, rank_hint)."""
    return FoldJobOut(
        id=job.id,
        project_id=job.project_id,
        batch_run_id=job.batch_run_id,
        sequence_id=job.sequence_id,
        label=job.label,
        provider=job.provider,
        provider_job_id=job.provider_job_id,
        model=job.model,
        state=job.state,
        raw_status=job.raw_status,
        scores=job.scores_json,
        per_model=job.per_model_json,
        structure_format=job.structure_format,
        has_structure=bool(job.structure_path),
        error=job.error,
        rank_hint=compute_rank_hint(job.scores_json, job.per_model_json),
        submitted_at=job.submitted_at,
        updated_at=job.updated_at,
    )


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compute_rank_hint(
    scores: dict[str, Any] | None, per_model: list[Any] | None
) -> float | None:
    """Single sortable number for the gallery: affinity when present, else ipTM/pTM/confidence."""
    sources: list[dict[str, Any]] = []
    if isinstance(scores, dict):
        sources.append(scores)
    if per_model:
        first = per_model[0]
        if isinstance(first, dict):
            sources.append(first)

    for key in (
        "affinity_pred_value",
        "iptm",
        "ptm",
        "confidence",
    ):
        for source in sources:
            val = _coerce_float(source.get(key))
            if val is not None:
                return val
    return None
