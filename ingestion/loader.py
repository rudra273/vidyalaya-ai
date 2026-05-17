"""Load and validate OCR JSONL pages for ingestion."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUIRED_PAGE_FIELDS = (
    "board",
    "class",
    "subject",
    "book_name",
    "book_id",
    "language",
    "source_pdf",
    "page_no",
    "text",
)


@dataclass(frozen=True)
class PageLoadResult:
    """Result of loading one OCR JSONL file."""

    pages: list[dict[str, Any]]
    total_rows: int
    skipped_empty_pages: int


def load_ocr_jsonl_pages(
    jsonl_path: Path,
    *,
    expected_board: str,
    expected_class: int,
    expected_subject: str,
) -> PageLoadResult:
    """Load OCR pages from JSONL and validate required metadata."""
    if not jsonl_path.exists():
        raise FileNotFoundError(f"JSONL file not found: {jsonl_path}")

    pages: list[dict[str, Any]] = []
    total_rows = 0
    skipped_empty_pages = 0

    with jsonl_path.open("r", encoding="utf-8") as file:
        for line_no, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue

            total_rows += 1
            page = _parse_json_line(line, jsonl_path, line_no)
            _validate_page(page, jsonl_path, line_no)
            _validate_expected_metadata(
                page,
                jsonl_path,
                line_no,
                expected_board=expected_board,
                expected_class=expected_class,
                expected_subject=expected_subject,
            )

            text = str(page["text"]).strip()
            if not text:
                skipped_empty_pages += 1
                continue

            page = dict(page)
            page["text"] = text
            pages.append(page)

    return PageLoadResult(
        pages=pages,
        total_rows=total_rows,
        skipped_empty_pages=skipped_empty_pages,
    )


def _parse_json_line(line: str, jsonl_path: Path, line_no: int) -> dict[str, Any]:
    """Parse one JSONL row and add file context to JSON errors."""
    try:
        data = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {jsonl_path} at line {line_no}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {jsonl_path} at line {line_no}")

    return data


def _validate_page(page: dict[str, Any], jsonl_path: Path, line_no: int) -> None:
    """Validate fields required by the ingestion pipeline."""
    missing_fields = [field for field in REQUIRED_PAGE_FIELDS if field not in page]
    if missing_fields:
        missing = ", ".join(missing_fields)
        raise ValueError(f"Missing fields in {jsonl_path} at line {line_no}: {missing}")

    if not isinstance(page["page_no"], int):
        raise ValueError(f"page_no must be an integer in {jsonl_path} at line {line_no}")

    if not isinstance(page["text"], str):
        raise ValueError(f"text must be a string in {jsonl_path} at line {line_no}")


def _validate_expected_metadata(
    page: dict[str, Any],
    jsonl_path: Path,
    line_no: int,
    *,
    expected_board: str,
    expected_class: int,
    expected_subject: str,
) -> None:
    """Make sure the file being loaded matches the configured run."""
    if page["board"] != expected_board:
        raise ValueError(f"Unexpected board in {jsonl_path} at line {line_no}: {page['board']}")

    if page["class"] != expected_class:
        raise ValueError(f"Unexpected class in {jsonl_path} at line {line_no}: {page['class']}")

    if page["subject"] != expected_subject:
        raise ValueError(f"Unexpected subject in {jsonl_path} at line {line_no}: {page['subject']}")
