"""Chunk OCR JSONL pages into retrieval-ready text blocks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ChunkConfig:
    """Settings for page-aware textbook chunking."""

    target_size: int = 2200
    max_size: int = 3000
    overlap_size: int = 350
    min_size: int = 350


def chunk_pages(
    pages: list[dict[str, Any]],
    config: ChunkConfig | None = None,
) -> list[dict[str, Any]]:
    """Create retrieval chunks from OCR pages without crossing page boundaries."""
    config = config or ChunkConfig()
    chunks: list[dict[str, Any]] = []

    for page in pages:
        page_chunks = _chunk_one_page(page, config)
        chunks.extend(page_chunks)

    return chunks


def _chunk_one_page(page: dict[str, Any], config: ChunkConfig) -> list[dict[str, Any]]:
    """Chunk a single OCR page and attach deterministic chunk metadata."""
    text = str(page["text"]).strip()
    if not text:
        return []

    blocks = _split_text_blocks(text)
    chunk_texts = _pack_blocks(blocks, config)
    chunk_texts = _merge_small_tail_chunks(chunk_texts, config)

    page_chunks: list[dict[str, Any]] = []
    for chunk_index, chunk_text in enumerate(chunk_texts, start=1):
        chunk = {
            "chunk_id": _build_chunk_id(page, chunk_index),
            "board": page["board"],
            "class": page["class"],
            "subject": page["subject"],
            "book_name": page["book_name"],
            "book_id": page["book_id"],
            "language": page["language"],
            "source_pdf": page["source_pdf"],
            "page_no": page["page_no"],
            "chunk_index": chunk_index,
            "text": chunk_text,
        }
        page_chunks.append(chunk)

    return page_chunks


def _split_text_blocks(text: str) -> list[str]:
    """Split OCR text into paragraph or line blocks."""
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", text) if part.strip()]

    if len(paragraphs) > 1:
        return paragraphs

    return [line.strip() for line in text.splitlines() if line.strip()]


def _pack_blocks(blocks: list[str], config: ChunkConfig) -> list[str]:
    """Pack text blocks into chunks using overlap between neighboring chunks."""
    chunks: list[str] = []
    current_blocks: list[str] = []

    for block in blocks:
        if len(block) > config.max_size:
            if current_blocks:
                chunks.append(_join_blocks(current_blocks))
                current_blocks = []
            chunks.extend(_split_large_block(block, config))
            continue

        candidate_blocks = [*current_blocks, block]
        candidate = _join_blocks(candidate_blocks)

        if len(candidate) <= config.target_size:
            current_blocks = candidate_blocks
            continue

        current_text = _join_blocks(current_blocks)
        if current_text and len(current_text) >= config.min_size:
            chunks.append(current_text)
            current_blocks = _start_next_chunk(current_text, block, config)
            continue

        if len(candidate) <= config.max_size:
            current_blocks = candidate_blocks
            continue

        if current_text:
            chunks.append(current_text)
        current_blocks = [block]

    if current_blocks:
        chunks.append(_join_blocks(current_blocks))

    return [chunk for chunk in chunks if chunk.strip()]


def _split_large_block(block: str, config: ChunkConfig) -> list[str]:
    """Split one unusually large OCR block by character size as a last fallback."""
    chunks: list[str] = []
    start = 0

    while start < len(block):
        end = min(start + config.max_size, len(block))
        chunk = block[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end == len(block):
            break

        start = max(end - config.overlap_size, start + 1)

    return chunks


def _merge_small_tail_chunks(chunks: list[str], config: ChunkConfig) -> list[str]:
    """Merge a tiny last chunk into the previous chunk when it fits."""
    if len(chunks) < 2:
        return chunks

    last_chunk = chunks[-1]
    previous_chunk = chunks[-2]
    merged = f"{previous_chunk}\n{last_chunk}".strip()

    if len(last_chunk) < config.min_size and len(merged) <= config.max_size:
        return [*chunks[:-2], merged]

    return chunks


def _start_next_chunk(previous_text: str, next_block: str, config: ChunkConfig) -> list[str]:
    """Start a new chunk with a small tail overlap from the previous chunk."""
    overlap = _tail_overlap(previous_text, config.overlap_size)
    if overlap:
        return [overlap, next_block]

    return [next_block]


def _tail_overlap(text: str, overlap_size: int) -> str:
    """Return a readable tail section to overlap into the next chunk."""
    if overlap_size <= 0 or len(text) <= overlap_size:
        return ""

    tail = text[-overlap_size:]
    newline_index = tail.find("\n")
    if newline_index != -1 and newline_index + 1 < len(tail):
        tail = tail[newline_index + 1 :]

    return tail.strip()


def _join_blocks(blocks: list[str]) -> str:
    """Join blocks while preserving readable line breaks."""
    return "\n".join(block.strip() for block in blocks if block.strip()).strip()


def _build_chunk_id(page: dict[str, Any], chunk_index: int) -> str:
    """Build a stable chunk ID from book, page, and chunk number."""
    return f"{page['book_id']}_p{page['page_no']:04d}_c{chunk_index:04d}"
