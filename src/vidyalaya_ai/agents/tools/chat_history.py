"""LangChain tool that reads a student's earlier conversation from storage.

The agent's working memory (the LangGraph checkpoint) is reset after a period of
inactivity, and even within a session only the last few messages are sent to the
model. The full conversation, however, lives permanently in the ``messages``
table. This tool lets the agent fetch that history on demand when the context it
needs isn't in the messages it can currently see.
"""

from __future__ import annotations

import logging

from langchain.tools import ToolRuntime, tool

from vidyalaya_ai.agents.learnassist.context import AGENT, LearnAssistContext
from vidyalaya_ai.chatlog import MessageView, get_history


logger = logging.getLogger("vidyalaya_ai.agents")

CHAT_HISTORY_TOOL_NAME = "get_chat_history"

# Model-facing default and hard cap on how many messages to pull back. The cap
# bounds token cost no matter what the model asks for.
_DEFAULT_LIMIT = 10
_MAX_LIMIT = 20

# Human-readable role labels for the transcript the model reads.
_ROLE_LABELS = {"human": "Student", "ai": "You"}


@tool
async def get_chat_history(
    runtime: ToolRuntime[LearnAssistContext],
    limit: int = _DEFAULT_LIMIT,
) -> str:
    """Retrieve this student's earlier messages with you, for the current subject.

    Use this ONLY when the student refers to something from earlier in your
    conversation that is NOT visible in the messages above — for example they say
    "continue", "what did we discuss", or "explain that again" after a break — and
    you cannot answer without that earlier context. Do NOT call it for greetings,
    brand-new questions, or when the needed context is already visible above.

    Args:
        limit: How many of the most recent messages to fetch (default 10, max 20).
            The result is the conversation oldest-first.
    """
    ctx = runtime.context
    n = max(1, min(limit, _MAX_LIMIT))
    logger.info(
        "get_chat_history thread=%s limit=%d", ctx.thread_id, n
    )

    rows = await get_history(
        firebase_uid=ctx.firebase_uid,
        agent=AGENT,
        limit=n,
        thread_id=ctx.thread_id,
    )
    if not rows:
        return "(no earlier conversation found)"
    return _format_transcript(rows)


def _format_transcript(rows: list[MessageView]) -> str:
    """Render history rows (oldest -> newest) as a plain Student/You transcript."""
    lines = []
    for row in rows:
        label = _ROLE_LABELS.get(row.role, row.role)
        lines.append(f"{label}: {row.content}")
    return "\n".join(lines)
