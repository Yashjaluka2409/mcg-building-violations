"""Alembic environment: async engine from the application settings, model metadata from app.models."""
from __future__ import annotations

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import async_url, make_engine  # noqa: E402
from app.models import building_violations  # noqa: E402,F401  (registers every table)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=async_url(settings.sqlalchemy_url), target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"},
                      render_as_batch=True, compare_type=True, render_item=_render_item)
    with context.begin_transaction():
        context.run_migrations()


def _render_item(type_, obj, autogen_context):
    """Render the module's UTCDateTime as a plain timezone-aware DateTime so migrations do not import app code."""
    if type_ == "type" and obj.__class__.__name__ == "UTCDateTime":
        return "sa.DateTime(timezone=True)"
    return False


def _do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=connection.dialect.name == "sqlite", compare_type=True, render_item=_render_item)
    with context.begin_transaction():
        context.run_migrations()


async def _run_async() -> None:
    engine = make_engine(settings.sqlalchemy_url)
    async with engine.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(_run_async())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
