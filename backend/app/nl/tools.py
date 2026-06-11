"""Anthropic tool definitions for the NL layer (FROZEN CONTRACT).

Two classes of tool:
  * BACKEND_ACTION_TOOLS — executed server-side, return real tool_result data.
  * UI_DIRECTIVE_TOOLS   — "executed" by recording a viewer Directive (see
    schemas.Directive); the loop emits it to the frontend and returns {"applied": true}.

`directive_from_tool` is the canonical conversion from a UI-directive tool call to a
Directive-shaped dict. Agent B (nl/loop, nl/handlers) imports this; it does not invent tools.
"""
from __future__ import annotations

from typing import Any

from ..constants import FOLD_MODELS, REPRESENTATIONS, VARIANT_STRATEGIES

BACKEND_ACTION_TOOLS: list[dict[str, Any]] = [
    {
        "name": "fetch_sequence",
        "description": (
            "Read a saved protein sequence (residues, length, kind) by id. "
            "Use before reasoning about edits, mutations, or optimization."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"sequence_id": {"type": "integer"}},
            "required": ["sequence_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "edit_sequence",
        "description": (
            "Apply edits to a saved sequence and save the result. Use when the user "
            "asks to mutate, insert, or delete residues. Positions are 1-indexed. "
            "Set save_as to keep the original and save a child sequence."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sequence_id": {"type": "integer"},
                "edits": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "op": {"type": "string", "enum": ["substitute", "insert", "delete"]},
                            "position": {"type": "integer", "description": "1-indexed position"},
                            "residue": {"type": "string", "description": "single-letter AA (substitute/insert)"},
                        },
                        "required": ["op", "position"],
                        "additionalProperties": False,
                    },
                },
                "save_as": {"type": "string", "description": "optional new name; saves a child sequence"},
            },
            "required": ["sequence_id", "edits"],
            "additionalProperties": False,
        },
    },
    {
        "name": "generate_variants",
        "description": (
            "Generate mutational variants from a base sequence (does NOT fold them). "
            "Strategies: positions_subs (params: positions[int], substitutions[str]); "
            "alanine_scan (params: positions[int] optional); pasted (params: sequences[str] "
            "or labeled[{label,residues}]). Use to propose an optimization panel before batch folding."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "base_sequence_id": {"type": "integer"},
                "strategy": {"type": "string", "enum": list(VARIANT_STRATEGIES)},
                "params": {"type": "object"},
            },
            "required": ["base_sequence_id", "strategy"],
            "additionalProperties": False,
        },
    },
    {
        "name": "submit_fold",
        "description": (
            "Submit ONE folding/co-folding job and return a job id immediately (does NOT wait "
            "for the result; the UI shows it when done). One protein sequence = monomer; add "
            "partner_sequence_id or multiple protein_sequences for a complex (e.g. antibody-antigen); "
            "add ligand_smiles for ligand co-folding."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "sequence_id": {"type": "integer", "description": "fold this saved sequence"},
                "protein_sequences": {"type": "array", "items": {"type": "string"}},
                "partner_sequence_id": {"type": "integer", "description": "saved partner/antigen chain"},
                "ligand_smiles": {"type": "array", "items": {"type": "string"}},
                "affinity_ligand_index": {"type": "integer"},
                "model": {"type": "string", "enum": list(FOLD_MODELS)},
            },
            "required": ["project_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "submit_batch_fold",
        "description": (
            "Generate variants from a base sequence and submit them all as a batch run "
            "(optionally each co-folded against a fixed partner/antigen). Returns a batch id and "
            "job ids immediately. Use for antibody optimization / mutational scans."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "base_sequence_id": {"type": "integer"},
                "strategy": {"type": "string", "enum": list(VARIANT_STRATEGIES)},
                "params": {"type": "object"},
                "partner_sequence_id": {"type": "integer"},
                "model": {"type": "string", "enum": list(FOLD_MODELS)},
                "name": {"type": "string"},
            },
            "required": ["project_id", "base_sequence_id", "strategy"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_jobs",
        "description": (
            "List folding jobs and their current state/scores for the project (optionally one "
            "batch). Use to check progress or compare results."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "batch_run_id": {"type": "integer"},
            },
            "required": ["project_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_job_result",
        "description": (
            "Get detailed scores (pTM, ipTM, pLDDT, and binding affinity/pIC50 when available) "
            "for a single job, or the ranked results of a batch. Use to answer 'which variant "
            "binds best' or 'how confident is this fold'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "integer"},
                "batch_run_id": {"type": "integer"},
            },
            "required": [],
            "additionalProperties": False,
        },
    },
]

UI_DIRECTIVE_TOOLS: list[dict[str, Any]] = [
    {
        "name": "color_selection",
        "description": (
            "Color part of the displayed structure. Use when the user asks to highlight/color a "
            "chain, residue, set of residues, or a range. color is a hex string like #e11d48."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "chain": {"type": "string", "description": "chain id, e.g. A"},
                "residues": {"type": "array", "items": {"type": "integer"}},
                "residue_range": {
                    "type": "array", "items": {"type": "integer"},
                    "minItems": 2, "maxItems": 2,
                    "description": "[start,end] inclusive, 1-indexed",
                },
                "color": {"type": "string", "description": "hex color, e.g. #e11d48"},
            },
            "required": ["color"],
            "additionalProperties": False,
        },
    },
    {
        "name": "add_label",
        "description": (
            "Add a text label on a residue in the 3D viewer. Use to annotate a mutation site "
            "or region of interest."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "chain": {"type": "string"},
                "residue": {"type": "integer", "description": "1-indexed position"},
                "text": {"type": "string"},
            },
            "required": ["chain", "residue", "text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "set_representation",
        "description": (
            "Change how (part of) the structure is drawn. Omit chain to apply to the whole structure."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "chain": {"type": "string"},
                "repr": {"type": "string", "enum": list(REPRESENTATIONS)},
            },
            "required": ["repr"],
            "additionalProperties": False,
        },
    },
    {
        "name": "focus_camera",
        "description": "Move the camera to focus on a chain, residue set, or range.",
        "input_schema": {
            "type": "object",
            "properties": {
                "chain": {"type": "string"},
                "residues": {"type": "array", "items": {"type": "integer"}},
                "residue_range": {
                    "type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2,
                },
            },
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "name": "select_region",
        "description": "Select/highlight a residue range on a chain. [start,end] inclusive, 1-indexed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "chain": {"type": "string"},
                "residue_range": {
                    "type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2,
                },
            },
            "required": ["chain", "residue_range"],
            "additionalProperties": False,
        },
    },
]

