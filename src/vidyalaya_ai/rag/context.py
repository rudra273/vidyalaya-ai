"""Merge and expand retrieved chunks into final context blocks."""

from __future__ import annotations

import logging
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue

from vidyalaya_ai.rag.config import RagConfig
from vidyalaya_ai.rag.logging_config import setup_rag_logging
from vidyalaya_ai.rag.retrieval import format_qdrant_point


logger = logging.getLogger("vidyalaya_ai.rag")


def build_context_blocks(
    hits: list[dict[str, Any]],
    *,
    config: RagConfig | None = None,
) -> list[dict[str, Any]]:
    """Expand top retrieval hits and return merged context blocks."""
    if not logger.handlers:
        setup_rag_logging()

    config = config or RagConfig()
    client = QdrantClient(url=config.qdrant_url)
    blocks: list[dict[str, Any]] = []
    seen_groups: set[tuple[str, int]] = set()
    seen_chunk_ids: set[str] = set()

    for hit in hits:
        if len(blocks) >= config.final_context_blocks:
            break

        if config.dedupe_context_chunks and hit["chunk_id"] in seen_chunk_ids:
            continue

        group_key = (str(hit["book_id"]), int(hit["page_no"]))
        if group_key in seen_groups:
            continue
        seen_groups.add(group_key)

        expanded_chunks = fetch_neighbor_chunks(client, hit, config=config)
        if not expanded_chunks:
            expanded_chunks = [hit]

        block = merge_chunks_into_context_block(hit, expanded_chunks, config=config)
        blocks.append(block)
        seen_chunk_ids.update(block["chunk_ids"])

    logger.info("Built %s final context blocks", len(blocks))
    for block in blocks:
        logger.info(
            "context score=%.4f book=%s pages=%s chunks=%s chars=%s",
            block["score"],
            block["book_name"],
            block["page_no"],
            len(block["chunk_ids"]),
            len(block["text"]),
        )

    return blocks


def fetch_neighbor_chunks(
    client: QdrantClient,
    hit: dict[str, Any],
    *,
    config: RagConfig,
) -> list[dict[str, Any]]:
    """Fetch neighboring chunks around a retrieved hit."""
    page_no = int(hit["page_no"])
    chunk_index = int(hit["chunk_index"])
    page_numbers = _window_values(page_no, config.neighbor_page_window, minimum=1)
    chunk_indexes = _window_values(chunk_index, config.neighbor_chunk_window, minimum=1)

    scroll_filter = Filter(
        must=[
            FieldCondition(key="board", match=MatchValue(value=hit["board"])),
            FieldCondition(key="class", match=MatchValue(value=hit["class"])),
            FieldCondition(key="subject", match=MatchValue(value=hit["subject"])),
            FieldCondition(key="book_id", match=MatchValue(value=hit["book_id"])),
            FieldCondition(key="page_no", match=MatchAny(any=page_numbers)),
            FieldCondition(key="chunk_index", match=MatchAny(any=chunk_indexes)),
        ]
    )

    points, _ = client.scroll(
        collection_name=config.collection_name,
        scroll_filter=scroll_filter,
        limit=50,
        with_payload=True,
        with_vectors=False,
    )

    chunks = [format_qdrant_point(point) for point in points]
    return sorted(chunks, key=lambda item: (item["page_no"], item["chunk_index"]))


def merge_chunks_into_context_block(
    hit: dict[str, Any],
    chunks: list[dict[str, Any]],
    *,
    config: RagConfig,
) -> dict[str, Any]:
    """Merge expanded chunks into one context block with citation metadata."""
    ordered_chunks = sorted(chunks, key=lambda item: (item["page_no"], item["chunk_index"]))
    text = "\n\n".join(str(chunk["text"]).strip() for chunk in ordered_chunks if chunk.get("text"))
    if len(text) > config.max_context_chars:
        text = text[: config.max_context_chars].rstrip()

    page_numbers = sorted({int(chunk["page_no"]) for chunk in ordered_chunks})
    return {
        "score": hit["score"],
        "board": hit["board"],
        "class": hit["class"],
        "subject": hit["subject"],
        "book_name": hit["book_name"],
        "book_id": hit["book_id"],
        "language": hit["language"],
        "source_pdf": hit["source_pdf"],
        "page_no": page_numbers[0] if len(page_numbers) == 1 else page_numbers,
        "chunk_ids": [chunk["chunk_id"] for chunk in ordered_chunks],
        "text": text,
    }


def _window_values(value: int, window: int, *, minimum: int) -> list[int]:
    """Return integer values around a center value."""
    start = max(minimum, value - window)
    end = value + window
    return list(range(start, end + 1))
