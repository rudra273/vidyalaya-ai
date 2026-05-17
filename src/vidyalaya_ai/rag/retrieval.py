"""Retrieve textbook chunks from Qdrant."""

from __future__ import annotations

import logging
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

from vidyalaya_ai.rag.config import RagConfig
from vidyalaya_ai.rag.logging_config import setup_rag_logging
from vidyalaya_ai.rag.query_embedding import embed_query


logger = logging.getLogger("vidyalaya_ai.rag")


def retrieve_chunks(
    query: str,
    *,
    board: str,
    class_no: int,
    subject: str | None = None,
    top_k: int | None = None,
    config: RagConfig | None = None,
) -> list[dict[str, Any]]:
    """Embed a query and retrieve matching textbook chunks from Qdrant."""
    if not logger.handlers:
        setup_rag_logging()

    config = config or RagConfig()
    top_k = top_k or config.top_k
    query_vector = embed_query(query, config)
    client = QdrantClient(url=config.qdrant_url)
    query_filter = _build_filter(board=board, class_no=class_no, subject=subject)

    logger.info("Retrieval query: %s", query)
    logger.info("Filters: board=%s class=%s subject=%s top_k=%s", board, class_no, subject, top_k)

    results = client.query_points(
        collection_name=config.collection_name,
        query=query_vector,
        query_filter=query_filter,
        limit=top_k,
        with_payload=True,
    )

    chunks = [format_qdrant_point(point) for point in results.points]
    logger.info("Retrieved %s chunks", len(chunks))
    for chunk in chunks[:5]:
        logger.info(
            "score=%.4f subject=%s book=%s page=%s chunk=%s",
            chunk["score"],
            chunk["subject"],
            chunk["book_name"],
            chunk["page_no"],
            chunk["chunk_id"],
        )

    return chunks


def _build_filter(*, board: str, class_no: int, subject: str | None = None) -> Filter:
    """Build Qdrant metadata filter for textbook retrieval."""
    conditions = [
        FieldCondition(key="board", match=MatchValue(value=board)),
        FieldCondition(key="class", match=MatchValue(value=class_no)),
    ]
    if subject:
        conditions.append(FieldCondition(key="subject", match=MatchValue(value=subject)))

    return Filter(must=conditions)


def format_qdrant_point(point) -> dict[str, Any]:
    """Return a compact retrieval result from a Qdrant point."""
    payload = point.payload or {}
    return {
        "score": getattr(point, "score", None),
        "chunk_id": payload.get("chunk_id"),
        "board": payload.get("board"),
        "class": payload.get("class"),
        "subject": payload.get("subject"),
        "book_name": payload.get("book_name"),
        "book_id": payload.get("book_id"),
        "language": payload.get("language"),
        "source_pdf": payload.get("source_pdf"),
        "page_no": payload.get("page_no"),
        "chunk_index": payload.get("chunk_index"),
        "text": payload.get("text", ""),
    }
