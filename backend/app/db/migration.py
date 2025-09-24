from __future__ import annotations

from pathlib import Path
from typing import Iterable

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.core.config import settings


def _candidate_roots(start: Path) -> Iterable[Path]:
    """Yield potential project roots to look for Alembic configuration files."""

    current = start.resolve()
    for candidate in (current, *current.parents):
        yield candidate


def _find_project_root() -> Path:
    """Locate the directory containing the Alembic configuration.

    The backend can run both from the monorepo (where Alembic lives at the
    repository root) and from the Docker image (where it is copied next to the
    backend sources). Walking the parents allows us to support both layouts.
    """

    for candidate in _candidate_roots(Path(__file__).parent):
        if (candidate / "alembic.ini").exists():
            return candidate

    raise RuntimeError("Unable to locate alembic.ini. Ensure it is bundled with the backend.")


def run_migrations() -> None:
    """Apply the latest Alembic migrations to the configured database."""

    project_root = _find_project_root()
    config = Config(str(project_root / "alembic.ini"))
    config.set_main_option("script_location", str(project_root / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url)

    connect_args = (
        {"check_same_thread": False}
        if settings.database_url.startswith("sqlite")
        else {}
    )
    engine = create_engine(settings.database_url, connect_args=connect_args)

    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            has_alembic_version = inspector.has_table("alembic_version")
            has_legacy_transactions = inspector.has_table("transactions")

        if not has_alembic_version and has_legacy_transactions:
            command.stamp(config, "0001")
    finally:
        engine.dispose()

    command.upgrade(config, "head")
