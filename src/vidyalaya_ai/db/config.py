"""MongoDB configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


@dataclass(frozen=True)
class MongoConfig:
    """Runtime MongoDB connection settings."""

    uri: str
    db_name: str = "vidyalaya_ai"


@lru_cache(maxsize=1)
def load_mongo_config() -> MongoConfig:
    """Load MongoDB config from environment variables."""
    load_dotenv()
    uri = os.getenv("MONGODB_URI", "").strip()
    if not uri:
        raise RuntimeError("MONGODB_URI is required for MongoDB-backed routes.")

    return MongoConfig(
        uri=uri,
        db_name=os.getenv("MONGODB_DB_NAME", "vidyalaya_ai").strip() or "vidyalaya_ai",
    )


def has_mongo_config() -> bool:
    """Return whether MongoDB has enough config to connect."""
    load_dotenv()
    return bool(os.getenv("MONGODB_URI", "").strip())
