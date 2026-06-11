"""Database engine + session dependency (FROZEN CONTRACT)."""
from __future__ import annotations

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from .config import get_settings

_settings = get_settings()
_connect_args = (
    {"check_same_thread": False} if _settings.db_url.startswith("sqlite") else {}
)
engine = create_engine(_settings.db_url, echo=False, connect_args=_connect_args)


def init_db() -> None:
    """Create tables. Importing models registers them on SQLModel.metadata."""
    from . import models  # noqa: F401  (side-effect: table registration)

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a DB session."""
    with Session(engine) as session:
        yield session
