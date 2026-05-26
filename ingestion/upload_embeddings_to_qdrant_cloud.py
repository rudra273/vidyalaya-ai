"""Upload saved embedding JSONL files to Qdrant Cloud."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from dotenv import load_dotenv

from ingestion.logging_config import setup_logging
from ingestion.qdrant_store import ensure_collection, make_qdrant_client, upsert_embedded_chunks


@dataclass(frozen=True)
class UploadConfig:
    """Settings for uploading saved embeddings to Qdrant."""

    board: str = "scert_odisha"
    class_no: int = 8
    embedding_model: str = "gemini-embedding-2"
    embedding_dim: int = 1536
    collection_name: str = "vidyalaya_textbook_chunks"
    embedding_root: Path = Path("data/processed/embeddings")
    batch_size: int = 16
    qdrant_timeout_seconds: int = 180

    @property
    def embedding_dir(self) -> Path:
        """Return directory containing embedding JSONL files."""
        return self.embedding_root / self.board / f"class_{self.class_no}"


def main() -> None:
    """Upload all configured class embeddings to Qdrant Cloud."""
    logger = setup_logging("logs/qdrant_cloud_upload.log")
    config = UploadConfig()
    qdrant_url, qdrant_api_key = _load_qdrant_env()
    embedding_files = list(_embedding_files(config))

    if not embedding_files:
        raise FileNotFoundError(f"No embedding JSONL files found in {config.embedding_dir}")

    client = make_qdrant_client(
        qdrant_url,
        qdrant_api_key,
        timeout=config.qdrant_timeout_seconds,
    )
    ensure_collection(
        client,
        collection_name=config.collection_name,
        vector_size=config.embedding_dim,
    )

    logger.info("Qdrant URL configured: %s", bool(qdrant_url))
    logger.info("Qdrant API key configured: %s", bool(qdrant_api_key))
    logger.info("Collection: %s", config.collection_name)
    logger.info("Embedding directory: %s", config.embedding_dir)
    logger.info("Embedding files: %s", len(embedding_files))
    logger.info("Upload batch size: %s", config.batch_size)

    total_uploaded = 0
    for embedding_file in embedding_files:
        subject = _subject_from_file_name(embedding_file, config)
        count = upload_embedding_file(client, config, embedding_file)
        total_uploaded += count
        logger.info("Uploaded subject=%s count=%s file=%s", subject, count, embedding_file)

    cloud_count = client.count(collection_name=config.collection_name, exact=True).count
    logger.info("Upload complete. Total uploaded from files: %s", total_uploaded)
    logger.info("Cloud collection count: %s", cloud_count)
    print(f"Upload complete: {total_uploaded} records")
    print(f"Cloud collection count: {cloud_count}")


def upload_embedding_file(client, config: UploadConfig, embedding_file: Path) -> int:
    """Upload one embedding JSONL file in batches."""
    logger = logging.getLogger("ingestion")
    uploaded = 0
    batch: list[dict[str, Any]] = []

    for record in _read_embedding_records(embedding_file, config.embedding_dim):
        batch.append(record)
        if len(batch) >= config.batch_size:
            uploaded += upsert_embedded_chunks(
                client,
                collection_name=config.collection_name,
                embedded_records=batch,
                batch_size=config.batch_size,
            )
            batch = []

    if batch:
        uploaded += upsert_embedded_chunks(
            client,
            collection_name=config.collection_name,
            embedded_records=batch,
            batch_size=config.batch_size,
        )

    logger.info("Finished file upload: %s records=%s", embedding_file, uploaded)
    return uploaded


def _read_embedding_records(embedding_file: Path, embedding_dim: int) -> Iterable[dict[str, Any]]:
    """Yield validated embedding records from one JSONL file."""
    with embedding_file.open("r", encoding="utf-8") as file:
        for line_no, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue

            record = json.loads(line)
            _validate_record(record, embedding_file, line_no, embedding_dim)
            yield record


def _validate_record(record: dict[str, Any], path: Path, line_no: int, embedding_dim: int) -> None:
    """Validate one saved embedding record before upload."""
    chunk_id = record.get("chunk_id")
    vector = record.get("vector")
    payload = record.get("payload")

    if not chunk_id:
        raise ValueError(f"Missing chunk_id at {path}:{line_no}")
    if not isinstance(vector, list) or len(vector) != embedding_dim:
        raise ValueError(f"Invalid vector at {path}:{line_no}")
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid payload at {path}:{line_no}")


def _embedding_files(config: UploadConfig) -> Iterable[Path]:
    """Return embedding JSONL files for the configured class."""
    pattern = f"*_{config.embedding_model}_{config.embedding_dim}.jsonl"
    return sorted(config.embedding_dir.glob(pattern))


def _subject_from_file_name(embedding_file: Path, config: UploadConfig) -> str:
    """Extract subject from an embedding file name."""
    suffix = f"_{config.embedding_model}_{config.embedding_dim}"
    return embedding_file.stem.removesuffix(suffix)


def _load_qdrant_env() -> tuple[str, str]:
    """Load Qdrant Cloud URL and API key from .env."""
    load_dotenv()
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")

    if not qdrant_url:
        raise RuntimeError("QDRANT_URL is not set in .env.")
    if not qdrant_api_key:
        raise RuntimeError("QDRANT_API_KEY is not set in .env.")

    return qdrant_url, qdrant_api_key


if __name__ == "__main__":
    main()
