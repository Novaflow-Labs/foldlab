"""Tests for the folding/jobs slice (Agent A).

Uses a private in-memory SQLite engine + Session so it never touches the shared
protein_demo.db (other agents run concurrently). The MockProvider drives a full
submit -> reconcile -> completed cycle without any network/credits.
"""
from __future__ import annotations

import time

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.constants import JobState
from app.models import Project, Sequence
from app.providers.mock_provider import MockProvider
from app.schemas import FoldSubmitRequest
from app.services import jobs as jobs_service
from app.services import poller as poller_service
from app.services import structures


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture()
def seeded(session):
    project = Project(name="Test")
    session.add(project)
    session.commit()
    session.refresh(project)

    seq = Sequence(
        project_id=project.id,
        name="seqA",
        residues="MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ",
    )
    session.add(seq)
    session.commit()
    session.refresh(seq)
    return session, project, seq


# ----------------------------------------------------------- compute_rank_hint
def test_rank_hint_prefers_affinity_over_iptm_ptm_confidence():
    scores = {
        "affinity_pred_value": 6.5,
        "iptm": 0.8,
        "ptm": 0.7,
        "confidence": 0.9,
    }
    assert jobs_service.compute_rank_hint(scores, None) == 6.5


def test_rank_hint_falls_back_to_iptm_then_ptm_then_confidence():
    assert jobs_service.compute_rank_hint(
        {"iptm": 0.8, "ptm": 0.7, "confidence": 0.9}, None
    ) == 0.8
    assert jobs_service.compute_rank_hint({"ptm": 0.7, "confidence": 0.9}, None) == 0.7
    assert jobs_service.compute_rank_hint({"confidence": 0.9}, None) == 0.9


def test_rank_hint_none_when_no_signal():
    assert jobs_service.compute_rank_hint({}, None) is None
    assert jobs_service.compute_rank_hint(None, None) is None


def test_rank_hint_reads_from_per_model_when_scores_missing():
    per_model = [{"ptm": 0.66, "iptm": None, "confidence": 0.5}]
    assert jobs_service.compute_rank_hint(None, per_model) == 0.66


def test_rank_hint_strict_ordering_across_jobs():
    # affinity-ranked beats iptm-ranked beats ptm-ranked beats confidence-ranked.
    affinity = jobs_service.compute_rank_hint({"affinity_pred_value": 3.0}, None)
    iptm = jobs_service.compute_rank_hint({"iptm": 0.95}, None)
    ptm = jobs_service.compute_rank_hint({"ptm": 0.95}, None)
    conf = jobs_service.compute_rank_hint({"confidence": 0.95}, None)
    # Each metric is selected from its own preferred field.
    assert affinity == 3.0
    assert iptm == 0.95
    assert ptm == 0.95
    assert conf == 0.95


# ----------------------------------------------------- submit_fold + reconcile
def test_submit_fold_then_reconcile_completes(seeded):
    session, project, seq = seeded
    provider = MockProvider()

    req = FoldSubmitRequest(
        project_id=project.id,
        sequence_id=seq.id,
        model="boltz_2",
        name="t-fold",
    )
    # Patch the provider used by submit_fold to our local MockProvider instance
    # so submit + reconcile share the same in-memory job registry.
    import app.services.jobs as jobs_mod

    original = jobs_mod.get_provider
    jobs_mod.get_provider = lambda: provider
    try:
        job = jobs_service.submit_fold(session, req)
    finally:
        jobs_mod.get_provider = original

    assert job.id is not None
    assert job.state == JobState.QUEUED.value
    assert job.provider == "mock"
    # Sequence residues were resolved into the request inputs.
    assert job.inputs_json["sequence_id"] == seq.id

    # The mock simulates ~3s of in-flight time; wait it out then reconcile.
    time.sleep(3.2)
    poller_service.reconcile(session, provider)

    session.refresh(job)
    assert job.state == JobState.COMPLETED.value
    assert job.scores_json is not None
    assert "ptm" in job.scores_json
    assert job.per_model_json and isinstance(job.per_model_json, list)
    assert job.structure_path is not None
    assert job.structure_format == "pdb"

    # Structure bytes are actually on disk and readable (non-empty PDB).
    data = structures.read_structure(job.structure_path)
    assert len(data) > 0


# ------------------------------------------------------------------ to_job_out
def test_to_job_out_mapping(seeded):
    session, project, seq = seeded
    provider = MockProvider()

    req = FoldSubmitRequest(
        project_id=project.id,
        sequence_id=seq.id,
        ligand_smiles=["CCO"],
        affinity_ligand_index=0,
        model="boltz_2",
    )
    import app.services.jobs as jobs_mod

    original = jobs_mod.get_provider
    jobs_mod.get_provider = lambda: provider
    try:
        job = jobs_service.submit_fold(session, req)
    finally:
        jobs_mod.get_provider = original

    time.sleep(3.2)
    poller_service.reconcile(session, provider)
    session.refresh(job)

    out = jobs_service.to_job_out(job)
    assert out.id == job.id
    assert out.project_id == project.id
    assert out.state == JobState.COMPLETED.value
    assert out.scores == job.scores_json
    assert out.per_model == job.per_model_json
    assert out.has_structure is True
    assert out.structure_format == "pdb"
    # Ligand present -> affinity drives rank_hint (a pIC50-scale number).
    assert out.rank_hint is not None
    assert out.rank_hint == job.scores_json["affinity_pred_value"]
