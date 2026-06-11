"""On-disk structure storage (PDB/mmCIF bytes).

FROZEN SIGNATURES — Agent A (Phase 1A) implements the bodies. Files live under
settings.structure_dir, named by provider_job_id. Only the path is stored in the DB.
"""
from __future__ import annotations

from pathlib import Path

from ..config import get_settings

# Normalized structure format -> on-disk file extension.
_EXT_BY_FORMAT: dict[str, str] = {"pdb": "pdb", "mmcif": "cif"}


def _structure_dir() -> Path:
    """Resolve (and create) the directory structures are stored in."""
    directory = Path(get_settings().structure_dir)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def structure_path_for(provider_job_id: str, fmt: str) -> str:
    """Absolute/relative path where a structure for this job would be stored."""
    ext = _EXT_BY_FORMAT.get(fmt, fmt)
    return str(_structure_dir() / f"{provider_job_id}.{ext}")


def save_structure(provider_job_id: str, data: bytes, fmt: str) -> str:
    """Write bytes to disk (creating the dir if needed) and return the path."""
    path = structure_path_for(provider_job_id, fmt)
    Path(path).write_bytes(data)
    return path


def read_structure(path: str) -> bytes:
    """Read structure bytes from disk."""
    return Path(path).read_bytes()
