"""Anthropic client factory for the NL layer.

The real client is read SERVER-SIDE from settings (config.Settings.anthropic_api_key).
An empty key is treated as "missing" (same convention as the providers) and raises a
clear error so the loop can surface a friendly `error` SSE event instead of crashing.

Tests never call this — they inject a fake client into `run_chat(..., client=...)`.
"""
from __future__ import annotations

from functools import lru_cache

import anthropic

from ..config import get_settings


class MissingAPIKeyError(RuntimeError):
    """Raised when no ANTHROPIC_API_KEY is configured."""


@lru_cache
def get_anthropic_client() -> anthropic.Anthropic:
    """Return a cached Anthropic client, or raise MissingAPIKeyError if no key is set."""
    api_key = get_settings().anthropic_api_key
    if not api_key:
        raise MissingAPIKeyError(
            "ANTHROPIC_API_KEY is required for the chat endpoint but is not configured."
        )
    return anthropic.Anthropic(api_key=api_key)
