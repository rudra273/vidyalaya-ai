"""Configuration for RAG retrieval functions."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv


@dataclass(frozen=True)
class RagConfig:
    """Runtime settings for textbook retrieval."""

    qdrant_url: str = field(default_factory=lambda: _env_value("QDRANT_URL", "http://localhost:6333"))
    qdrant_api_key: str | None = field(default_factory=lambda: _env_value("QDRANT_API_KEY"))
    collection_name: str = "vidyalaya_textbook_chunks"
    embedding_model: str = "gemini-embedding-2"
    embedding_dim: int = 1536
    top_k: int = 10
    request_timeout_ms: int = 60_000
    final_context_blocks: int = 4
    neighbor_chunk_window: int = 1
    neighbor_page_window: int = 0
    max_context_chars: int = 6_000
    dedupe_context_chunks: bool = True
    min_context_score: float = 0.45
    max_answer_context_chars: int = 12_000


def load_gemini_api_key(env_path: str = ".env") -> str:
    """Load Gemini API key from environment or a local .env file."""
    load_dotenv(env_path)

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")

    return api_key


def _env_value(name: str, default: str | None = None) -> str | None:
    """Load one environment value from process env or .env."""
    load_dotenv()
    return os.getenv(name) or default
