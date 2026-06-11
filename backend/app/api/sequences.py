"""Sequences router — real CRUD via services.sequences + the DB.

Keeps the routes/response_models below as the contract the frontend integrates
against. Sequence -> SequenceOut mapping injects `length=len(residues)`.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from ..db import get_session
from ..models import Sequence
from ..schemas import SequenceCreate, SequenceOut, SequenceUpdate
from ..services import sequences as svc

router = APIRouter(prefix="/sequences", tags=["sequences"])


def _to_out(sequence: Sequence) -> SequenceOut:
    return SequenceOut(
        id=sequence.id,
        project_id=sequence.project_id,
        name=sequence.name,
        residues=sequence.residues,
        length=len(sequence.residues),
        kind=sequence.kind,
        parent_id=sequence.parent_id,
        created_at=sequence.created_at,
    )


@router.get("", response_model=list[SequenceOut])
def list_sequences(
    project_id: int, session: Session = Depends(get_session)
) -> list[SequenceOut]:
    return [_to_out(s) for s in svc.list_sequences(session, project_id)]


@router.post("", response_model=SequenceOut)
def create_sequence(
    data: SequenceCreate, session: Session = Depends(get_session)
) -> SequenceOut:
    try:
        sequence = svc.create_sequence(session, data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return _to_out(sequence)


@router.get("/{sequence_id}", response_model=SequenceOut)
def get_sequence(
    sequence_id: int, session: Session = Depends(get_session)
) -> SequenceOut:
    sequence = svc.get_sequence(session, sequence_id)
    if sequence is None:
        raise HTTPException(status_code=404, detail="sequence not found")
    return _to_out(sequence)


@router.put("/{sequence_id}", response_model=SequenceOut)
def update_sequence(
    sequence_id: int, data: SequenceUpdate, session: Session = Depends(get_session)
) -> SequenceOut:
    if svc.get_sequence(session, sequence_id) is None:
        raise HTTPException(status_code=404, detail="sequence not found")
    try:
        sequence = svc.update_sequence(session, sequence_id, data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return _to_out(sequence)


@router.delete("/{sequence_id}", status_code=204)
def delete_sequence(
    sequence_id: int, session: Session = Depends(get_session)
) -> None:
    if svc.get_sequence(session, sequence_id) is None:
        raise HTTPException(status_code=404, detail="sequence not found")
    svc.delete_sequence(session, sequence_id)
    return None
