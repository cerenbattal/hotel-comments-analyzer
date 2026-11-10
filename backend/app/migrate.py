"""Bring the database schema up to date with Alembic.

Run it from the command line with `alembic upgrade head` (inside backend/), or
let the API do it on startup (see main.py).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

BACKEND_DIR = Path(__file__).resolve().parent.parent
INITIAL_REVISION = "0001"


def alembic_config(database_url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.attributes["database_url"] = database_url
    return cfg


async def _table_names(database_url: str) -> set[str]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            return set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
    finally:
        await engine.dispose()


def upgrade(database_url: str) -> None:
    """Blocking; call it from a thread when an event loop is already running."""
    cfg = alembic_config(database_url)
    tables = asyncio.run(_table_names(database_url))
    if "reports" in tables and "alembic_version" not in tables:
        # Database created before migrations existed: its schema matches the
        # first revision, so mark it as such instead of re-creating tables.
        command.stamp(cfg, INITIAL_REVISION)
    command.upgrade(cfg, "head")
