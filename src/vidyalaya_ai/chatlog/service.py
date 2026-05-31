"""Chat history + usage-event persistence.

``persist_turn`` is the single post-response write path shared by Phase 3
(permanent ``messages`` for scroll-back) and Phase 4 (``usage_events``
analytics). It is called from a FastAPI BackgroundTask after the response is
sent, so it never adds latency to the chat turn. It also swallows and logs its
own errors: a lost history/analytics row must never turn a successful answer the
student already received into a failure.

``get_history`` powers ``GET /me/history`` — paginated scroll-back, returned
oldest -> newest.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select

from vidyalaya_ai.agents import TurnUsage
from vidyalaya_ai.db.engine import session_scope
from vidyalaya_ai.db.models import Message, UsageEvent


logger = logging.getLogger("vidyalaya_ai.api")


@dataclass(frozen=True)
class MessageView:
    """API-facing chat history row."""

    id: int
    role: str
    content: str
    citations: list[dict[str, Any]] | None
    created_at: datetime


async def persist_turn(
    *,
    firebase_uid: str,
    thread_id: str,
    agent: str,
    question: str,
    answer: str,
    citations: list[dict[str, Any]] | None,
    usage: TurnUsage,
) -> None:
    """Persist the human + AI messages and the turn's usage event.

    Best-effort: any failure is logged and swallowed so a background write never
    crashes the request that already returned the answer.
    """
    try:
        async with session_scope() as session:
            session.add(
                Message(
                    firebase_uid=firebase_uid,
                    thread_id=thread_id,
                    agent=agent,
                    role="human",
                    content=question,
                    citations=None,
                )
            )
            session.add(
                Message(
                    firebase_uid=firebase_uid,
                    thread_id=thread_id,
                    agent=agent,
                    role="ai",
                    content=answer,
                    citations=citations or None,
                )
            )
            session.add(
                UsageEvent(
                    firebase_uid=firebase_uid,
                    agent=agent,
                    model=usage.model,
                    llm_calls=usage.llm_calls,
                    tool_calls=usage.tool_calls,
                    tokens_input=usage.tokens_input,
                    tokens_output=usage.tokens_output,
                    tokens_total=usage.tokens_total,
                )
            )
            await session.commit()
    except Exception:
        logger.exception(
            "Failed to persist chat turn uid=%s thread=%s", firebase_uid, thread_id
        )


async def get_history(
    *,
    firebase_uid: str,
    agent: str,
    limit: int,
    before_id: int | None = None,
    thread_id: str | None = None,
) -> list[MessageView]:
    """Return a page of the student's chat history, oldest -> newest.

    Pages backwards from ``before_id`` (a message id; exclusive) for infinite
    scroll-back: fetch the newest ``limit`` rows older than the cursor, then
    return them in chronological order for display.

    When ``thread_id`` is given, history is scoped to that single channel/thread so
    each tab shows only its own messages (screen = the model's per-channel memory).
    """
    async with session_scope() as session:
        stmt = (
            select(Message)
            .where(Message.firebase_uid == firebase_uid, Message.agent == agent)
            .order_by(Message.id.desc())
            .limit(limit)
        )
        if thread_id is not None:
            stmt = stmt.where(Message.thread_id == thread_id)
        if before_id is not None:
            stmt = stmt.where(Message.id < before_id)
        rows = (await session.execute(stmt)).scalars().all()

    rows.reverse()  # newest-first query -> chronological for the client
    return [
        MessageView(
            id=row.id,
            role=row.role,
            content=row.content,
            citations=row.citations,
            created_at=row.created_at,
        )
        for row in rows
    ]
