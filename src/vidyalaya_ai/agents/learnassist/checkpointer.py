"""Checkpointer for the LearnAssist agent.

Uses Postgres when configured so conversation memory persists across requests and
process restarts, falling back to an in-memory saver for local/dev/tests.

``langgraph-checkpoint-postgres`` ships ``AsyncPostgresSaver``, which is
interface-compatible with the old ``MongoDBSaver`` — no graph code changes. It is
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

# AsyncPostgresSaver requires autocommit connections (it manages its own
# transactions) and uses prepared statements. prepare_threshold=0 keeps it
# compatible if you ever route through a pooler; a direct/session connection
# supports prepares fine.
_CONNECTION_KWARGS = {"autocommit": True, "prepare_threshold": 0}


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
        logger.warning("DATABASE_URL not set; LearnAssist using in-memory checkpoints")
        _checkpointer = InMemorySaver()
        return _checkpointer

    config = load_postgres_config()
    _pool = AsyncConnectionPool(
        conninfo=config.psycopg_url,
        max_size=10,
        open=False,
        kwargs=_CONNECTION_KWARGS,
    )
    await _pool.open(wait=True)
    saver = AsyncPostgresSaver(_pool)
    await saver.setup()
    _checkpointer = saver
    logger.info("LearnAssist using AsyncPostgresSaver checkpointer")
    return _checkpointer


def get_checkpointer() -> Any:
    """Return the already-initialized checkpointer.

    ``initialize_checkpointer`` must have run first (app lifespan startup). This
    synchronous accessor lets the agent be compiled lazily without awaiting.
    """
    if _checkpointer is None:
        raise RuntimeError(
            "Checkpointer not initialized; call initialize_checkpointer() at startup."
        )
    return _checkpointer


async def close_checkpointer() -> None:
    """Close the async pool used by the checkpointer."""
    global _pool, _checkpointer
    if _pool is not None:
        await _pool.close()
        _pool = None
    _checkpointer = None
