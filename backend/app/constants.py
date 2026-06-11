"""Shared constants and enums (FROZEN CONTRACT — Phase-1 agents import, never edit)."""
from __future__ import annotations

from enum import Enum

# Canonical 20 amino acids (single-letter).
AMINO_ACIDS: frozenset[str] = frozenset("ACDEFGHIKLMNPQRSTVWY")


class JobState(str, Enum):
    """Normalized folding-job state used across the app (provider-agnostic)."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


TERMINAL_STATES: frozenset[JobState] = frozenset(
    {JobState.COMPLETED, JobState.FAILED, JobState.STOPPED}
)

# Folding models exposed in the UI. RowanProvider validates these against
# rowan.CofoldingModel at startup; treat this tuple as the canonical UI list.
FOLD_MODELS: tuple[str, ...] = ("boltz_2", "boltz_1", "chai_1r")
DEFAULT_FOLD_MODEL = "boltz_2"

# Rowan status enum name -> normalized JobState. Anything NOT in this map is
# treated as in-flight (RUNNING) by the provider (Rowan has no literal RUNNING).
ROWAN_STATUS_MAP: dict[str, JobState] = {
    "QUEUED": JobState.QUEUED,
    "DRAFT": JobState.QUEUED,
    "COMPLETED_OK": JobState.COMPLETED,
    "FAILED": JobState.FAILED,
    "STOPPED": JobState.STOPPED,
}

# Allowed enum-ish string values used in schemas.
DIRECTIVE_KINDS: tuple[str, ...] = ("color", "label", "representation", "focus", "select")
REPRESENTATIONS: tuple[str, ...] = ("cartoon", "ball-and-stick", "surface", "spacefill")
SEQUENCE_KINDS: tuple[str, ...] = ("protein", "antigen", "partner")
VARIANT_STRATEGIES: tuple[str, ...] = ("positions_subs", "alanine_scan", "claude", "pasted")
