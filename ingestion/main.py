"""Run the Vidyalaya AI RAG ingestion pipeline.

For now this file only holds the shared configuration and environment check.
The actual loader, chunker, embedder, and Qdrant upsert steps are added in the
next phases.
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ingestion.chunk import ChunkConfig, chunk_pages
from ingestion.embed import EmbeddingConfig, embed_chunks, load_gemini_api_key
from ingestion.loader import load_ocr_jsonl_pages
from ingestion.logging_config import setup_logging
from ingestion.qdrant_store import ensure_collection, make_qdrant_client, upsert_embedded_chunks


def _env_value(name: str, default: str | None = None) -> str | None:
    """Load one environment value from process env or .env."""
    load_dotenv()
    return os.getenv(name) or default


@dataclass(frozen=True)
class IngestionConfig:
    """Configuration for local ingestion runs."""

    board: str = "scert_odisha"
    class_no: int = 7
    subjects: tuple[str, ...] = (
        "english",
        "hindi",
        "maths",
        "odia",
        "sanskrit",
        "science",
        "social_science",
    )
    processed_ocr_root: Path = Path("data/processed/ocr")
    qdrant_url: str = field(default_factory=lambda: _env_value("QDRANT_URL", "http://localhost:6333"))
    qdrant_api_key: str | None = field(default_factory=lambda: _env_value("QDRANT_API_KEY"))
    collection_name: str = "vidyalaya_textbook_chunks"
    embedding_model: str = "gemini-embedding-2"
    embedding_dim: int = 1536
    embedding_batch_size: int = 32
    run_embeddings: bool = True
    embedding_cache_root: Path = Path("data/processed/embeddings")
    chunk_config: ChunkConfig = ChunkConfig()

    @property
    def jsonl_dir(self) -> Path:
        """Return the JSONL directory for the configured board and class."""
        return self.processed_ocr_root / self.board / f"class_{self.class_no}" / "jsonl"

    def input_jsonl(self, subject: str) -> Path:
        """Return the JSONL path for the configured subject."""
        return self.jsonl_dir / f"{subject}.jsonl"

    def embedding_cache_path(self, subject: str) -> Path:
        """Return the local resume cache path for embedded chunks."""
        file_name = f"{subject}_{self.embedding_model}_{self.embedding_dim}.jsonl"
        return self.embedding_cache_root / self.board / f"class_{self.class_no}" / file_name

    def embedding_config(self, subject: str) -> EmbeddingConfig:
        """Return Gemini embedding settings for the configured run."""
        return EmbeddingConfig(
            model=self.embedding_model,
            dimension=self.embedding_dim,
            batch_size=self.embedding_batch_size,
            cache_path=self.embedding_cache_path(subject),
            request_delay_seconds=2.0,
            request_timeout_ms=60_000,
            retry_wait_seconds=(2, 5, 10, 20, 40, 60, 90, 120),
        )


def main() -> None:
    """Run ingestion for the configured subjects."""
    logger = setup_logging()
    config = IngestionConfig()
    api_key = load_gemini_api_key()
    qdrant_client = make_qdrant_client(config.qdrant_url, config.qdrant_api_key)
    ensure_collection(
        qdrant_client,
        collection_name=config.collection_name,
        vector_size=config.embedding_dim,
    )

    logger.info("Qdrant URL: %s", config.qdrant_url)
    logger.info("Qdrant API key configured: %s", bool(config.qdrant_api_key))
    logger.info("Collection: %s", config.collection_name)
    logger.info("Embedding model: %s", config.embedding_model)
    logger.info("Embedding dimension: %s", config.embedding_dim)
    logger.info("Subjects: %s", ", ".join(config.subjects))

    total_upserted = 0
    for subject in config.subjects:
        total_upserted += ingest_subject(config, qdrant_client, api_key, subject)

    logger.info("All configured subjects processed. Total points upserted: %s", total_upserted)


def ingest_subject(
    config: IngestionConfig,
    qdrant_client,
    api_key: str,
    subject: str,
) -> int:
    """Load, chunk, embed, and upsert one subject JSONL file."""
    logger = logging.getLogger("ingestion")
    input_jsonl = config.input_jsonl(subject)
    embedding_cache_path = config.embedding_cache_path(subject)

    logger.info("")
    logger.info("Starting subject: %s", subject)
    logger.info("Input JSONL: %s", input_jsonl)

    load_result = load_ocr_jsonl_pages(
        input_jsonl,
        expected_board=config.board,
        expected_class=config.class_no,
        expected_subject=subject,
    )
    chunks = chunk_pages(load_result.pages, config.chunk_config)

    logger.info("JSONL rows found: %s", load_result.total_rows)
    logger.info("Pages loaded: %s", len(load_result.pages))
    logger.info("Empty pages skipped: %s", load_result.skipped_empty_pages)
    logger.info("Chunks created: %s", len(chunks))
    logger.info("Chunk target size: %s", config.chunk_config.target_size)
    logger.info("Chunk max size: %s", config.chunk_config.max_size)
    logger.info("Chunk overlap size: %s", config.chunk_config.overlap_size)
    logger.info("Embedding cache: %s", embedding_cache_path)

    if not config.run_embeddings:
        logger.info("Embedding run is disabled. Set run_embeddings=True when ready to call Gemini.")
        return 0

    embedded_records = embed_chunks(
        chunks,
        config.embedding_config(subject),
        api_key=api_key,
    )
    logger.info("Embedding records ready: %s", len(embedded_records))
    inserted_count = upsert_embedded_chunks(
        qdrant_client,
        collection_name=config.collection_name,
        embedded_records=embedded_records,
    )
    logger.info("Qdrant points upserted: %s", inserted_count)
    return inserted_count


if __name__ == "__main__":
    main()
