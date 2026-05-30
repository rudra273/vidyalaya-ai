"""Entry point for running the LearnAssist agent on a single chat turn."""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from vidyalaya_ai.agents.exceptions import AgentTimeout, AgentUnavailable
from vidyalaya_ai.agents.learnassist.agent import get_agent_for
from vidyalaya_ai.agents.learnassist.context import LearnAssistContext
from vidyalaya_ai.agents.learnassist.prompt import build_citations, build_retrieval_metadata
from vidyalaya_ai.agents.learnassist.tools import SEARCH_TOOL_NAME


logger = logging.getLogger("vidyalaya_ai.agents")

# Hard ceiling for a single chat turn. Generous enough for retrieval + a couple
# of model calls + retry backoff, but bounded so a stuck provider returns a 504
# instead of holding the request (and a worker) open indefinitely.
_TURN_TIMEOUT_SECONDS = float(os.getenv("LEARNASSIST_TURN_TIMEOUT", "90"))


@dataclass
class TurnUsage:
    """Per-turn LLM/tool accounting, summed across the turn's AI messages."""

    llm_calls: int = 0
    tool_calls: int = 0
    tokens_input: int = 0
    tokens_output: int = 0
    tokens_total: int = 0
    model: str | None = None


@dataclass
class LearnAssistResult:
    """Result of a single LearnAssist turn."""

    answer: str
    citations: list[dict[str, Any]] = field(default_factory=list)
    retrieval: dict[str, Any] = field(default_factory=dict)
    context_blocks: list[dict[str, Any]] = field(default_factory=list)
    usage: TurnUsage = field(default_factory=TurnUsage)


async def run_learnassist(
    message: str,
    context: LearnAssistContext,
    *,
    thread_id: str,
    provider: str | None = None,
    model: str | None = None,
) -> LearnAssistResult:
    """Run one chat turn and return the answer with citations and metadata.

    The checkpointer stores only ``messages``. Per-turn inputs (board, class,
    subject, language) come from ``context`` each call, and retrieval output is
    read from this turn's search_textbook ToolMessage - so nothing leaks across
    turns.

    Failures are normalized for the API: a turn that exceeds the time budget
    raises :class:`AgentTimeout` (504), and a model/provider failure that
    survives the agent's retry middleware raises :class:`AgentUnavailable`
    (503). The full underlying error is logged server-side only.
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
    try:
        state = await asyncio.wait_for(
            agent.ainvoke(
                {"messages": [HumanMessage(message)]},
                context=context,
                config=config,
            ),
            timeout=_TURN_TIMEOUT_SECONDS,
        )
    except (asyncio.TimeoutError, TimeoutError) as exc:
        logger.warning("LearnAssist turn timed out thread=%s", thread_id)
        raise AgentTimeout("LearnAssist turn timed out.") from exc
    except Exception as exc:
        # Reached only after the agent's retry middleware has exhausted retries.
        # Treat as a provider/model outage and surface a friendly 503.
        logger.exception("LearnAssist turn failed thread=%s", thread_id)
        raise AgentUnavailable("LearnAssist is temporarily unavailable.") from exc

    messages = state["messages"]
    answer = _final_text(messages[-1])
    blocks, retrieval = _retrieval_from_current_turn(messages)

    return LearnAssistResult(
        answer=answer,
        citations=build_citations(blocks, answer),
        retrieval=retrieval,
        context_blocks=blocks,
        usage=_usage_from_current_turn(messages),
    )


def _usage_from_current_turn(messages: list[Any]) -> TurnUsage:
    """Sum token/call usage from the AI + tool messages of the current turn.

    Only messages after the last human turn are counted, so prior turns kept in
    the checkpoint history are never double-counted. Token counts come from each
    AIMessage's ``usage_metadata`` (Gemini and OpenRouter both populate it).
    """
    last_human = _last_index(messages, HumanMessage)
    usage = TurnUsage()
    for message in messages[last_human + 1 :]:
        if isinstance(message, AIMessage):
            usage.llm_calls += 1
            if getattr(message, "tool_calls", None):
                usage.tool_calls += len(message.tool_calls)
            meta = getattr(message, "usage_metadata", None) or {}
            usage.tokens_input += int(meta.get("input_tokens", 0) or 0)
            usage.tokens_output += int(meta.get("output_tokens", 0) or 0)
            usage.tokens_total += int(meta.get("total_tokens", 0) or 0)
            model = (getattr(message, "response_metadata", {}) or {}).get("model_name")
            if model:
                usage.model = model
    return usage


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
