"""Simple hardcoded retrieve_textbook tool test."""

from __future__ import annotations

import textwrap
from typing import Any

from vidyalaya_ai.tools.retrieve_textbook import TextbookRetrievalConfig, retrieve_textbook


# Change only these values while testing.
QUERY = "କୋଷ କିଏ ଆବିଷ୍କାର କରିଥିଲେ?"
BOARD = "scert_odisha"
CLASS_NO = 8

# Set SUBJECT to None to test whether retrieval finds the subject by itself.
# Examples: "english", "maths", "science", "social_science", "odia", "hindi", "sanskrit"
SUBJECT = None

TOP_K = 10
CONTEXT_BLOCKS = 4
NEIGHBOR_CHUNK_WINDOW = 1
NEIGHBOR_PAGE_WINDOW = 0
MAX_CONTEXT_CHARS = 6000
PREVIEW_CHARS = 1200


def main() -> None:
    """Run a manual query and print tool output."""
    result = retrieve_textbook(
        query=QUERY,
        board=BOARD,
        class_no=CLASS_NO,
        subject=SUBJECT,
        tool_config=TextbookRetrievalConfig(
            top_k=TOP_K,
            context_blocks=CONTEXT_BLOCKS,
            neighbor_chunk_window=NEIGHBOR_CHUNK_WINDOW,
            neighbor_page_window=NEIGHBOR_PAGE_WINDOW,
            max_context_chars=MAX_CONTEXT_CHARS,
        ),
    )

    raw_hits = result["raw_hits"]
    contexts = result["context_blocks"]
    metadata = result["metadata"]

    print("\nINPUT")
    print("=" * 100)
    print(f"query: {QUERY}")
    print(f"board: {BOARD}")
    print(f"class: {CLASS_NO}")
    print(f"subject: {SUBJECT}")

    print("\nMETADATA")
    print("=" * 100)
    print(metadata)

    print("\nRAW TOP HITS")
    print("=" * 100)
    for index, hit in enumerate(raw_hits, start=1):
        print_hit(index, hit)

    print("\nMERGED CONTEXT BLOCKS")
    print("=" * 100)
    for index, block in enumerate(contexts, start=1):
        print_context_block(index, block)


def run_subject_provided_test() -> dict[str, Any]:
    """Run a quick test with an explicit subject filter."""
    return retrieve_textbook(
        query=QUERY,
        board=BOARD,
        class_no=CLASS_NO,
        subject="science",
        tool_config=TextbookRetrievalConfig(
            top_k=TOP_K,
            context_blocks=CONTEXT_BLOCKS,
            neighbor_chunk_window=NEIGHBOR_CHUNK_WINDOW,
            neighbor_page_window=NEIGHBOR_PAGE_WINDOW,
            max_context_chars=MAX_CONTEXT_CHARS,
        ),
    )


def run_subject_missing_test() -> dict[str, Any]:
    """Run a quick test without a subject filter."""
    return retrieve_textbook(
        query=QUERY,
        board=BOARD,
        class_no=CLASS_NO,
        subject=None,
        tool_config=TextbookRetrievalConfig(
            top_k=TOP_K,
            context_blocks=CONTEXT_BLOCKS,
            neighbor_chunk_window=NEIGHBOR_CHUNK_WINDOW,
            neighbor_page_window=NEIGHBOR_PAGE_WINDOW,
            max_context_chars=MAX_CONTEXT_CHARS,
        ),
    )


def run_cross_subject_test() -> dict[str, Any]:
    """Run a quick test where subject discovery should happen through retrieval."""
    return retrieve_textbook(
        query="Who was Major Somnath Sharma?",
        board=BOARD,
        class_no=CLASS_NO,
        subject=None,
        tool_config=TextbookRetrievalConfig(
            top_k=TOP_K,
            context_blocks=CONTEXT_BLOCKS,
            neighbor_chunk_window=NEIGHBOR_CHUNK_WINDOW,
            neighbor_page_window=NEIGHBOR_PAGE_WINDOW,
            max_context_chars=MAX_CONTEXT_CHARS,
        ),
    )


def print_hit(index: int, hit: dict[str, Any]) -> None:
    """Print one raw retrieval hit."""
    print(f"\n[{index}] score={hit['score']:.4f}")
    print(f"subject={hit['subject']} | book={hit['book_name']} | page={hit['page_no']}")
    print(f"source_pdf={hit['source_pdf']}")
    print(f"chunk_id={hit['chunk_id']} | chunk_index={hit['chunk_index']}")


def print_context_block(index: int, block: dict[str, Any]) -> None:
    """Print one merged context block."""
    print(f"\n[{index}] score={block['score']:.4f}")
    print(f"subject={block['subject']} | book={block['book_name']} | page={block['page_no']}")
    print(f"source_pdf={block['source_pdf']}")
    print(f"chunk_ids={block['chunk_ids']}")
    print("context:")
    print(indent_text(str(block["text"])[:PREVIEW_CHARS]))


def indent_text(text: str) -> str:
    """Indent multi-line text for readable terminal output."""
    return textwrap.indent(text.strip(), "  ")


if __name__ == "__main__":
    main()
