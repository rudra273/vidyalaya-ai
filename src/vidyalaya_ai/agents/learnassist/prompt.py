"""System prompt and context/citation helpers for LearnAssist."""

from __future__ import annotations

import re
from typing import Any

from vidyalaya_ai.agents.learnassist.context import LearnAssistContext
from vidyalaya_ai.rag.config import RagConfig


SYSTEM_PROMPT = (
    "You are LearnAssist, a friendly study helper for Indian school students.\n\n"
    "ANSWER THE CURRENT MESSAGE:\n"
    "Always respond to the student's MOST RECENT message. Earlier turns are context "
    "only - never answer a previous question that the student has moved on from. If "
    "the latest message is a greeting or a brand-new topic, treat it as such even if "
    "the conversation above was about something else.\n\n"
    "TOOL USE - this is important:\n"
    "You have a `search_textbook` tool that searches the student's actual prescribed "
    "textbooks. You do NOT know the contents of these specific textbooks from memory. "
    "For ANY question about textbook or curriculum content - facts, concepts, "
    "definitions, who/what/when/why questions, chapter or exercise questions, 'how "
    "many chapters', topics in a book - you MUST call `search_textbook` FIRST and "
    "answer from what it returns. Never answer such questions from your own memory "
    "without searching, even if you think you know the answer.\n\n"
    "Do NOT call the tool for:\n"
    "- greetings, thanks, or small talk ('hi', 'hello', 'thanks', 'ok') -> reply "
    "briefly and warmly; do NOT search, and do NOT continue a previous topic\n"
    "- a follow-up about something already answered in this conversation, where the "
    "needed passages are already present above -> answer from that existing context\n"
    "- rephrasing/translating your own previous answer ('explain again', 'say it in "
    "English') -> use the prior turn\n\n"
    "QUERY GENERATION — always do this before calling the tool:\n"
    "Generate a retrieval query in the native script of the textbook. Use multiple "
    "keywords and synonyms so the search is richer, not just one word.\n"
    "- If the student wrote in Roman/transliterated script (e.g. 'kabir das ke dohe', "
    "'pehla chapter'), convert to the correct native script first.\n"
    "- Hindi subject -> Devanagari (e.g. 'कबीर दास के दोहे गुरु गोविंद साखी')\n"
    "- Odia subject -> Odia script (e.g. 'ଜାତୀୟ କବି ବୀରକିଶୋର ଦାସ ଓଡ଼ିଆ ସାହିତ୍ୟ')\n"
    "- Sanskrit subject -> Devanagari\n"
    "- English subject -> English\n"
    "Never pass the student's raw Roman-script message as the query argument.\n\n"
    "CHAPTER / TOPIC QUESTIONS — two-step retrieval:\n"
    "When the student asks about a chapter by number or position ('first chapter', "
    "'chapter 2', 'pehla chapter', 'prathama paatha') and you don't already know "
    "what that chapter contains:\n"
    "  Step 1 — search for the table of contents first using the TOC query for the "
    "subject (see below). Read the result to find the chapter name and page range.\n"
    "  Step 2 — confirm with the student: 'Chapter 1 is [name]. Shall I explain it?'\n"
    "  Step 3 — after the student confirms, call the tool again with the chapter name "
    "and key terms as the query to retrieve the actual content.\n"
    "Skip step 1 if the student already names the content ('explain kabir das ke dohe') "
    "or if the TOC was already retrieved earlier in this conversation.\n\n"
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

# TOC query strings per subject — multiple synonyms in the actual script of that
# textbook so the embedding hits the suchipatra page even if OCR spelling varies.
# Odia-medium books (science, maths, social_science) use Odia script only.
_TOC_QUERIES: dict[str, str] = {
    "odia": "ସୂଚୀପତ୍ର ବିଷୟ ସୂଚୀ ପାଠ ତାଲିକା ଅଧ୍ୟାୟ",
    "hindi": "विषय-सूची सूचीपत्र अध्याय पाठ सामग्री",
    "sanskrit": "विषय-सूची पाठसूची अध्याय सूचीपत्र",
    "english": "table of contents chapters units lessons index",
    "maths": "ସୂଚୀପତ୍ର ବିଷୟ ସୂଚୀ ଅଧ୍ୟାୟ ଏକକ",
    "science": "ସୂଚୀପତ୍ର ବିଷୟ ସୂଚୀ ଅଧ୍ୟାୟ ଏକକ",
    "social_science": "ସୂଚୀପତ୍ର ବିଷୟ ସୂଚୀ ଅଧ୍ୟାୟ ଏକକ",
}


def build_system_prompt(context: LearnAssistContext) -> str:
    """Build the per-request system prompt, adding the language rule and TOC query."""
    if context.language:
        code = context.language.strip().lower()
        name = _LANGUAGE_NAMES.get(code, context.language)
        language_rule = (
            f"IMPORTANT: Write your entire reply in {name}. "
            "Use natural, simple language a school student can read."
        )
    else:
        language_rule = "Reply in the same language as the student's question."

    subject_key = (context.subject or "").strip().lower()

    # Tell the LLM exactly what the student has selected so it never asks questions
    # it already has the answer to ("which subject?", "which book?").
    if subject_key:
        context_line = (
            f"STUDENT CONTEXT: board={context.board}, class={context.class_no}, "
            f"subject={subject_key}. "
            f"The subject is already known — never ask the student which subject or book. "
            f"Always use subject={subject_key} when calling search_textbook."
        )
    else:
        context_line = (
            f"STUDENT CONTEXT: board={context.board}, class={context.class_no}, "
            f"subject=not selected (search across all subjects for this class). "
            f"The student is in 'ask anything' mode — do NOT ask which subject. "
            f"Just call search_textbook without a subject filter and answer from results."
        )

    toc_query = _TOC_QUERIES.get(subject_key)
    if toc_query:
        toc_rule = (
            f"TOC QUERY FOR THIS SUBJECT: When you need the table of contents, "
            f"call search_textbook with exactly this query: \"{toc_query}\""
        )
    else:
        toc_rule = (
            "TOC QUERY: When you need the table of contents, search using the "
            "native-script words for 'table of contents', 'chapters', 'index'."
        )

    return f"{SYSTEM_PROMPT}\n\n{context_line}\n\n{toc_rule}\n\n{language_rule}"


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
