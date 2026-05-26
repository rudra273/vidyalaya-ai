"""Retrieve textbook context for agents."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from vidyalaya_ai.rag.config import RagConfig
from vidyalaya_ai.rag.context import build_context_blocks
from vidyalaya_ai.rag.logging_config import setup_rag_logging
from vidyalaya_ai.rag.retrieval import retrieve_chunks


logger = logging.getLogger("vidyalaya_ai.rag")


@dataclass(frozen=True)
class TextbookRetrievalConfig:
    """Server-side tuning for the textbook retrieval tool."""

    top_k: int = 10
    context_blocks: int = 4
    neighbor_chunk_window: int = 1
    neighbor_page_window: int = 0
    max_context_chars: int = 6_000


def retrieve_textbook(
    query: str,
    board: str,
    class_no: int,
    subject: str | None = None,
    *,
    tool_config: TextbookRetrievalConfig | None = None,
    rag_config: RagConfig | None = None,
) -> dict[str, Any]:
    """Retrieve merged textbook context blocks for a student query."""
    if not logger.handlers:
        setup_rag_logging()

    cleaned_query = query.strip()
    cleaned_board = board.strip()
    cleaned_subject = subject.strip() if subject else None
    _validate_inputs(cleaned_query, cleaned_board, class_no)

    tool_config = tool_config or TextbookRetrievalConfig()
    rag_config = _build_rag_config(tool_config, rag_config)

    logger.info(
        "retrieve_textbook query=%s board=%s class=%s subject=%s top_k=%s context_blocks=%s",
        cleaned_query,
        cleaned_board,
        class_no,
        cleaned_subject,
        tool_config.top_k,
        tool_config.context_blocks,
    )

    raw_hits = retrieve_chunks(
        cleaned_query,
        board=cleaned_board,
        class_no=class_no,
        subject=cleaned_subject,
        top_k=tool_config.top_k,
        config=rag_config,
    )
    context_blocks = build_context_blocks(raw_hits, config=rag_config)
    metadata = _build_metadata(
        query=cleaned_query,
        board=cleaned_board,
        class_no=class_no,
        subject=cleaned_subject,
        raw_hits=raw_hits,
        context_blocks=context_blocks,
    )

    logger.info(
        "retrieve_textbook result top_score=%s subjects=%s pages=%s context_blocks=%s",
        metadata["top_score"],
        metadata["subjects_found"],
        metadata["pages_found"],
        metadata["context_block_count"],
    )

    return {
        "context_blocks": context_blocks,
        "raw_hits": [_compact_hit(hit) for hit in raw_hits],
        "metadata": metadata,
    }


def _build_rag_config(
    tool_config: TextbookRetrievalConfig,
    rag_config: RagConfig | None,
) -> RagConfig:
    """Copy base RAG config while applying tool-level retrieval tuning."""
    base_config = rag_config or RagConfig()
    return RagConfig(
        qdrant_url=base_config.qdrant_url,
        qdrant_api_key=base_config.qdrant_api_key,
        collection_name=base_config.collection_name,
        embedding_model=base_config.embedding_model,
        embedding_dim=base_config.embedding_dim,
        top_k=tool_config.top_k,
        request_timeout_ms=base_config.request_timeout_ms,
        final_context_blocks=tool_config.context_blocks,
        neighbor_chunk_window=tool_config.neighbor_chunk_window,
        neighbor_page_window=tool_config.neighbor_page_window,
        max_context_chars=tool_config.max_context_chars,
        dedupe_context_chunks=base_config.dedupe_context_chunks,
        min_context_score=base_config.min_context_score,
        max_answer_context_chars=base_config.max_answer_context_chars,
    )


def _validate_inputs(query: str, board: str, class_no: int) -> None:
    """Validate required client/API inputs."""
    if not query:
        raise ValueError("query cannot be empty.")
    if not board:
        raise ValueError("board cannot be empty.")
    if class_no <= 0:
        raise ValueError("class_no must be a positive integer.")


def _build_metadata(
    *,
    query: str,
    board: str,
    class_no: int,
    subject: str | None,
    raw_hits: list[dict[str, Any]],
    context_blocks: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build summary metadata for retrieved textbook context."""
    subjects_found = sorted({str(hit["subject"]) for hit in raw_hits if hit.get("subject")})
    pages_found = _sorted_pages(hit.get("page_no") for hit in raw_hits)
    top_score = raw_hits[0].get("score") if raw_hits else None

    return {
        "query": query,
        "board": board,
        "class_no": class_no,
        "subject_filter": subject,
        "subjects_found": subjects_found,
        "pages_found": pages_found,
        "top_score": top_score,
        "context_block_count": len(context_blocks),
    }


def _compact_hit(hit: dict[str, Any]) -> dict[str, Any]:
    """Return raw hit metadata without full text."""
    return {
        "score": hit.get("score"),
        "board": hit.get("board"),
        "class": hit.get("class"),
        "subject": hit.get("subject"),
        "book_name": hit.get("book_name"),
        "book_id": hit.get("book_id"),
        "language": hit.get("language"),
        "source_pdf": hit.get("source_pdf"),
        "page_no": hit.get("page_no"),
        "chunk_id": hit.get("chunk_id"),
        "chunk_index": hit.get("chunk_index"),
    }


def _sorted_pages(values) -> list[int]:
    """Return sorted page numbers from scalar or list page values."""
    pages: set[int] = set()
    for value in values:
        if isinstance(value, list):
            pages.update(int(item) for item in value)
        elif value is not None:
            pages.add(int(value))

    return sorted(pages)
