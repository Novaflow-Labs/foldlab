"""Background poller that reconciles in-flight folding jobs with the provider.

`Poller.start()` / `Poller.stop()` are the FROZEN API that main.py's lifespan
depends on — Agent A (Phase 1A) implements `poll_once` (and may extend the loop)
but must keep start()/stop() working. The Phase-0 `poll_once` is a no-op so the
skeleton boots with an idle loop.
"""
from __future__ import annotations

import asyncio
import dataclasses
import logging
from datetime import UTC, datetime

import anyio
from sqlmodel import Session, select

from .. import db
from ..config import get_settings
from ..constants import TERMINAL_STATES, JobState
from ..models import BatchRun, FoldJob
from ..providers.base import FoldingProvider
from ..providers.factory import get_provider
from . import structures
from .jobs import _rollup_status

logger = logging.getLogger(__name__)

# Normalized states that mean "still in flight" and should be polled.
_ACTIVE_STATES: frozenset[str] = frozenset(
    {JobState.QUEUED.value, JobState.RUNNING.value}
)
_TERMINAL_VALUES: frozenset[str] = frozenset(s.value for s in TERMINAL_STATES)


def reconcile(session: Session, provider: FoldingProvider) -> None:
    """One synchronous reconciliation pass over active jobs (unit-testable).

    For each queued/running FoldJob: ask the provider for status; on terminal
    completion fetch the result, persist scores + structure; on terminal
    failure/stop record the error; otherwise just refresh state. BatchRun
    rollups for affected batches are recomputed. Idempotent and per-job
    fault-isolated (one bad job never aborts the pass).
    """
    jobs = session.exec(
        select(FoldJob).where(FoldJob.state.in_(_ACTIVE_STATES))  # type: ignore[attr-defined]
    ).all()

    affected_batches: set[int] = set()
    for job in jobs:
        try:
            _reconcile_job(session, provider, job)
            if job.batch_run_id is not None:
                affected_batches.add(job.batch_run_id)
        except Exception:  # noqa: BLE001
            logger.exception(
                "reconcile failed for job id=%s provider_job_id=%s",
                job.id,
                job.provider_job_id,
            )
            session.rollback()

    for batch_id in affected_batches:
        try:
            _refresh_batch_rollup(session, batch_id)
        except Exception:  # noqa: BLE001
            logger.exception("batch rollup failed for batch id=%s", batch_id)
            session.rollback()


def _reconcile_job(
    session: Session, provider: FoldingProvider, job: FoldJob
) -> None:
    st = provider.status(job.provider_job_id)
    now = datetime.now(UTC)

    if st.state in TERMINAL_STATES and st.state == JobState.COMPLETED:
        res = provider.fetch_result(job.provider_job_id)
        path = structures.save_structure(
            job.provider_job_id, res.structure_bytes, res.structure_format
        )
        job.scores_json = res.scores
        job.per_model_json = [dataclasses.asdict(e) for e in res.per_model]
        job.structure_path = path
        job.structure_format = res.structure_format
        job.state = JobState.COMPLETED.value
        job.raw_status = st.raw_status
        job.error = None
    elif st.state in (JobState.FAILED, JobState.STOPPED):
        error = None
        try:
            res = provider.fetch_result(job.provider_job_id)
            error = "; ".join(res.messages) if res.messages else None
        except Exception:  # noqa: BLE001
            error = None
        job.state = st.state.value
        job.raw_status = st.raw_status
        job.error = error or st.raw_status or st.state.value
    else:
        job.state = st.state.value
        job.raw_status = st.raw_status

    job.updated_at = now
    session.add(job)
    session.commit()


def _refresh_batch_rollup(session: Session, batch_id: int) -> None:
    batch = session.get(BatchRun, batch_id)
    if batch is None:
        return
    jobs = session.exec(
        select(FoldJob).where(FoldJob.batch_run_id == batch_id)
    ).all()
    rollup = _rollup_status(list(jobs))
    if batch.status != rollup:
        batch.status = rollup
        session.add(batch)
        session.commit()


async def poll_once() -> None:
    """One reconciliation pass.

    Self-contained: opens a DB session, resolves the provider, and runs
    `reconcile` with provider network I/O off the event loop. Idempotent (safe
    to re-run after a restart — state is re-resolved from the provider).
    """
    provider = get_provider()
    with Session(db.engine) as session:
        await anyio.to_thread.run_sync(reconcile, session, provider)


class Poller:
    def __init__(self, interval: float | None = None) -> None:
        self._interval = interval or get_settings().poll_interval_seconds
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        if self._task is None:
            self._stop.clear()
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            try:
                await self._task
            finally:
                self._task = None

    async def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                await poll_once()
            except Exception:  # noqa: BLE001
                logger.exception("poll_once failed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._interval)
            except TimeoutError:
                pass
