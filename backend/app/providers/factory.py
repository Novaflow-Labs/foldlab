"""Provider selection. `get_provider()` returns a cached singleton.

The Rowan import is lazy so the app runs with FOLDING_PROVIDER=mock even before
rowan_provider.py exists. Agent A adds RowanProvider; this file otherwise stands.
"""
from __future__ import annotations

from functools import lru_cache

from ..config import get_settings
from .base import FoldingProvider


@lru_cache
def get_provider() -> FoldingProvider:
    name = (get_settings().folding_provider or "mock").strip().lower()
    if name == "rowan":
        from .rowan_provider import RowanProvider  # lazy: created by Agent A

        return RowanProvider()
    from .mock_provider import MockProvider

    return MockProvider()
