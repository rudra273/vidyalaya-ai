"""Entry point for running the LearnAssist agent on a single chat turn."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import HumanMessage, ToolMessage

from vidyalaya_ai.agents.learnassist.agent import get_agent
from vidyalaya_ai.agents.learnassist.context import LearnAssistContext
from vidyalaya_ai.agents.learnassist.prompt import build_citations, build_retrieval_metadata
from vidyalaya_ai.agents.learnassist.tools import SEARCH_TOOL_NAME


logger = logging.getLogger("vidyalaya_ai.agents")


@dataclass
class LearnAssistResult:
    """Result of a single LearnAssist turn."""

    answer: str
    citations: list[dict[str, Any]] = field(default_factory=list)
    retrieval: dict[str, Any] = field(default_factory=dict)
    context_blocks: list[dict[str, Any]] = field(default_factory=list)


async def run_learnassist(
    message: str,
    context: LearnAssistContext,
    *,
    thread_id: str,
) -> LearnAssistResult:
    """Run one chat turn and return the answer with citations and metadata.

    The checkpointer stores only ``messages``. Per-turn inputs (board, class,
    subject, language) come from ``context`` each call, and retrieval output is
    read from this turn's search_textbook ToolMessage - so nothing leaks across
    turns. Any model/tool error propagates to the caller.
    """
    agent = get_agent()
    config = {"configurable": {"thread_id": thread_id}}
    logger.info(
        "LearnAssist turn thread=%s board=%s class=%s subject=%s",
        thread_id,
        context.board,
        context.class_no,
        context.subject,
    )

    # Any orphaned tool turn left by a previous crash is cleaned by the agent's
    # _heal_history middleware before the model runs (see agent.py).
    state = await agent.ainvoke(
        {"messages": [HumanMessage(message)]},
        context=context,
        config=config,
    )

    messages = state["messages"]
    answer = _final_text(messages[-1])
    blocks, retrieval = _retrieval_from_current_turn(messages)

    return LearnAssistResult(
        answer=answer,
        citations=build_citations(blocks, answer),
        retrieval=retrieval,
        context_blocks=blocks,
    )


def _retrieval_from_current_turn(
    messages: list[Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read retrieval output from the search_textbook ToolMessage of this turn.

    Only messages after the last human turn are considered, so a tool result
    from an earlier turn is never picked up.
    """
    last_human = _last_index(messages, HumanMessage)
    for message in reversed(messages[last_human + 1 :]):
        if (
            isinstance(message, ToolMessage)
            and message.name == SEARCH_TOOL_NAME
            and isinstance(message.artifact, dict)
        ):
            artifact = message.artifact
            return (
                artifact.get("context_blocks") or [],
                artifact.get("retrieval") or build_retrieval_metadata(None, tool_used=True),
            )
    return [], build_retrieval_metadata(None, tool_used=False)


def _last_index(messages: list[Any], message_type: type) -> int:
    """Return the index of the last message of the given type, or -1."""
    for index in range(len(messages) - 1, -1, -1):
        if isinstance(messages[index], message_type):
            return index
    return -1


def _final_text(message: Any) -> str:
    """Extract plain text from the final agent message."""
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        ]
        return "\n".join(p for p in parts if p).strip()
    return str(content).strip()
