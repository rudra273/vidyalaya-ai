"""Async SQLAlchemy engine + session lifecycle.

A single process-wide async engine (asyncpg driver) backs all app tables. The
repositories and services open short-lived sessions via ``session_scope()``.

For dev convenience we ``create_all`` the ORM metadata on startup
(``ensure_schema``); migration discipline (Alembic) is adopted only as we
approach production.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from vidyalaya_ai.db.base import Base
from vidyalaya_ai.db.config import has_postgres_config, load_postgres_config

# Import models so they register on Base.metadata before create_all runs.
from vidyalaya_ai.db import models as _models  # noqa: F401


logger = logging.getLogger("vidyalaya_ai.api")

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return the process-wide async engine, creating it on first use."""
    global _engine
    if _engine is None:
        config = load_postgres_config()
        _engine = create_async_engine(
            config.sqlalchemy_url,
            pool_pre_ping=True,
            future=True,
        )
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return the process-wide async session factory."""
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return _sessionmaker


def session_scope() -> AsyncSession:
    """Return a new async session.

    Use as an async context manager::

        async with session_scope() as session:
            ...
    """
    return get_sessionmaker()()


async def ensure_schema() -> None:
    """Create app tables if missing (dev convenience).

    Failures here are logged but do not crash startup: a transient DB hiccup at
    boot should not kill the deploy. The first request will surface a clear error
    if Postgres is genuinely unreachable.
    """
    if not has_postgres_config():
        logger.warning("DATABASE_URL is not set; skipping Postgres schema setup")
        return

    try:
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Postgres connected, app tables ensured")
    except Exception:
        logger.exception("Failed to ensure Postgres schema at startup; continuing")


async def close_engine() -> None:
    """Dispose the process-wide async engine."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _sessionmaker = None
        logger.info("Postgres engine disposed")
