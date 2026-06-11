"""Variant generation (pure, backend-only).

FROZEN SIGNATURE — Agent C (Phase 1C) implements the body; do NOT change the
signature (api/variants.py and nl/handlers.py call `generate`). The "claude"
strategy uses the Anthropic client (messages.parse) to PROPOSE mutations, but
this function APPLIES + validates them against the base.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from ..config import get_settings
from ..constants import AMINO_ACIDS
from ..schemas import VariantOut
from .sequences import validate_residues

# Hard cap on the number of variants returned by any strategy.
MAX_VARIANTS = 96


def generate(base_residues: str, strategy: str, params: dict[str, Any]) -> list[VariantOut]:
    """Return a list of variants (label, residues, mutations) for the base sequence.

    Strategies:
      * positions_subs — params: {positions: [int], substitutions: [str], include_wt?: bool, max_variants?: int}
      * alanine_scan   — params: {positions?: [int]}  (default: all non-Ala positions)
      * claude         — params: {n: int, rationale_prompt?: str}  (proposes via messages.parse)
      * pasted         — params: {sequences: [str]} or {labeled: [{label, residues}]}
    Positions are 1-indexed. Raises ValueError on invalid input.
    """
    base = validate_residues(base_residues)
    params = params or {}

    if strategy == "positions_subs":
        variants = _positions_subs(base, params)
    elif strategy == "alanine_scan":
        variants = _alanine_scan(base, params)
    elif strategy == "pasted":
        variants = _pasted(base, params)
    elif strategy == "claude":
        variants = _claude(base, params)
    else:
        raise ValueError(f"unknown variant strategy {strategy!r}")

    return _dedupe_and_cap(variants)


def _dedupe_and_cap(variants: list[VariantOut]) -> list[VariantOut]:
    """Dedupe by residues (first occurrence wins), validate, and cap at MAX_VARIANTS."""
    seen: set[str] = set()
    result: list[VariantOut] = []
    for v in variants:
        residues = validate_residues(v.residues)
        if residues in seen:
            continue
        seen.add(residues)
        if len(result) >= MAX_VARIANTS:
            # Capped: callers that surface a summary can detect truncation by
            # len(result) == MAX_VARIANTS and note it.
            break
        result.append(VariantOut(label=v.label, residues=residues, mutations=v.mutations))
    return result


def _validate_aa(residue: str, *, context: str) -> str:
    cleaned = residue.strip().upper()
    if len(cleaned) != 1 or cleaned not in AMINO_ACIDS:
        raise ValueError(f"invalid substitution '{residue}' ({context})")
    return cleaned


def _positions_subs(base: str, params: dict[str, Any]) -> list[VariantOut]:
    positions = params.get("positions")
    substitutions = params.get("substitutions")
    if not positions:
        raise ValueError("positions_subs requires a non-empty 'positions' list")
    if not substitutions:
        raise ValueError("positions_subs requires a non-empty 'substitutions' list")
    include_wt = bool(params.get("include_wt", False))
    max_variants = params.get("max_variants")

    subs = [_validate_aa(s, context="positions_subs") for s in substitutions]

    variants: list[VariantOut] = []
    if include_wt:
        variants.append(VariantOut(label="WT", residues=base, mutations=[]))

    for p in positions:
        if not isinstance(p, int) or not (1 <= p <= len(base)):
            raise ValueError(f"position {p} out of range 1..{len(base)}")
        wt = base[p - 1]
        for s in subs:
            if s == wt:
                continue
            mutated = base[: p - 1] + s + base[p:]
            label = f"{wt}{p}{s}"
            variants.append(
                VariantOut(label=label, residues=mutated, mutations=[label])
            )
            if max_variants is not None and len(variants) >= max_variants:
                return variants
    return variants


def _alanine_scan(base: str, params: dict[str, Any]) -> list[VariantOut]:
    positions = params.get("positions")
    if positions is None:
        positions = [i for i, ch in enumerate(base, start=1) if ch != "A"]

    variants: list[VariantOut] = [VariantOut(label="WT", residues=base, mutations=[])]
    for p in positions:
        if not isinstance(p, int) or not (1 <= p <= len(base)):
            raise ValueError(f"position {p} out of range 1..{len(base)}")
        wt = base[p - 1]
        if wt == "A":
            continue
        mutated = base[: p - 1] + "A" + base[p:]
        label = f"{wt}{p}A"
        variants.append(VariantOut(label=label, residues=mutated, mutations=[label]))
    return variants


def _pasted(base: str, params: dict[str, Any]) -> list[VariantOut]:
    labeled = params.get("labeled")
    sequences = params.get("sequences")
    variants: list[VariantOut] = []
    if labeled:
        for item in labeled:
            label = item.get("label")
            residues = item.get("residues")
            if not label or not residues:
                raise ValueError("each labeled entry requires 'label' and 'residues'")
            variants.append(
                VariantOut(label=str(label), residues=validate_residues(residues), mutations=[])
            )
    elif sequences:
        for i, seq in enumerate(sequences):
            variants.append(
                VariantOut(
                    label=f"variant_{i + 1}",
                    residues=validate_residues(seq),
                    mutations=[],
                )
            )
    else:
        raise ValueError("pasted requires 'sequences' or 'labeled'")
    return variants


# --- claude strategy -------------------------------------------------------
class _Mutation(BaseModel):
    pos: int
    from_aa: str
    to_aa: str


class _ProposedVariant(BaseModel):
    label: str
    mutations: list[_Mutation]


class _ClaudeVariants(BaseModel):
    variants: list[_ProposedVariant]


def _claude(base: str, params: dict[str, Any]) -> list[VariantOut]:
    import anthropic

    settings = get_settings()
    if not settings.anthropic_api_key:
        raise ValueError("claude strategy requires an Anthropic API key")

    n = params.get("n")
    if not isinstance(n, int) or n <= 0:
        raise ValueError("claude strategy requires a positive integer 'n'")
    rationale_prompt = params.get("rationale_prompt") or ""

    prompt = (
        "You are a protein engineer proposing point-mutation variants of a base "
        "sequence to test computationally.\n\n"
        f"Base sequence ({len(base)} residues, 1-indexed):\n{base}\n\n"
        f"Propose {n} distinct variants. Each variant is a list of point mutations. "
        "For every mutation give the 1-indexed position `pos`, the original amino "
        "acid `from_aa` (single letter, must match the base at that position), and "
        "the new amino acid `to_aa` (single letter, one of the 20 canonical amino "
        "acids). Give each variant a short descriptive `label`."
    )
    if rationale_prompt:
        prompt += f"\n\nAdditional guidance: {rationale_prompt}"

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.parse(
        model=settings.anthropic_model,
        max_tokens=2048,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        messages=[{"role": "user", "content": prompt}],
        output_format=_ClaudeVariants,
    )
    proposed = response.parsed_output
    if proposed is None:
        raise ValueError("claude strategy produced no parseable variants")

    variants: list[VariantOut] = []
    for pv in proposed.variants:
        try:
            residues, mutations = _apply_proposed_mutations(base, pv.mutations)
        except ValueError:
            # Skip invalid proposals (bad position, from_aa mismatch, non-AA).
            continue
        if not mutations:
            continue
        label = pv.label.strip() if pv.label and pv.label.strip() else "_".join(mutations)
        variants.append(VariantOut(label=label, residues=residues, mutations=mutations))
    return variants


def _apply_proposed_mutations(
    base: str, mutations: list[_Mutation]
) -> tuple[str, list[str]]:
    """Apply Claude-proposed mutations onto the base; verify + build labels."""
    chars = list(base)
    labels: list[str] = []
    for m in mutations:
        if not (1 <= m.pos <= len(chars)):
            raise ValueError(f"position {m.pos} out of range")
        wt = chars[m.pos - 1]
        if m.from_aa.strip().upper() != wt:
            raise ValueError(f"from_aa {m.from_aa!r} does not match base {wt!r} at {m.pos}")
        to_aa = _validate_aa(m.to_aa, context="claude proposal")
        chars[m.pos - 1] = to_aa
        labels.append(f"{wt}{m.pos}{to_aa}")
    return "".join(chars), labels
