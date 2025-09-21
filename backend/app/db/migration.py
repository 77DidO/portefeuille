from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.core.config import settings


def run_migrations() -> None:
    """Apply the latest Alembic migrations to the configured database."""

    project_root = Path(__file__).resolve().parents[3]
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
