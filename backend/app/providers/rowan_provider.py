"""Rowan-backed folding provider (protein co-folding via rowan-python).

Wraps `rowan.submit_protein_cofolding_workflow` / `retrieve_workflow` behind the
FoldingProvider seam. All SDK calls are synchronous here; async callers (the
poller, chat loop) wrap provider methods in `anyio.to_thread.run_sync`.

The Rowan SDK emits PDB only — `Protein.download_pdb_file(path)` writes a file,
there is no in-memory / mmCIF accessor. We therefore download to a NamedTemporary
file and read the bytes back, reporting `structure_format="pdb"`.
"""
from __future__ import annotations

import os
import tempfile
from typing import Any

import rowan

from ..config import get_settings
from ..constants import ROWAN_STATUS_MAP, JobState
from .base import (
    FoldingProvider,
    FoldRequest,
    FoldResult,
    FoldStatus,
    PerModelExtras,
)


def _status_name(workflow: Any) -> str | None:
    """Extract the Rowan Status enum NAME from a workflow (defensively)."""
    status = getattr(workflow, "status", None)
    if status is None:
        return None
    # stjames.Status is an Enum; fall back to str() for anything else.
    return getattr(status, "name", None) or str(status)


def _to_status(workflow: Any) -> FoldStatus:
    """Map a retrieved workflow to a normalized FoldStatus."""
    name = _status_name(workflow)
    state = ROWAN_STATUS_MAP.get(name or "", JobState.RUNNING)
    return FoldStatus(
        provider_job_id=str(workflow.uuid),
        state=state,
        raw_status=name,
    )


def _message_text(msg: Any) -> str:
    """Render a Rowan workflow message (dataclass | str | other) to text."""
    if isinstance(msg, str):
        return msg
    title = getattr(msg, "title", None)
    body = getattr(msg, "body", None)
    if title or body:
        return ": ".join(part for part in (title, body) if part)
    return str(msg)


class RowanProvider(FoldingProvider):
    name = "rowan"

    def __init__(self) -> None:
        settings = get_settings()
        rowan.api_key = settings.rowan_api_key

    @staticmethod
    def _validate_model(model: str) -> None:
        valid = [m.value for m in rowan.CofoldingModel]
        if model not in valid:
            raise ValueError(
                f"Invalid model '{model}'. Must be one of: {', '.join(valid)}"
            )

    def submit(self, req: FoldRequest) -> FoldStatus:
        self._validate_model(req.model)
        wf = rowan.submit_protein_cofolding_workflow(
            initial_protein_sequences=req.protein_sequences,
            initial_smiles_list=(req.ligand_smiles or None),
            ligand_binding_affinity_index=req.affinity_ligand_index,
            model=req.model,
            name=req.name,
            use_msa_server=req.use_msa_server,
            num_samples=req.num_samples,
            do_pose_refinement=req.do_pose_refinement,
            max_credits=req.max_credits,
        )
        name = _status_name(wf)
        state = ROWAN_STATUS_MAP.get(name or "", JobState.QUEUED)
        return FoldStatus(
            provider_job_id=str(wf.uuid),
            state=state,
            raw_status=name,
        )

    def batch_submit(self, reqs: list[FoldRequest]) -> list[FoldStatus]:
        return [self.submit(r) for r in reqs]

    def status(self, provider_job_id: str) -> FoldStatus:
        wf = rowan.retrieve_workflow(provider_job_id)
        return _to_status(wf)

    def fetch_result(self, provider_job_id: str) -> FoldResult:
        wf = rowan.retrieve_workflow(provider_job_id)
        result = wf.result(wait=False)

        scores_obj = getattr(result, "scores", None)
        affinity = getattr(result, "affinity_score", None)

        # Normalized top-level scores dict (snake_case, provider-agnostic keys).
        scores: dict[str, Any] = {
            "ptm": getattr(scores_obj, "ptm", None),
            "iptm": getattr(scores_obj, "iptm", None),
            "avg_lddt": getattr(scores_obj, "avg_lddt", None),
            "confidence": getattr(scores_obj, "confidence_score", None),
        }
        if affinity is not None:
            scores["affinity_pred_value"] = getattr(affinity, "pred_value", None)
            scores["affinity_probability"] = getattr(
                affinity, "probability_binary", None
            )

        per_model = self._build_per_model(result, scores_obj, affinity)
        structure_bytes = self._download_pdb_bytes(result)
        messages = [
            _message_text(m) for m in (getattr(result, "messages", None) or [])
        ]

        return FoldResult(
            provider_job_id=provider_job_id,
            structure_bytes=structure_bytes,
            structure_format="pdb",
            scores=scores,
            per_model=per_model,
            messages=messages,
        )

    @staticmethod
    def _build_per_model(
        result: Any, top_scores: Any, top_affinity: Any
    ) -> list[PerModelExtras]:
        """One PerModelExtras per returned sample (falling back to top-level)."""
        predictions = list(getattr(result, "predictions", None) or [])
        extras: list[PerModelExtras] = []
        for pred in predictions:
            p_scores = getattr(pred, "scores", None)
            p_aff = getattr(pred, "affinity_score", None)
            extras.append(
                PerModelExtras(
                    ptm=getattr(p_scores, "ptm", None),
                    iptm=getattr(p_scores, "iptm", None),
                    avg_lddt=getattr(p_scores, "avg_lddt", None),
                    confidence=getattr(p_scores, "confidence_score", None),
                    affinity_pred_value=getattr(p_aff, "pred_value", None),
                    affinity_probability=getattr(p_aff, "probability_binary", None),
                    strain=getattr(pred, "strain", None),
                    posebusters_valid=getattr(pred, "posebusters_valid", None),
                )
            )
        if extras:
            return extras
        # No per-sample breakdown returned: synthesize one from top-level data.
        return [
            PerModelExtras(
                ptm=getattr(top_scores, "ptm", None),
                iptm=getattr(top_scores, "iptm", None),
                avg_lddt=getattr(top_scores, "avg_lddt", None),
                confidence=getattr(top_scores, "confidence_score", None),
                affinity_pred_value=getattr(top_affinity, "pred_value", None),
                affinity_probability=getattr(
                    top_affinity, "probability_binary", None
                ),
                strain=getattr(result, "strain", None),
                posebusters_valid=getattr(result, "posebusters_valid", None),
            )
        ]

    @staticmethod
    def _download_pdb_bytes(result: Any) -> bytes:
        """Fetch the predicted structure and read its PDB bytes off a temp file."""
        protein = result.get_predicted_structure()
        if protein is None:
            raise RuntimeError("Rowan result has no predicted structure")
        tmp_path: str | None = None
        try:
            fd, tmp_path = tempfile.mkstemp(suffix=".pdb")
            os.close(fd)
            protein.download_pdb_file(tmp_path)
            with open(tmp_path, "rb") as fh:
                return fh.read()
        finally:
            if tmp_path is not None:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
