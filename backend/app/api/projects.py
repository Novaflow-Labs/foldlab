"""Projects router (DB-backed glue — owned by Phase 0 / integration).

Projects scope sequences, jobs, and batches. A default "Demo" project is seeded
at startup (see main.lifespan), so the frontend always has project_id=1.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..db import get_session
from ..models import Project
from ..schemas import ProjectCreate, ProjectOut

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
def list_projects(session: Session = Depends(get_session)) -> list[Project]:
    return list(session.exec(select(Project).order_by(Project.id)).all())


@router.post("", response_model=ProjectOut)
def create_project(data: ProjectCreate, session: Session = Depends(get_session)) -> Project:
    project = Project(name=data.name)
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, session: Session = Depends(get_session)) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project
