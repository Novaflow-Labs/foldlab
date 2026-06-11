"""Sequence CRUD + validation.

FROZEN SIGNATURES — Agent C (Phase 1C) implements the bodies; do NOT change the
signatures (api/sequences.py and nl/handlers.py both call these). Pure helpers
(`validate_residues`, `apply_edits`) have no DB access and are unit-testable.
"""
from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from ..constants import AMINO_ACIDS
from ..models import Sequence
from ..schemas import SequenceCreate, SequenceUpdate


def validate_residues(residues: str) -> str:
    """Uppercase + strip whitespace; validate against the 20-AA alphabet.

    Returns the cleaned residue string. Raises ValueError on any invalid character.
    """
    cleaned = "".join(residues.split()).upper()
    if not cleaned:
        raise ValueError("residues must be non-empty")
    for i, ch in enumerate(cleaned, start=1):
        if ch not in AMINO_ACIDS:
            raise ValueError(f"invalid residue '{ch}' at position {i}")
    return cleaned


def apply_edits(residues: str, edits: list[dict[str, Any]]) -> str:
    """Apply ordered substitute/insert/delete edits (positions 1-indexed) and
    return the new, validated residue string. Raises ValueError on bad ops/positions.
    """
    chars = list(validate_residues(residues))
    for edit in edits:
        op = edit.get("op")
        position = edit.get("position")
        if not isinstance(position, int):
            raise ValueError(f"edit position must be an integer, got {position!r}")

        if op == "substitute":
            if not (1 <= position <= len(chars)):
                raise ValueError(
                    f"substitute position {position} out of range 1..{len(chars)}"
                )
            residue = _validate_edit_residue(edit, op)
            chars[position - 1] = residue
        elif op == "insert":
            # Insert BEFORE `position`; position may be len+1 (append).
            if not (1 <= position <= len(chars) + 1):
                raise ValueError(
                    f"insert position {position} out of range 1..{len(chars) + 1}"
                )
            residue = _validate_edit_residue(edit, op)
            chars.insert(position - 1, residue)
        elif op == "delete":
            if not (1 <= position <= len(chars)):
                raise ValueError(
                    f"delete position {position} out of range 1..{len(chars)}"
                )
            del chars[position - 1]
        else:
            raise ValueError(f"unknown edit op {op!r}")

    return validate_residues("".join(chars))


def _validate_edit_residue(edit: dict[str, Any], op: str) -> str:
    """Extract + validate a single-letter AA from a substitute/insert edit."""
    residue = edit.get("residue")
    if not isinstance(residue, str):
        raise ValueError(f"{op} edit requires a 'residue'")
    cleaned = residue.strip().upper()
    if len(cleaned) != 1 or cleaned not in AMINO_ACIDS:
        raise ValueError(f"invalid residue '{residue}' for {op}")
    return cleaned


def create_sequence(session: Session, data: SequenceCreate) -> Sequence:
    residues = validate_residues(data.residues)
    sequence = Sequence(
        project_id=data.project_id,
        name=data.name,
        residues=residues,
        kind=data.kind,
        parent_id=data.parent_id,
    )
    session.add(sequence)
    session.commit()
    session.refresh(sequence)
    return sequence


def get_sequence(session: Session, sequence_id: int) -> Sequence | None:
    return session.get(Sequence, sequence_id)


def list_sequences(session: Session, project_id: int) -> list[Sequence]:
    statement = (
        select(Sequence)
        .where(Sequence.project_id == project_id)
        .order_by(Sequence.id)
    )
    return list(session.exec(statement).all())


def update_sequence(session: Session, sequence_id: int, data: SequenceUpdate) -> Sequence:
    sequence = session.get(Sequence, sequence_id)
    if sequence is None:
        raise ValueError(f"sequence {sequence_id} not found")
    if data.name is not None:
        sequence.name = data.name
    if data.residues is not None:
        sequence.residues = validate_residues(data.residues)
    if data.kind is not None:
        sequence.kind = data.kind
    session.add(sequence)
    session.commit()
    session.refresh(sequence)
    return sequence


def delete_sequence(session: Session, sequence_id: int) -> None:
    sequence = session.get(Sequence, sequence_id)
    if sequence is None:
        raise ValueError(f"sequence {sequence_id} not found")
    session.delete(sequence)
    session.commit()
