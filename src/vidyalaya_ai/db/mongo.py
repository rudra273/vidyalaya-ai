"""Async MongoDB client lifecycle and indexes."""

from __future__ import annotations

import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING

from vidyalaya_ai.db.config import has_mongo_config, load_mongo_config


logger = logging.getLogger("vidyalaya_ai.api")
_client: AsyncIOMotorClient | None = None


def get_mongo_client() -> AsyncIOMotorClient:
    """Return a process-wide Motor client."""
    global _client
    if _client is None:
        config = load_mongo_config()
        _client = AsyncIOMotorClient(config.uri)
    return _client


def get_db() -> AsyncIOMotorDatabase:
    """Return the configured MongoDB database."""
    config = load_mongo_config()
    return get_mongo_client()[config.db_name]


async def ensure_indexes() -> None:
    """Create MongoDB indexes used by the app."""
    if not has_mongo_config():
        logger.warning("MONGODB_URI is not set; skipping Mongo index setup")
        return

    db = get_db()
    await db.command("ping")
    await db.users.create_index([("firebase_uid", ASCENDING)], unique=True)
    await db.users.create_index(
        [("email", ASCENDING)],
        unique=True,
        sparse=True,
    )
    await db.student_profiles.create_index([("user_id", ASCENDING)], unique=True)
    await db.student_profiles.create_index([("firebase_uid", ASCENDING)], unique=True)
    await db.daily_usage.create_index(
        [("firebase_uid", ASCENDING), ("date_ist", ASCENDING), ("agent", ASCENDING)],
        unique=True,
    )
    await db.daily_usage.create_index(
        [("first_at", ASCENDING)],
        expireAfterSeconds=35 * 24 * 60 * 60,
    )
    logger.info("Mongo connected, indexes ensured")


async def close_mongo_client() -> None:
    """Close the process-wide Motor client."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
        logger.info("Mongo client closed")
