"""Application settings. API keys are read here SERVER-SIDE only."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Secrets (empty string is treated as "missing" by the factory/providers).
    rowan_api_key: str = ""
    anthropic_api_key: str = ""

    # Provider selection: "mock" (default, zero-cost) or "rowan".
    folding_provider: str = "mock"

    anthropic_model: str = "claude-opus-4-8"
    default_fold_model: str = "boltz_2"

    db_url: str = "sqlite:///./protein_demo.db"
    structure_dir: str = "./app/data/structures"

    # Optional per-job Rowan credit cap.
    max_credits: int | None = None

    # Background poller cadence (seconds).
    poll_interval_seconds: float = 5.0

    # Allowed CORS origins for a deployed frontend (dev uses the Vite proxy).
    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
