"""Shared checkpointer for all agents.

Uses Postgres when configured so conversation memory persists across requests and
process restarts, falling back to an in-memory saver for local/dev/tests.

``langgraph-checkpoint-postgres`` ships ``AsyncPostgresSaver``, which is
genuinely async (psycopg3 + an async pool), so checkpoint I/O stays off the event
loop under ``ainvoke``. Its tables are created once via ``await saver.setup()``,
invoked from the app lifespan at startup (see ``initialize_checkpointer``).
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from vidyalaya_ai.db.config import has_postgres_config, load_postgres_config


logger = logging.getLogger("vidyalaya_ai.agents")

_pool: AsyncConnectionPool | None = None
_checkpointer: Any | None = None

# Connection kwargs for every pooled checkpointer connection:
# - autocommit: AsyncPostgresSaver manages its own transactions.
# - prepare_threshold=0: stay compatible if routed through a pooler.
# - connect_timeout: fail fast instead of hanging if the DB is unreachable.
# - keepalives: ask the OS to probe idle TCP sockets so a connection silently
#   dropped by Supabase's pooler/NAT is detected quickly rather than hanging
#   until a multi-minute SSL syscall timeout on the next request.
_CONNECTION_KWARGS = {
    "autocommit": True,
    "prepare_threshold": 0,
    "connect_timeout": 10,
    "keepalives": 1,
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 3,
}


async def initialize_checkpointer() -> Any:
    """Create (once) and return the process-wide checkpointer.

    Called from the app lifespan startup. When ``DATABASE_URL`` is configured,
    opens an async psycopg pool, builds an ``AsyncPostgresSaver``, and runs its
    one-time ``setup()`` to ensure the checkpoint tables exist. Without config it
    falls back to an in-memory saver (dev/tests).
    """
    global _pool, _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    if not has_postgres_config():
        logger.warning("DATABASE_URL not set; agents using in-memory checkpoints")
        _checkpointer = InMemorySaver()
        return _checkpointer

    config = load_postgres_config()
    _pool = AsyncConnectionPool(
        conninfo=config.psycopg_url,
        min_size=1,
        max_size=10,
        open=False,
        kwargs=_CONNECTION_KWARGS,
        # Validate a connection before handing it out: a stale/dead connection
        # (reaped by the pooler while idle) is transparently discarded and
        # replaced instead of surfacing as a 500 on the next chat request.
        check=AsyncConnectionPool.check_connection,
        # Recycle connections proactively so they rotate out before the upstream
        # pooler kills them for being idle.
        max_idle=120.0,
        max_lifetime=1800.0,
    )
    await _pool.open(wait=True)
    saver = AsyncPostgresSaver(_pool)
    await saver.setup()
    _checkpointer = saver
    logger.info("Agents using AsyncPostgresSaver checkpointer")
    return _checkpointer


def get_checkpointer() -> Any:
    """Return the already-initialized checkpointer.

    ``initialize_checkpointer`` must have run first (app lifespan startup). This
    synchronous accessor lets agents be compiled lazily without awaiting.
    """
    if _checkpointer is None:
        raise RuntimeError(
            "Checkpointer not initialized; call initialize_checkpointer() at startup."
        )
    return _checkpointer


async def reset_thread_checkpoint(thread_id: str) -> None:
    """Delete all LangGraph checkpoint state for this thread.

    Uses the checkpointer's built-in ``adelete_thread``. Works for both
    ``AsyncPostgresSaver`` (Postgres) and ``InMemorySaver`` (dev). The
    permanent ``messages`` table is never touched.
    """
    checkpointer = get_checkpointer()
    await checkpointer.adelete_thread(thread_id)
    logger.info("Checkpoint reset for thread=%s", thread_id)


async def close_checkpointer() -> None:
    """Close the async pool used by the checkpointer."""
    global _pool, _checkpointer
    if _pool is not None:
        await _pool.close()
        _pool = None
    _checkpointer = None
