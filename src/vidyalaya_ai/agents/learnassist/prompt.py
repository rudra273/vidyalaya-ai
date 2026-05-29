"""System prompt and context/citation helpers for LearnAssist."""

from __future__ import annotations

import re
from typing import Any

from vidyalaya_ai.agents.learnassist.context import LearnAssistContext
from vidyalaya_ai.rag.config import RagConfig


SYSTEM_PROMPT = (
    "You are LearnAssist, a friendly study helper for Indian school students.\n\n"
    "TOOL USE - this is important:\n"
    "You have a `search_textbook` tool that searches the student's actual prescribed "
    "textbooks. You do NOT know the contents of these specific textbooks from memory. "
    "For ANY question about textbook or curriculum content - facts, concepts, "
    "definitions, who/what/when/why questions, chapter or exercise questions, 'how "
    "many chapters', topics in a book - you MUST call `search_textbook` FIRST and "
    "answer from what it returns. Never answer such questions from your own memory "
    "without searching, even if you think you know the answer.\n\n"
    "Do NOT call the tool for:\n"
    "- greetings, thanks, or small talk -> reply briefly and warmly\n"
    "- a follow-up about something already answered in this conversation, where the "
    "needed passages are already present above -> answer from that existing context\n"
    "- rephrasing/translating your own previous answer ('explain again', 'say it in "
    "English') -> use the prior turn\n\n"
    "When you use the tool, ground your answer in the returned passages and cite them "
    "inline as [1], [2], ... in the order shown. If you genuinely did not use the "
    "tool, do not add citation labels. Explain simply, step by step, at a school "
    "student's level."
)


# Map common language codes to full names so the model answers in the right script.
_LANGUAGE_NAMES = {
    "or": "Odia",
    "od": "Odia",
    "hi": "Hindi",
    "en": "English",
    "bn": "Bengali",
    "sa": "Sanskrit",
    "te": "Telugu",
    "ta": "Tamil",
}


def build_system_prompt(context: LearnAssistContext) -> str:
    """Build the per-request system prompt, adding the language rule."""
    if context.language:
        code = context.language.strip().lower()
        name = _LANGUAGE_NAMES.get(code, context.language)
        language_rule = (
            f"IMPORTANT: Write your entire reply in {name}. "
            "Use natural, simple language a school student can read."
        )
    else:
        language_rule = "Reply in the same language as the student's question."
    return f"{SYSTEM_PROMPT}\n\n{language_rule}"


def format_context(context_blocks: list[dict[str, Any]], rag_config: RagConfig) -> str:
    """Format context blocks with citation labels for the tool message."""
    formatted_blocks: list[str] = []
    total_chars = 0

    for index, block in enumerate(context_blocks, start=1):
        text = str(block.get("text", "")).strip()
        if not text:
            continue

        block_text = f"{citation_heading(index, block)}\n{text}"
        if total_chars + len(block_text) > rag_config.max_answer_context_chars:
            remaining_chars = rag_config.max_answer_context_chars - total_chars
            if remaining_chars <= 0:
                break
            block_text = block_text[:remaining_chars].rstrip()

        formatted_blocks.append(block_text)
        total_chars += len(block_text)

    return "\n\n".join(formatted_blocks)


def citation_heading(index: int, block: dict[str, Any]) -> str:
    """Create a citation heading for a context block."""
    return (
        f"[{index}] "
        f"Book: {block.get('book_name')} | "
        f"PDF: {block.get('source_pdf')} | "
        f"Page: {block.get('page_no')}"
    )


def build_citations(context_blocks: list[dict[str, Any]], answer: str) -> list[dict[str, Any]]:
    """Build citation metadata only for labels actually used in the answer."""
    used_labels = {int(match) for match in re.findall(r"\[(\d+)\]", answer)}
    if not used_labels:
        return []

    citations = []
    for index, block in enumerate(context_blocks, start=1):
        if index not in used_labels:
            continue

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


def build_retrieval_metadata(
    retrieval_result: dict[str, Any] | None,
    *,
    tool_used: bool,
) -> dict[str, Any]:
    """Build response metadata about retrieval."""
    metadata = dict(retrieval_result.get("metadata", {})) if retrieval_result else {}
    metadata["tool_used"] = tool_used
    return metadata
