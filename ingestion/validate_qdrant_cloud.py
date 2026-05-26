"""Validate Qdrant Cloud connection from local .env values."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from qdrant_client import QdrantClient


COLLECTION_NAME = "vidyalaya_textbook_chunks"


def main() -> None:
    """Connect to Qdrant and print a safe connection summary."""
    load_dotenv()
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")

    if not qdrant_url:
        raise RuntimeError("QDRANT_URL is not set in .env.")
    if not qdrant_api_key:
        raise RuntimeError("QDRANT_API_KEY is not set in .env.")

    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
    collections = client.get_collections().collections
    collection_names = sorted(collection.name for collection in collections)

    print("Qdrant connection: ok")
    print(f"Collections found: {len(collection_names)}")
    print(f"Target collection exists: {COLLECTION_NAME in collection_names}")

    if COLLECTION_NAME in collection_names:
        count = client.count(collection_name=COLLECTION_NAME, exact=True).count
        print(f"Target collection count: {count}")


if __name__ == "__main__":
    main()
