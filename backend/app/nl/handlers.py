"""Tool dispatch for the NL layer.

`dispatch_tool` turns one Anthropic `tool_use` block into:
  * a JSON string for the `tool_result` content (what the model sees next), and
  * a list of SSE events to forward to the frontend (directive / job).

UI-directive tools are "executed" by recording + emitting a viewer Directive.
Backend-action tools call the frozen service functions (sequences/variants/jobs),
which are synchronous, so they run in a worker thread via `anyio.to_thread.run_sync`.

The service bodies are implemented by other agents; this module only calls their frozen
signatures. Errors are caught and returned as `is_error` tool_results so the model can
recover within the loop instead of the stream dying.
"""
from __future__ import annotations

import json
from typing import Any

import anyio
from sqlmodel import Session

from .. import models, schemas
from ..constants import DEFAULT_FOLD_MODEL
from ..services import jobs, sequences, variants
from .tools import BACKEND_ACTION_NAMES, UI_DIRECTIVE_NAMES, directive_from_tool

# An SSE event the loop will forward: {"event": <SSEEvent value>, "data": <dict>}.
SSEEventDict = dict[str, Any]


def _dumps(data: Any) -> str:
    """Stable, model-facing JSON (sorted keys keep tool_result content deterministic)."""
    return json.dumps(data, sort_keys=True, default=str)


async def dispatch_tool(
    session: Session,
    project_id: int,
    name: str,
    tool_input: dict[str, Any],
) -> tuple[str, list[SSEEventDict]]:
    """Execute one tool call. Returns (tool_result_content_json, sse_events).

    Never raises: failures are converted into an error tool_result string the model can read.
    """
    try:
        if name in UI_DIRECTIVE_NAMES:
            return _handle_directive(session, project_id, name, tool_input)
        if name in BACKEND_ACTION_NAMES:
            return await _handle_backend_action(session, project_id, name, tool_input)
        return _dumps({"error": f"Unknown tool: {name}"}), []
    except Exception as exc:  # noqa: BLE001 - surface any failure back to the model
        return _dumps({"error": f"{type(exc).__name__}: {exc}"}), []


# ---------------------------------------------------------------- UI directives
def _handle_directive(
    session: Session,
    project_id: int,
    name: str,
    tool_input: dict[str, Any],
) -> tuple[str, list[SSEEventDict]]:
    payload = directive_from_tool(name, tool_input)
    # Validate the shape against the frozen schema (raises -> caught by dispatch_tool).
    schemas.Directive(**payload)

    # Persist a Directive row (best-effort; the viewer is driven by the SSE event).
    # Persistence failure (incl. a missing/broken session) must never abort the directive.
    try:
        row = models.Directive(
            project_id=project_id,
            kind=payload["kind"],
            payload_json=payload,
            source="chat",
        )
        session.add(row)
        session.commit()
    except Exception:  # noqa: BLE001 - non-critical; the SSE directive is what matters
        try:
            session.rollback()
        except Exception:  # noqa: BLE001
            pass

    events = [{"event": schemas.SSEEvent.directive.value, "data": payload}]
    return _dumps({"applied": True}), events


# ---------------------------------------------------------------- Backend actions
async def _handle_backend_action(
    session: Session,
    project_id: int,
    name: str,
    tool_input: dict[str, Any],
) -> tuple[str, list[SSEEventDict]]:
    if name == "fetch_sequence":
        return await _fetch_sequence(session, tool_input)
    if name == "edit_sequence":
        return await _edit_sequence(session, tool_input)
    if name == "generate_variants":
        return await _generate_variants(session, tool_input)
    if name == "submit_fold":
        return await _submit_fold(session, project_id, tool_input)
    if name == "submit_batch_fold":
        return await _submit_batch_fold(session, project_id, tool_input)
    if name == "list_jobs":
        return await _list_jobs(session, project_id, tool_input)
    if name == "get_job_result":
        return await _get_job_result(session, project_id, tool_input)
    return _dumps({"error": f"Unhandled backend action: {name}"}), []


def _require(tool_input: dict[str, Any], key: str) -> Any:
    if key not in tool_input or tool_input[key] is None:
        raise ValueError(f"Missing required argument: {key}")
    return tool_input[key]


async def _fetch_sequence(
    session: Session, tool_input: dict[str, Any]
) -> tuple[str, list[SSEEventDict]]:
    seq_id = _require(tool_input, "sequence_id")
    seq = await anyio.to_thread.run_sync(sequences.get_sequence, session, seq_id)
    if seq is None:
        return _dumps({"error": f"Sequence {seq_id} not found"}), []
    return _dumps(
        {
            "id": seq.id,
            "name": seq.name,
            "residues": seq.residues,
            "length": len(seq.residues),
            "kind": seq.kind,
        }
    ), []


async def _edit_sequence(
    session: Session, tool_input: dict[str, Any]
) -> tuple[str, list[SSEEventDict]]:
    seq_id = _require(tool_input, "sequence_id")
    edits = _require(tool_input, "edits")
    save_as = tool_input.get("save_as")

    seq = await anyio.to_thread.run_sync(sequences.get_sequence, session, seq_id)
    if seq is None:
        return _dumps({"error": f"Sequence {seq_id} not found"}), []

    new_residues = await anyio.to_thread.run_sync(
        sequences.apply_edits, seq.residues, edits
    )

    if save_as:
        data = schemas.SequenceCreate(
            project_id=seq.project_id,
            name=save_as,
            residues=new_residues,
            kind=seq.kind,
            parent_id=seq.id,
        )
        child = await anyio.to_thread.run_sync(sequences.create_sequence, session, data)
        return _dumps(
            {
                "saved_as_new": True,
                "id": child.id,
                "name": child.name,
                "residues": child.residues,
                "length": len(child.residues),
                "parent_id": seq.id,
            }
        ), []

    update = schemas.SequenceUpdate(residues=new_residues)
    updated = await anyio.to_thread.run_sync(
        sequences.update_sequence, session, seq_id, update
    )
    return _dumps(
        {
            "saved_as_new": False,
            "id": updated.id,
            "name": updated.name,
            "residues": updated.residues,
            "length": len(updated.residues),
        }
    ), []


