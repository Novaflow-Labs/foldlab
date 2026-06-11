"""Folding router — wired to services.jobs + services.structures.

Routes stay synchronous `def` (FastAPI runs them in a worker thread, so the
provider/DB calls inside the services are safe). Response models, paths, and the
/jobs/{id}/structure byte contract (with X-Structure-Format header) are frozen.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import Session

from ..db import get_session
from ..schemas import (
    BatchFoldRequest,
    BatchRunOut,
    BatchSubmitResponse,
    FoldJobOut,
    FoldSubmitRequest,
    JobRef,
)
from ..services import jobs as jobs_service
from ..services import structures

router = APIRouter(tags=["folding"])

# Normalized structure format -> HTTP media type for the byte response.
_MEDIA_TYPE_BY_FORMAT: dict[str, str] = {
    "pdb": "chemical/x-pdb",
    "mmcif": "chemical/x-cif",
}


@router.post("/fold", response_model=JobRef)
def submit_fold(
    req: FoldSubmitRequest, session: Session = Depends(get_session)
) -> JobRef:
    job = jobs_service.submit_fold(session, req)
    return JobRef(
        job_id=job.id,
        provider_job_id=job.provider_job_id,
        state=job.state,
        label=job.label,
    )


@router.post("/fold/batch", response_model=BatchSubmitResponse)
def submit_batch(
    req: BatchFoldRequest, session: Session = Depends(get_session)
) -> BatchSubmitResponse:
    batch, batch_jobs = jobs_service.submit_batch(session, req)
    return BatchSubmitResponse(
        batch_run_id=batch.id,
        jobs=[
            JobRef(
                job_id=job.id,
                provider_job_id=job.provider_job_id,
                state=job.state,
                label=job.label,
            )
            for job in batch_jobs
        ],
    )


@router.get("/jobs", response_model=list[FoldJobOut])
def list_jobs(
    project_id: int,
    batch_run_id: int | None = None,
    session: Session = Depends(get_session),
) -> list[FoldJobOut]:
    return [
        jobs_service.to_job_out(job)
        for job in jobs_service.list_jobs(session, project_id, batch_run_id)
    ]


@router.get("/jobs/{job_id}", response_model=FoldJobOut)
def get_job(
    job_id: int, session: Session = Depends(get_session)
) -> FoldJobOut:
    job = jobs_service.get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return jobs_service.to_job_out(job)


@router.get("/jobs/{job_id}/structure")
def get_structure(
    job_id: int, session: Session = Depends(get_session)
) -> Response:
    job = jobs_service.get_job(session, job_id)
    if job is None or not job.structure_path:
        raise HTTPException(status_code=404, detail="structure not available")
    data = structures.read_structure(job.structure_path)
    fmt = job.structure_format or "pdb"
    media_type = _MEDIA_TYPE_BY_FORMAT.get(fmt, "application/octet-stream")
    return Response(
        content=data,
        media_type=media_type,
        headers={"X-Structure-Format": fmt},
    )


@router.get("/batches", response_model=list[BatchRunOut])
def list_batches(
    project_id: int, session: Session = Depends(get_session)
) -> list[BatchRunOut]:
    return jobs_service.list_batches(session, project_id)
