"""Qdrant collection and point storage helpers."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PayloadSchemaType, PointStruct, VectorParams


logger = logging.getLogger("ingestion")
POINT_ID_NAMESPACE = uuid.UUID("f75f2f86-8e9d-4c7b-94c3-7b70a4a676f1")
FILTER_INDEXES = {
    "board": PayloadSchemaType.KEYWORD,
    "class": PayloadSchemaType.INTEGER,
    "subject": PayloadSchemaType.KEYWORD,
    "book_id": PayloadSchemaType.KEYWORD,
    "page_no": PayloadSchemaType.INTEGER,
    "chunk_index": PayloadSchemaType.INTEGER,
}


def make_qdrant_client(
    qdrant_url: str,
    qdrant_api_key: str | None = None,
    *,
    timeout: int = 120,
) -> QdrantClient:
    """Create a Qdrant client for local or cloud Qdrant."""
    return QdrantClient(url=qdrant_url, api_key=qdrant_api_key, timeout=timeout)


def ensure_collection(
    client: QdrantClient,
    *,
    collection_name: str,
    vector_size: int,
) -> None:
    """Create or validate the Qdrant collection and common payload indexes."""
    if not client.collection_exists(collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
        logger.info("Created Qdrant collection: %s", collection_name)
    else:
        _validate_collection_vector_size(client, collection_name, vector_size)
        logger.info("Qdrant collection already exists: %s", collection_name)

    _ensure_payload_indexes(client, collection_name)


def upsert_embedded_chunks(
    client: QdrantClient,
    *,
    collection_name: str,
    embedded_records: list[dict[str, Any]],
    batch_size: int = 64,
    retry_wait_seconds: tuple[int, ...] = (2, 5, 10, 20, 40),
) -> int:
    """Upsert embedded chunks into Qdrant and return inserted point count."""
    inserted_count = 0

    for start in range(0, len(embedded_records), batch_size):
        batch = embedded_records[start : start + batch_size]
        points = [
            PointStruct(
                id=deterministic_point_id(record["chunk_id"]),
                vector=record["vector"],
                payload=record["payload"],
            )
            for record in batch
        ]

        _upsert_points_with_retry(
            client,
            collection_name=collection_name,
            points=points,
            retry_wait_seconds=retry_wait_seconds,
        )

        inserted_count += len(points)
        logger.info("Upserted %s/%s points", inserted_count, len(embedded_records))

    return inserted_count


def _upsert_points_with_retry(
    client: QdrantClient,
    *,
    collection_name: str,
    points: list[PointStruct],
    retry_wait_seconds: tuple[int, ...],
) -> None:
    """Upsert points with retry for transient cloud/network failures."""
    for attempt in range(len(retry_wait_seconds) + 1):
        try:
            client.upsert(
                collection_name=collection_name,
                points=points,
                wait=True,
            )
            return
        except Exception:
            if attempt == len(retry_wait_seconds):
                logger.exception("Qdrant upsert failed after retries")
                raise

            wait_seconds = retry_wait_seconds[attempt]
            logger.warning(
                "Qdrant upsert failed on attempt %s/%s. Waiting %ss before retry.",
                attempt + 1,
                len(retry_wait_seconds) + 1,
                wait_seconds,
            )
            time.sleep(wait_seconds)


def deterministic_point_id(chunk_id: str) -> str:
    """Create a stable Qdrant point ID from a chunk ID."""
    return str(uuid.uuid5(POINT_ID_NAMESPACE, chunk_id))


def _ensure_payload_indexes(client: QdrantClient, collection_name: str) -> None:
    """Create indexes for fields used in filters."""
    for field_name, field_schema in FILTER_INDEXES.items():
        try:
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=field_schema,
                wait=True,
            )
            logger.info("Ensured payload index: %s", field_name)
        except Exception as exc:
            if "already exists" not in str(exc).lower():
                raise
            logger.info("Payload index already exists: %s", field_name)


def _validate_collection_vector_size(
    client: QdrantClient,
    collection_name: str,
    expected_vector_size: int,
) -> None:
    """Validate that an existing collection matches the configured vector size."""
    collection = client.get_collection(collection_name)
    vectors = collection.config.params.vectors
    actual_vector_size = getattr(vectors, "size", None)

    if actual_vector_size != expected_vector_size:
        raise ValueError(
            f"Collection {collection_name} has vector size {actual_vector_size}, "
            f"but config expects {expected_vector_size}."
        )