async def _generate_variants(
    session: Session, tool_input: dict[str, Any]
) -> tuple[str, list[SSEEventDict]]:
    base_id = _require(tool_input, "base_sequence_id")
    strategy = _require(tool_input, "strategy")
    params = tool_input.get("params") or {}

    base = await anyio.to_thread.run_sync(sequences.get_sequence, session, base_id)
    if base is None:
        return _dumps({"error": f"Base sequence {base_id} not found"}), []

    variant_list = await anyio.to_thread.run_sync(
        variants.generate, base.residues, strategy, params
    )
    return _dumps(
        {
            "base_sequence_id": base_id,
            "strategy": strategy,
            "count": len(variant_list),
            "variants": [v.model_dump() for v in variant_list],
        }
    ), []


async def _submit_fold(
    session: Session, project_id: int, tool_input: dict[str, Any]
) -> tuple[str, list[SSEEventDict]]:
    mapped: dict[str, Any] = {"project_id": tool_input.get("project_id", project_id)}
    for key in (
        "sequence_id",
        "protein_sequences",
        "partner_sequence_id",
        "copies",
        "ligand_smiles",
        "affinity_ligand_index",
        "model",
    ):
        if tool_input.get(key) is not None:
            mapped[key] = tool_input[key]

    req = schemas.FoldSubmitRequest(**mapped)
    job = await anyio.to_thread.run_sync(jobs.submit_fold, session, req)

    job_event = {
        "job_id": job.id,
        "provider_job_id": job.provider_job_id,
        "state": job.state,
        "label": job.label,
    }
    events = [{"event": schemas.SSEEvent.job.value, "data": job_event}]
    return _dumps(
        {"submitted": True, "job_id": job.id, "state": job.state, "label": job.label}
    ), events


async def _submit_batch_fold(
    session: Session, project_id: int, tool_input: dict[str, Any]
) -> tuple[str, list[SSEEventDict]]:
    base_id = _require(tool_input, "base_sequence_id")
    strategy = _require(tool_input, "strategy")
    params = tool_input.get("params") or {}
    pid = tool_input.get("project_id", project_id)

    base = await anyio.to_thread.run_sync(sequences.get_sequence, session, base_id)
    if base is None:
        return _dumps({"error": f"Base sequence {base_id} not found"}), []

    variant_list = await anyio.to_thread.run_sync(
        variants.generate, base.residues, strategy, params
    )
    if not variant_list:
        return _dumps({"error": "No variants generated; nothing to batch."}), []

    items = [
        schemas.BatchFoldItem(label=v.label, protein_sequences=[v.residues])
        for v in variant_list
    ]
    batch_req = schemas.BatchFoldRequest(
        project_id=pid,
        items=items,
        model=tool_input.get("model", DEFAULT_FOLD_MODEL),
        partner_sequence_id=tool_input.get("partner_sequence_id"),
        name=tool_input.get("name", "batch"),
    )

    def _run() -> tuple[Any, list[Any]]:
        return jobs.submit_batch(
            session,
            batch_req,
            base_sequence_id=base_id,
            strategy=strategy,
            params=params,
        )

    batch_run, created_jobs = await anyio.to_thread.run_sync(_run)

    events: list[SSEEventDict] = []
    job_ids: list[int | None] = []
    for job in created_jobs:
        job_ids.append(job.id)
        events.append(
            {
                "event": schemas.SSEEvent.job.value,
                "data": {
                    "job_id": job.id,
                    "provider_job_id": job.provider_job_id,
                    "state": job.state,
                    "label": job.label,
                },
            }
        )

    return _dumps(
        {
            "submitted": True,
            "batch_run_id": batch_run.id,
            "job_count": len(job_ids),
            "job_ids": job_ids,
        }
    ), events


async def _list_jobs(
    session: Session, project_id: int, tool_input: dict[str, Any]
) -> tuple[str, list[SSEEventDict]]:
    pid = tool_input.get("project_id", project_id)
    batch_run_id = tool_input.get("batch_run_id")

    job_rows = await anyio.to_thread.run_sync(
        jobs.list_jobs, session, pid, batch_run_id
    )
    out = [jobs.to_job_out(j).model_dump() for j in job_rows]
    return _dumps({"count": len(out), "jobs": out}), []


async def _get_job_result(
    session: Session, project_id: int, tool_input: dict[str, Any]
) -> tuple[str, list[SSEEventDict]]:
    job_id = tool_input.get("job_id")
    batch_run_id = tool_input.get("batch_run_id")

    if job_id is not None:
        job = await anyio.to_thread.run_sync(jobs.get_job, session, job_id)
        if job is None:
            return _dumps({"error": f"Job {job_id} not found"}), []
        return _dumps({"job": jobs.to_job_out(job).model_dump()}), []

    if batch_run_id is not None:
        pid = tool_input.get("project_id", project_id)
        job_rows = await anyio.to_thread.run_sync(
            jobs.list_jobs, session, pid, batch_run_id
        )
        ranked = sorted(
            (jobs.to_job_out(j).model_dump() for j in job_rows),
            key=lambda j: (j.get("rank_hint") is None, -(j.get("rank_hint") or 0.0)),
        )
        return _dumps({"batch_run_id": batch_run_id, "ranked": ranked}), []

    return _dumps({"error": "Provide either job_id or batch_run_id."}), []