ALL_TOOLS: list[dict[str, Any]] = BACKEND_ACTION_TOOLS + UI_DIRECTIVE_TOOLS
BACKEND_ACTION_NAMES: frozenset[str] = frozenset(t["name"] for t in BACKEND_ACTION_TOOLS)
UI_DIRECTIVE_NAMES: frozenset[str] = frozenset(t["name"] for t in UI_DIRECTIVE_TOOLS)

_DIRECTIVE_KIND_BY_TOOL: dict[str, str] = {
    "color_selection": "color",
    "add_label": "label",
    "set_representation": "representation",
    "focus_camera": "focus",
    "select_region": "select",
}


def directive_from_tool(name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    """Convert a UI-directive tool call into a Directive-shaped dict (see schemas.Directive)."""
    kind = _DIRECTIVE_KIND_BY_TOOL[name]
    target = {
        "chain": tool_input.get("chain"),
        "residue": tool_input.get("residue"),
        "residues": tool_input.get("residues"),
        "residue_range": tool_input.get("residue_range"),
    }
    target = {k: v for k, v in target.items() if v is not None}
    payload: dict[str, Any] = {"kind": kind, "target": target}
    if name == "color_selection":
        payload["color"] = tool_input.get("color")
    elif name == "add_label":
        payload["text"] = tool_input.get("text")
    elif name == "set_representation":
        payload["repr"] = tool_input.get("repr")
    return payload
