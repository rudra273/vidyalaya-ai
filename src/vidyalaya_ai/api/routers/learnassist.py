"""LearnAssist routes."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends

from vidyalaya_ai.agents import (
    AGENT,
    LearnAssistContext,
    build_thread_id,
    reset_thread_checkpoint,
    run_learnassist,
)
from vidyalaya_ai.api.dependencies import get_current_user
from vidyalaya_ai.api.schemas.learnassist import (
    LearnAssistChatRequest,
    LearnAssistChatResponse,
    MemoryResetRequest,
    MemoryResetResponse,
)
from vidyalaya_ai.api.schemas.me import UsageResponse
from vidyalaya_ai.auth.models import AuthenticatedUser
from vidyalaya_ai.chatlog import get_last_message_at, persist_turn
from vidyalaya_ai.quota.service import check_and_increment
from vidyalaya_ai.users.repository import get_preferences

logger = logging.getLogger("vidyalaya_ai.api")
router = APIRouter(prefix="/learnassist", tags=["learnassist"])


def _session_timeout_minutes() -> int:
    """Return the inactivity timeout in minutes; non-positive disables reset."""
    raw = os.getenv("LEARNASSIST_SESSION_TIMEOUT_MINUTES", "30").strip()
    try:
        return int(raw)
    except ValueError:
        logger.warning(
            "Invalid LEARNASSIST_SESSION_TIMEOUT_MINUTES=%r; using default 30",
            raw,
        )
        return 30


def should_reset_session(
    last_message_at: datetime | None,
    now: datetime,
    timeout_minutes: int,
) -> bool:
    """Return whether a thread's checkpoint should be reset for inactivity."""
    if timeout_minutes <= 0 or last_message_at is None:
        return False
    return (now - last_message_at) > timedelta(minutes=timeout_minutes)


@router.post("/chat", response_model=LearnAssistChatResponse)
async def learnassist_chat(
    payload: LearnAssistChatRequest,
    background_tasks: BackgroundTasks,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> LearnAssistChatResponse:
    """Answer a student query with LearnAssist."""
    firebase_uid = current_user.firebase_uid or current_user.user_id
    # Memory is scoped per (channel, board, class, subject) - see build_thread_id -
    # so subjects never leak into each other and a class/board change starts fresh.
    # `channel` is the agent/surface; `thread_subject` is the subject or "general".
    thread_id = build_thread_id(
        channel=payload.channel,
        firebase_uid=firebase_uid,
        board=payload.board,
        class_no=payload.class_no,
        subject=payload.thread_subject,
    )
    logger.info(
        "LearnAssist request user=%s channel=%s board=%s class=%s subject=%s debug=%s",
        firebase_uid,
        payload.channel,
        payload.board,
        payload.class_no,
        payload.subject,
        payload.debug,
    )

    # User preference takes priority over the env default.
    # enabled=False means the student explicitly disabled auto-reset → timeout=0.
    # No profile yet → env default applies (allows global kill-switch via env=0).
    prefs = await get_preferences(firebase_uid)
    if prefs.has_preference:
        timeout = prefs.memory_reset_minutes if prefs.memory_reset_enabled else 0
    else:
        timeout = _session_timeout_minutes()

    if timeout > 0:
        last_message_at = await get_last_message_at(thread_id=thread_id)
        now = datetime.now(timezone.utc)
        if should_reset_session(last_message_at, now, timeout):
            gap = now - last_message_at
            logger.info(
                "Session expired (%.0f min inactive); resetting checkpoint thread=%s",
                gap.total_seconds() / 60,
                thread_id,
            )
            await reset_thread_checkpoint(thread_id)

    usage = await check_and_increment(firebase_uid, AGENT, current_user)
    result = await run_learnassist(
        payload.message,
        LearnAssistContext(
            board=payload.board,
            class_no=payload.class_no,
            subject=payload.subject,
            language=payload.language,
        ),
        thread_id=thread_id,
        provider=current_user.plan_provider,
        model=current_user.plan_model,
    )

    # Persist history + usage after the response is sent (Phases 3 & 4): never
    # adds latency, and a failed write can't fail an answer already produced.
    background_tasks.add_task(
        persist_turn,
        firebase_uid=firebase_uid,
        thread_id=thread_id,
        agent=AGENT,
        question=payload.message,
        answer=result.answer,
        citations=result.citations,
        usage=result.usage,
    )

    return LearnAssistChatResponse(
        answer=result.answer,
        citations=result.citations,
        retrieval=result.retrieval,
        usage=UsageResponse(
            date_ist=usage.date_ist,
            used=usage.used,
            limit=usage.limit,
            remaining=usage.remaining,
            unlimited=usage.unlimited,
        ),
        context_blocks=result.context_blocks if payload.debug else None,
    )


@router.post("/memory/reset", response_model=MemoryResetResponse)
async def reset_memory(
    payload: MemoryResetRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> MemoryResetResponse:
    """Clear the agent's working memory for one thread (manual 'Start fresh').

    Deletes the LangGraph checkpoint for the thread reconstructed from the
    request selectors. The permanent chat history in ``messages`` is not
    affected — the student still sees their conversation in the UI.
    """
    firebase_uid = current_user.firebase_uid or current_user.user_id
    thread_id = build_thread_id(
        channel=payload.channel,
        firebase_uid=firebase_uid,
        board=payload.board,
        class_no=payload.class_no,
        subject=payload.thread_subject,
    )
    logger.info(
        "Manual memory reset user=%s thread=%s",
        firebase_uid,
        thread_id,
    )
    await reset_thread_checkpoint(thread_id)
    return MemoryResetResponse(reset=True)
