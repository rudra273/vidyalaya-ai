"""Generate answers from retrieved textbook context blocks."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from vidyalaya_ai.rag.config import RagConfig
from vidyalaya_ai.rag.logging_config import setup_rag_logging


logger = logging.getLogger("vidyalaya_ai.rag")


def generate_answer(
    *,
    query: str,
    context_blocks: list[dict[str, Any]],
    llm: Runnable,
    config: RagConfig | None = None,
) -> dict[str, Any]:
    """Generate an answer using a LangChain-compatible LLM."""
    if not logger.handlers:
        setup_rag_logging()

    config = config or RagConfig()
    cleaned_query = query.strip()
    if not cleaned_query:
        raise ValueError("Query cannot be empty.")

    if _context_is_weak(context_blocks, config):
        logger.info("Context is weak or empty. Returning not-found answer without LLM call.")
        return {
            "answer": "I could not find this clearly in the provided textbook context.",
            "citations": [],
            "used_context_blocks": [],
            "context_strength": "weak",
        }

    messages = build_answer_messages(cleaned_query, context_blocks, config=config)
    response = llm.invoke(messages)
    answer = _response_text(response)
    citations = build_citations(context_blocks)

    logger.info("Generated answer with %s context blocks and %s citations", len(context_blocks), len(citations))
    return {
        "answer": answer,
        "citations": citations,
        "used_context_blocks": context_blocks,
        "context_strength": "ok",
    }


def build_answer_messages(
    query: str,
    context_blocks: list[dict[str, Any]],
    *,
    config: RagConfig | None = None,
) -> list[BaseMessage]:
    """Build LangChain chat messages for grounded textbook answering."""
    config = config or RagConfig()
    context_text = format_context_for_prompt(context_blocks, config=config)

    system_prompt = (
        "You are Vidyalaya AI, a careful textbook assistant for school students. "
        "Answer only from the provided textbook context. "
        "If the context does not clearly contain the answer, say that it was not found clearly. "
        "Do not use outside knowledge. "
        "Include citations using the context labels like [1], [2]."
    )
    human_prompt = (
        f"Student question:\n{query.strip()}\n\n"
        f"Textbook context:\n{context_text}\n\n"
        "Answer the student clearly and cite the relevant context labels."
    )

    return [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt),
    ]


def format_context_for_prompt(
    context_blocks: list[dict[str, Any]],
    *,
    config: RagConfig | None = None,
) -> str:
    """Format context blocks with citation labels for the LLM prompt."""
    config = config or RagConfig()
    formatted_blocks: list[str] = []
    total_chars = 0

    for index, block in enumerate(context_blocks, start=1):
        citation = _citation_label(index, block)
        text = str(block.get("text", "")).strip()
        if not text:
            continue

        block_text = f"{citation}\n{text}"
        if total_chars + len(block_text) > config.max_answer_context_chars:
            remaining_chars = config.max_answer_context_chars - total_chars
            if remaining_chars <= 0:
                break
            block_text = block_text[:remaining_chars].rstrip()

        formatted_blocks.append(block_text)
        total_chars += len(block_text)

    return "\n\n".join(formatted_blocks)


def build_citations(context_blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build citation metadata for final answers."""
    citations = []
    for index, block in enumerate(context_blocks, start=1):
        citations.append(
            {
                "label": f"[{index}]",
                "book_name": block.get("book_name"),
                "source_pdf": block.get("source_pdf"),
                "page_no": block.get("page_no"),
                "score": block.get("score"),
                "chunk_ids": block.get("chunk_ids", []),
            }
        )

    return citations


def _citation_label(index: int, block: dict[str, Any]) -> str:
    """Create a readable citation heading for one context block."""
    return (
        f"[{index}] "
        f"Book: {block.get('book_name')} | "
        f"PDF: {block.get('source_pdf')} | "
        f"Page: {block.get('page_no')}"
    )


def _context_is_weak(context_blocks: list[dict[str, Any]], config: RagConfig) -> bool:
    """Return whether context is too weak to answer from."""
    if not context_blocks:
        return True

    best_score = max(float(block.get("score") or 0.0) for block in context_blocks)
    return best_score < config.min_context_score


def _response_text(response: Any) -> str:
    """Extract text from a LangChain response object."""
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n".join(str(item) for item in content).strip()

    return str(content).strip()
