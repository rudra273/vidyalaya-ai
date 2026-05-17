"""Configuration for RAG retrieval functions."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class RagConfig:
    """Runtime settings for textbook retrieval."""

    qdrant_url: str = "http://localhost:6333"
    collection_name: str = "vidyalaya_textbook_chunks"
    embedding_model: str = "gemini-embedding-2"
    embedding_dim: int = 1536
    top_k: int = 10
    request_timeout_ms: int = 60_000


def load_gemini_api_key(env_path: str = ".env") -> str:
    """Load Gemini API key from environment or a local .env file."""
    load_dotenv(env_path)

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")

    return api_key

