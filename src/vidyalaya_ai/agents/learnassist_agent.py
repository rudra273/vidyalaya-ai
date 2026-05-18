"""LearnAssist Agent for student question answering."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from vidyalaya_ai.llm import LLMConfig, create_chat_model
from vidyalaya_ai.rag.config import RagConfig
from vidyalaya_ai.tools.retrieve_textbook import TextbookRetrievalConfig, retrieve_textbook


logger = logging.getLogger("vidyalaya_ai.agents")


@dataclass(frozen=True)
class LearnAssistInput:
    """Client/API inputs for the LearnAssist agent."""

    query: str
    board: str
    class_no: int
    subject: str | None = None
    language: str | None = None


def answer_with_learnassist(
    request: LearnAssistInput,
    *,
    llm: BaseChatModel | None = None,
    llm_config: LLMConfig | None = None,
    tool_config: TextbookRetrievalConfig | None = None,
    rag_config: RagConfig | None = None,
    existing_context_blocks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Answer a student question using textbook context when available."""
    _setup_agent_logging()
    _validate_request(request)

    rag_config = rag_config or RagConfig()
    context_blocks = existing_context_blocks or []
    retrieval_result: dict[str, Any] | None = None
    tool_used = not bool(context_blocks)

    if tool_used:
        retrieval_result = retrieve_textbook(
            query=request.query,
            board=request.board,
            class_no=request.class_no,
            subject=request.subject,
            tool_config=tool_config,
            rag_config=rag_config,
        )
        context_blocks = retrieval_result["context_blocks"]

    llm = llm or create_chat_model(llm_config or LLMConfig())
    messages = _build_messages(request, context_blocks, rag_config)
    logger.info("LearnAssist calling LLM for query=%s", request.query)
    response = llm.invoke(messages)
    answer = _response_text(response)

    return {
        "answer": answer,
        "citations": _build_citations(context_blocks, answer),
        "retrieval": _build_retrieval_metadata(retrieval_result, tool_used=tool_used),
        "context_blocks": context_blocks,
    }


def _build_messages(
    request: LearnAssistInput,
    context_blocks: list[dict[str, Any]],
    rag_config: RagConfig,
) -> list:
    """Build LearnAssist prompt messages."""
    context_text = _format_context(context_blocks, rag_config)
    language_instruction = (
        f"Reply in {request.language} when natural for the student."
        if request.language
        else "Reply in the same language as the student's question when possible."
    )

    system_prompt = (
        "You are LearnAssist, a careful textbook study assistant for school students. "
        "Use the provided textbook context when it is relevant. "
        "If the context is missing or not useful, still answer the student clearly using your own knowledge. "
        "Use citation labels like [1], [2] only when you actually use the provided context. "
        "Explain simply and step by step when useful. "
        f"{language_instruction}"
    )
    human_prompt = (
        f"Student question:\n{request.query.strip()}\n\n"
        f"Textbook context:\n{context_text}\n\n"
        "Answer clearly. Include citation labels only if you use the provided textbook context."
    )

    return [SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)]


def _format_context(context_blocks: list[dict[str, Any]], rag_config: RagConfig) -> str:
    """Format context blocks with citation labels."""
    formatted_blocks: list[str] = []
    total_chars = 0

    for index, block in enumerate(context_blocks, start=1):
        text = str(block.get("text", "")).strip()
        if not text:
            continue

        block_text = f"{_citation_heading(index, block)}\n{text}"
        if total_chars + len(block_text) > rag_config.max_answer_context_chars:
            remaining_chars = rag_config.max_answer_context_chars - total_chars
            if remaining_chars <= 0:
                break
            block_text = block_text[:remaining_chars].rstrip()

        formatted_blocks.append(block_text)
        total_chars += len(block_text)

    return "\n\n".join(formatted_blocks)


def _citation_heading(index: int, block: dict[str, Any]) -> str:
    """Create a prompt citation heading for a context block."""
    return (
        f"[{index}] "
        f"Book: {block.get('book_name')} | "
        f"PDF: {block.get('source_pdf')} | "
        f"Page: {block.get('page_no')}"
    )


def _build_citations(context_blocks: list[dict[str, Any]], answer: str) -> list[dict[str, Any]]:
    """Build citation metadata only for labels used in the answer."""
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


def _build_retrieval_metadata(
    retrieval_result: dict[str, Any] | None,
    *,
    tool_used: bool,
) -> dict[str, Any]:
    """Build response metadata about retrieval."""
    metadata = dict(retrieval_result.get("metadata", {})) if retrieval_result else {}
    metadata["tool_used"] = tool_used
    return metadata


def _response_text(response: Any) -> str:
    """Extract text from a LangChain response object."""
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n".join(str(item) for item in content).strip()

    return str(content).strip()


def _validate_request(request: LearnAssistInput) -> None:
    """Validate LearnAssist required inputs."""
    if not request.query.strip():
        raise ValueError("query cannot be empty.")
    if not request.board.strip():
        raise ValueError("board cannot be empty.")
    if request.class_no <= 0:
        raise ValueError("class_no must be a positive integer.")


def _setup_agent_logging(log_path: str | Path = "logs/agents.log") -> logging.Logger:
    """Configure a simple file logger for agents."""
    if logger.handlers:
        return logger

    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.info("Logging to %s", log_path)
    return logger
