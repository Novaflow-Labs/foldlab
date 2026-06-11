"""Tests for app.services.sequences (Agent C / Phase 1C).

Uses an in-memory SQLite engine created here — never touches the default
protein_demo.db (other agents run concurrently).
"""
from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models import Project
from app.schemas import SequenceCreate, SequenceUpdate
from app.services import sequences as svc


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        project = Project(name="Test")
        s.add(project)
        s.commit()
        s.refresh(project)
        s.project_id = project.id  # type: ignore[attr-defined]
        yield s


# --- validate_residues -----------------------------------------------------
def test_validate_residues_uppercases_and_strips():
    assert svc.validate_residues("  giv eq\ncct  ") == "GIVEQCCT"


def test_validate_residues_uppercases_lowercase():
    assert svc.validate_residues("acdef") == "ACDEF"


def test_validate_residues_empty_raises():
    with pytest.raises(ValueError):
        svc.validate_residues("   \n ")


def test_validate_residues_invalid_char_raises():
    with pytest.raises(ValueError) as exc:
        svc.validate_residues("ACXEF")
    # X is at position 3 (1-indexed) after cleaning.
    assert "position 3" in str(exc.value)
    assert "X" in str(exc.value)


# --- apply_edits -----------------------------------------------------------
def test_apply_edits_substitute():
    result = svc.apply_edits("ACDEF", [{"op": "substitute", "position": 1, "residue": "G"}])
    assert result == "GCDEF"


def test_apply_edits_insert():
    # Insert BEFORE position 1 (prepend).
    result = svc.apply_edits("ACDEF", [{"op": "insert", "position": 1, "residue": "M"}])
    assert result == "MACDEF"


def test_apply_edits_insert_append_at_end():
    result = svc.apply_edits("ACDEF", [{"op": "insert", "position": 6, "residue": "W"}])
    assert result == "ACDEFW"


def test_apply_edits_delete():
    result = svc.apply_edits("ACDEF", [{"op": "delete", "position": 2}])
    assert result == "ADEF"


def test_apply_edits_sequential_positions_track_current_state():
    # delete pos 1 (A->CDEF), then substitute pos 1 (C->G) of the NEW state.
    result = svc.apply_edits(
        "ACDEF",
        [
            {"op": "delete", "position": 1},
            {"op": "substitute", "position": 1, "residue": "G"},
        ],
    )
    assert result == "GDEF"


def test_apply_edits_substitute_out_of_range_raises():
    with pytest.raises(ValueError):
        svc.apply_edits("ACDEF", [{"op": "substitute", "position": 6, "residue": "G"}])


def test_apply_edits_delete_out_of_range_raises():
    with pytest.raises(ValueError):
        svc.apply_edits("ACDEF", [{"op": "delete", "position": 0}])


def test_apply_edits_insert_out_of_range_raises():
    with pytest.raises(ValueError):
        svc.apply_edits("ACDEF", [{"op": "insert", "position": 7, "residue": "G"}])


def test_apply_edits_invalid_residue_raises():
    with pytest.raises(ValueError):
        svc.apply_edits("ACDEF", [{"op": "substitute", "position": 1, "residue": "Z"}])


def test_apply_edits_unknown_op_raises():
    with pytest.raises(ValueError):
        svc.apply_edits("ACDEF", [{"op": "frobnicate", "position": 1}])


# --- CRUD ------------------------------------------------------------------
def test_crud_round_trip(session):
    pid = session.project_id  # type: ignore[attr-defined]
    created = svc.create_sequence(
        session,
        SequenceCreate(project_id=pid, name="Seq A", residues="giv eqcct"),
    )
    assert created.id is not None
    assert created.residues == "GIVEQCCT"  # cleaned

    fetched = svc.get_sequence(session, created.id)
    assert fetched is not None
    assert fetched.name == "Seq A"

    listed = svc.list_sequences(session, pid)
    assert [s.id for s in listed] == [created.id]

    updated = svc.update_sequence(
        session, created.id, SequenceUpdate(name="Seq B", residues="ACDEF")
    )
    assert updated.name == "Seq B"
    assert updated.residues == "ACDEF"

    svc.delete_sequence(session, created.id)
    assert svc.get_sequence(session, created.id) is None
    assert svc.list_sequences(session, pid) == []


def test_create_sequence_invalid_residues_raises(session):
    pid = session.project_id  # type: ignore[attr-defined]
    with pytest.raises(ValueError):
        svc.create_sequence(
            session, SequenceCreate(project_id=pid, name="bad", residues="ACXEF")
        )


def test_update_missing_sequence_raises(session):
    with pytest.raises(ValueError):
        svc.update_sequence(session, 9999, SequenceUpdate(name="nope"))


def test_delete_missing_sequence_raises(session):
    with pytest.raises(ValueError):
        svc.delete_sequence(session, 9999)
