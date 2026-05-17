"""Run the Vidyalaya AI RAG ingestion pipeline.

For now this file only holds the shared configuration and environment check.
The actual loader, chunker, embedder, and Qdrant upsert steps are added in the
next phases.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ingestion.chunk import ChunkConfig, chunk_pages
from ingestion.embed import EmbeddingConfig, embed_chunks, load_gemini_api_key
from ingestion.loader import load_ocr_jsonl_pages
from ingestion.qdrant_store import ensure_collection, make_qdrant_client, upsert_embedded_chunks


@dataclass(frozen=True)
class IngestionConfig:
    """Configuration for local ingestion runs."""

    board: str = "scert_odisha"
    class_no: int = 8
    subject: str = "english"
    processed_ocr_root: Path = Path("data/processed/ocr")
    qdrant_url: str = "http://localhost:6333"
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

    @property
    def input_jsonl(self) -> Path:
        """Return the JSONL path for the configured subject."""
        return self.jsonl_dir / f"{self.subject}.jsonl"

    @property
    def embedding_cache_path(self) -> Path:
        """Return the local resume cache path for embedded chunks."""
        file_name = f"{self.subject}_{self.embedding_model}_{self.embedding_dim}.jsonl"
        return self.embedding_cache_root / self.board / f"class_{self.class_no}" / file_name

    @property
    def embedding_config(self) -> EmbeddingConfig:
        """Return Gemini embedding settings for the configured run."""
        return EmbeddingConfig(
            model=self.embedding_model,
            dimension=self.embedding_dim,
            batch_size=self.embedding_batch_size,
            cache_path=self.embedding_cache_path,
            request_delay_seconds=2.0,
            max_retries=5,
        )


def main() -> None:
    """Check configuration, environment, and load the configured JSONL file."""
    config = IngestionConfig()
    api_key = load_gemini_api_key()

    load_result = load_ocr_jsonl_pages(
        config.input_jsonl,
        expected_board=config.board,
        expected_class=config.class_no,
        expected_subject=config.subject,
    )
    chunks = chunk_pages(load_result.pages, config.chunk_config)
    qdrant_client = make_qdrant_client(config.qdrant_url)
    ensure_collection(
        qdrant_client,
        collection_name=config.collection_name,
        vector_size=config.embedding_dim,
    )

    print("Ingestion configuration is ready.")
    print(f"Input JSONL: {config.input_jsonl}")
    print(f"Qdrant URL: {config.qdrant_url}")
    print(f"Collection: {config.collection_name}")
    print(f"Embedding model: {config.embedding_model}")
    print(f"Embedding dimension: {config.embedding_dim}")
    print(f"JSONL rows found: {load_result.total_rows}")
    print(f"Pages loaded: {len(load_result.pages)}")
    print(f"Empty pages skipped: {load_result.skipped_empty_pages}")
    print(f"Chunks created: {len(chunks)}")
    print(f"Chunk target size: {config.chunk_config.target_size}")
    print(f"Chunk max size: {config.chunk_config.max_size}")
    print(f"Chunk overlap size: {config.chunk_config.overlap_size}")
    print(f"Embedding cache: {config.embedding_cache_path}")

    if not config.run_embeddings:
        print("Embedding run is disabled. Set run_embeddings=True when ready to call Gemini.")
        return

    embedded_records = embed_chunks(
        chunks,
        config.embedding_config,
        api_key=api_key,
    )
    print(f"Embedding records ready: {len(embedded_records)}")
    inserted_count = upsert_embedded_chunks(
        qdrant_client,
        collection_name=config.collection_name,
        embedded_records=embedded_records,
    )
    print(f"Qdrant points upserted: {inserted_count}")


if __name__ == "__main__":
    main()
