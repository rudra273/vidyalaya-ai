"""Checkpointer for the LearnAssist agent.

Uses MongoDB when configured so conversation memory persists across requests and
process restarts, falling back to an in-memory saver for local/dev/tests.

``langgraph-checkpoint-mongodb`` ships only the sync ``MongoDBSaver``; its async
methods wrap the sync pymongo client with ``run_in_executor``, so calling the
agent with ``ainvoke`` keeps checkpoint I/O off the event loop. We therefore use
a dedicated sync pymongo client here (separate from the app's motor client).
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.mongodb import MongoDBSaver
from pymongo import MongoClient

from vidyalaya_ai.db.config import has_mongo_config, load_mongo_config


logger = logging.getLogger("vidyalaya_ai.agents")
_sync_client: MongoClient | None = None


@lru_cache(maxsize=1)
def get_checkpointer() -> Any:
    """Return the process-wide checkpointer, preferring MongoDB."""
    global _sync_client
    if has_mongo_config():
        config = load_mongo_config()
        _sync_client = MongoClient(config.uri)
        logger.info("LearnAssist using MongoDBSaver checkpointer")
        return MongoDBSaver(
            _sync_client,
            db_name=config.db_name,
            checkpoint_collection_name="checkpoints",
            writes_collection_name="checkpoint_writes",
        )

    logger.warning("MONGODB_URI not set; LearnAssist using in-memory checkpoints")
    return InMemorySaver()


def close_checkpointer() -> None:
    """Close the sync client used by the checkpointer."""
    global _sync_client
    if _sync_client is not None:
        _sync_client.close()
        _sync_client = None
    get_checkpointer.cache_clear()
