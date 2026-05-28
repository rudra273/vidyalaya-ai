"""MongoDB access helpers."""

from vidyalaya_ai.db.mongo import close_mongo_client, ensure_indexes, get_db


__all__ = ["close_mongo_client", "ensure_indexes", "get_db"]
