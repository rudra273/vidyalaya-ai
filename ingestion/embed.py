"""Gemini embedding helpers for ingestion and query."""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types
from dotenv import load_dotenv


logger = logging.getLogger("ingestion")


@dataclass(frozen=True)
class EmbeddingConfig:
    """Settings for Gemini document embeddings."""

    model: str
    dimension: int
    batch_size: int = 32
    cache_path: Path | None = None
    request_delay_seconds: float = 2.0
    request_timeout_ms: int = 60_000
    retry_wait_seconds: tuple[int, ...] = (2, 5, 10, 20, 40, 60, 90, 120)


def load_gemini_api_key(env_path: Path | str = ".env") -> str:
    """Load the Gemini API key from the environment or local .env file."""
    load_dotenv(env_path)

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to .env or export it before running ingestion."
        )

    return api_key


def embed_chunks(
    chunks: list[dict[str, Any]],
    config: EmbeddingConfig,
    *,
    api_key: str | None = None,
) -> list[dict[str, Any]]:
    """Embed chunks with Gemini and return chunk/vector records."""
    if not chunks:
        return []

    api_key = api_key or load_gemini_api_key()
    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=config.request_timeout_ms),
    )
    cached_records = _load_cached_embeddings(config.cache_path)
    embedded_records: list[dict[str, Any]] = []

    for chunk in chunks:
        cached_record = cached_records.get(chunk["chunk_id"])
        if cached_record is not None:
            embedded_records.append(cached_record)

    chunks_to_embed = [chunk for chunk in chunks if chunk["chunk_id"] not in cached_records]
    logger.info("Embedding cache hits: %s", len(embedded_records))
    logger.info("Chunks left to embed: %s", len(chunks_to_embed))

    for pending_index, chunk in enumerate(chunks_to_embed, start=1):
        prepared_text = format_document_for_embedding(chunk)
        logger.info(
            "Embedding chunk %s/%s: %s page=%s chunk=%s",
            pending_index,
            len(chunks_to_embed),
            chunk["subject"],
            chunk["page_no"],
            chunk["chunk_id"],
        )
        vector = _embed_one_text_with_retry(
            prepared_text,
            client=client,
            model=config.model,
            dimension=config.dimension,
            retry_wait_seconds=config.retry_wait_seconds,
        )
        record = {
            "chunk_id": chunk["chunk_id"],
            "vector": vector,
            "payload": chunk,
        }
        _append_cached_embeddings(config.cache_path, [record])
        embedded_records.append(record)
        logger.info("Cached embedding: %s", chunk["chunk_id"])

        done_count = len(embedded_records)
        total_count = len(chunks)
        if done_count == total_count or done_count % config.batch_size == 0:
            logger.info("Embedded %s/%s chunks", done_count, total_count)

        if config.request_delay_seconds > 0:
            time.sleep(config.request_delay_seconds)

    return _order_records_by_chunks(embedded_records, chunks)


def embed_texts(
    texts: list[str],
    *,
    client: genai.Client,
    model: str,
    dimension: int,
) -> list[list[float]]:
    """Embed prepared text strings with Gemini."""
    if not texts:
        return []

    return [
        _embed_one_text(
            text,
            client=client,
            model=model,
            dimension=dimension,
        )
        for text in texts
    ]


def _embed_one_text(
    text: str,
    *,
    client: genai.Client,
    model: str,
    dimension: int,
) -> list[float]:
    """Embed one prepared text string and validate its vector size."""
    result = client.models.embed_content(
        model=model,
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=dimension),
    )

    embeddings = getattr(result, "embeddings", None)
    if embeddings is None:
        embedding = getattr(result, "embedding", None)
        embeddings = [embedding] if embedding is not None else []

    if not embeddings:
        raise ValueError("Gemini did not return an embedding")

    vector = _embedding_values(embeddings[0])
    if len(vector) != dimension:
        raise ValueError(f"Expected {dimension}-dim embedding, got {len(vector)}")

    return vector


def _embed_one_text_with_retry(
    text: str,
    *,
    client: genai.Client,
    model: str,
    dimension: int,
    retry_wait_seconds: tuple[int, ...],
) -> list[float]:
    """Embed one text string with backoff for rate limits."""
    for attempt in range(len(retry_wait_seconds) + 1):
        try:
            return _embed_one_text(
                text,
                client=client,
                model=model,
                dimension=dimension,
            )
        except Exception as exc:
            if not _is_rate_limit_error(exc) or attempt == len(retry_wait_seconds):
                logger.exception("Gemini embedding failed after retries")
                raise

            wait_seconds = retry_wait_seconds[attempt]
            logger.warning(
                "Gemini rate limit hit on attempt %s/%s. Waiting %ss before retry.",
                attempt + 1,
                len(retry_wait_seconds),
                wait_seconds,
            )
            time.sleep(wait_seconds)

    raise RuntimeError("Embedding retry loop ended unexpectedly")


def _is_rate_limit_error(exc: Exception) -> bool:
    """Return whether an exception looks like a Gemini rate limit error."""
    text = str(exc)
    return "429" in text or "RESOURCE_EXHAUSTED" in text


def format_document_for_embedding(chunk: dict[str, Any]) -> str:
    """Format a textbook chunk with retrieval context before embedding."""
    return "\n".join(
        [
            "task: question answering | document:",
            f"Board: {chunk['board']}",
            f"Class: {chunk['class']}",
            f"Subject: {chunk['subject']}",
            f"Book: {chunk['book_name']}",
            f"Page: {chunk['page_no']}",
            "",
            str(chunk["text"]),
        ]
    )


def _embedding_values(embedding: Any) -> list[float]:
    """Extract numeric values from a Gemini embedding response object."""
    values = getattr(embedding, "values", None)
    if values is None and isinstance(embedding, dict):
        values = embedding.get("values")
    if values is None:
        raise ValueError("Gemini embedding response did not contain values")

    return [float(value) for value in values]


def _load_cached_embeddings(cache_path: Path | None) -> dict[str, dict[str, Any]]:
    """Load cached embedding records keyed by chunk ID."""
    if cache_path is None or not cache_path.exists():
        return {}

    records: dict[str, dict[str, Any]] = {}
    with cache_path.open("r", encoding="utf-8") as file:
        for line_no, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue

            record = json.loads(line)
            chunk_id = record.get("chunk_id")
            vector = record.get("vector")
            if not chunk_id or not isinstance(vector, list):
                raise ValueError(f"Invalid embedding cache row at {cache_path}:{line_no}")
            records[chunk_id] = record

    return records


def _append_cached_embeddings(cache_path: Path | None, records: list[dict[str, Any]]) -> None:
    """Append newly embedded records to the local cache file."""
    if cache_path is None or not records:
        return

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("a", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def _order_records_by_chunks(
    records: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return embedding records in the same order as the chunk list."""
    records_by_id = {record["chunk_id"]: record for record in records}
    return [records_by_id[chunk["chunk_id"]] for chunk in chunks]
