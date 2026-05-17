"""Embed student queries for textbook retrieval."""

from __future__ import annotations

from google import genai
from google.genai import types

from vidyalaya_ai.rag.config import RagConfig, load_gemini_api_key


def embed_query(query: str, config: RagConfig | None = None) -> list[float]:
    """Embed one student query with Gemini Embedding 2."""
    config = config or RagConfig()
    cleaned_query = query.strip()
    if not cleaned_query:
        raise ValueError("Query cannot be empty.")

    client = genai.Client(
        api_key=load_gemini_api_key(),
        http_options=types.HttpOptions(timeout=config.request_timeout_ms),
    )
    result = client.models.embed_content(
        model=config.embedding_model,
        contents=format_query_for_embedding(cleaned_query),
        config=types.EmbedContentConfig(output_dimensionality=config.embedding_dim),
    )

    embeddings = getattr(result, "embeddings", None)
    if embeddings is None:
        embedding = getattr(result, "embedding", None)
        embeddings = [embedding] if embedding is not None else []

    if not embeddings:
        raise ValueError("Gemini did not return a query embedding.")

    vector = [float(value) for value in embeddings[0].values]
    if len(vector) != config.embedding_dim:
        raise ValueError(f"Expected {config.embedding_dim}-dim embedding, got {len(vector)}.")

    return vector


def format_query_for_embedding(query: str) -> str:
    """Format a student question before embedding."""
    return "\n".join(
        [
            "task: question answering | query:",
            "",
            query.strip(),
        ]
    )

