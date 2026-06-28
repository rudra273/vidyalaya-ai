"""LearnAssist routes."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends
from sse_starlette.sse import EventSourceResponse

from vidyalaya_ai.agents import (
    AGENT,
    AgentTimeout,
    AgentUnavailable,
    LearnAssistContext,
    build_thread_id,
    reset_thread_checkpoint,
    run_learnassist,
    run_learnassist_stream,
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
from vidyalaya_ai.quota.service import UsageView, check_and_increment
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


async def _prepare_turn(
    payload: LearnAssistChatRequest,
    current_user: AuthenticatedUser,
) -> tuple[str, str, UsageView]:
    """Run the pre-answer steps shared by the streaming and non-streaming chat
    endpoints: resolve the thread, expire a stale session, and spend quota.

    Returns ``(firebase_uid, thread_id, usage)``. Quota is spent *before* any
    answer begins, so an over-quota request raises :class:`QuotaExceeded` (429)
    cleanly instead of mid-stream. Must run before streaming starts.
    """
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
    return firebase_uid, thread_id, usage


def _usage_response(usage: UsageView) -> UsageResponse:
    """Map the quota service view onto the public usage schema."""
    return UsageResponse(
        date_ist=usage.date_ist,
        used=usage.used,
        limit=usage.limit,
        remaining=usage.remaining,
        unlimited=usage.unlimited,
    )


@router.post("/chat", response_model=LearnAssistChatResponse)
async def learnassist_chat(
    payload: LearnAssistChatRequest,
    background_tasks: BackgroundTasks,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> LearnAssistChatResponse:
    """Answer a student query with LearnAssist."""
    firebase_uid, thread_id, usage = await _prepare_turn(payload, current_user)
    result = await run_learnassist(
        payload.message,
        LearnAssistContext(
            firebase_uid=firebase_uid,
            thread_id=thread_id,
            board=payload.board,
            class_no=payload.class_no,
            subject=payload.subject,
            language=payload.language,
        ),
        thread_id=thread_id,
        provider=current_user.plan_provider,
        model=current_user.plan_model,
        image_base64=payload.image_base64,
        image_media_type=payload.image_media_type,
    )

    # Store the student's text; fall back to a marker when only an image was sent
    # so history rows are never empty. Raw image bytes are never persisted.
    persisted_question = payload.message or "[Image shared]"

    # Persist history + usage after the response is sent (Phases 3 & 4): never
    # adds latency, and a failed write can't fail an answer already produced.
    background_tasks.add_task(
        persist_turn,
        firebase_uid=firebase_uid,
        thread_id=thread_id,
        agent=AGENT,
        question=persisted_question,
        answer=result.answer,
        citations=result.citations,
        usage=result.usage,
    )

    return LearnAssistChatResponse(
        answer=result.answer,
        citations=result.citations,
        retrieval=result.retrieval,
        tools_used=result.tools_used,
        usage=_usage_response(usage),
        context_blocks=result.context_blocks if payload.debug else None,
    )


@router.post("/chat/stream")
async def learnassist_chat_stream(
    payload: LearnAssistChatRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> EventSourceResponse:
    """Answer a student query with LearnAssist, streamed as Server-Sent Events.

    Same inputs and pre-flight (auth, session reset, quota) as ``/chat``; the
    answer is streamed instead of bundled. Frames:
      - ``event: tool``  – ``{"tool", "status"}`` progress hint per tool call.
      - ``event: token`` – ``{"text"}`` a piece of the answer.
      - ``event: done``  – ``{"citations", "retrieval", "tools_used", "usage",
        ["context_blocks"]}`` final metadata (citations/usage are only known once
        generation finishes, so they ride here, not with the first bytes).
      - ``event: error`` – ``{"code", "message"}`` if generation fails mid-stream.

    Pre-flight errors (401/429/...) are returned as normal JSON before any frame
    is sent. Once streaming has begun the status is already 200, so a failure
    becomes an ``error`` frame instead of an HTTP error code.
    """
    firebase_uid, thread_id, usage = await _prepare_turn(payload, current_user)
    context = LearnAssistContext(
        firebase_uid=firebase_uid,
        thread_id=thread_id,
        board=payload.board,
        class_no=payload.class_no,
        subject=payload.subject,
        language=payload.language,
    )

    async def event_stream():
        done: dict | None = None
        try:
            async for ev in run_learnassist_stream(
                payload.message,
                context,
                thread_id=thread_id,
                provider=current_user.plan_provider,
                model=current_user.plan_model,
                image_base64=payload.image_base64,
                image_media_type=payload.image_media_type,
            ):
                kind = ev["type"]
                if kind == "token":
                    yield {"event": "token", "data": json.dumps({"text": ev["text"]})}
                elif kind == "tool":
                    yield {
                        "event": "tool",
                        "data": json.dumps({"tool": ev["tool"], "status": ev["status"]}),
                    }
                elif kind == "done":
                    done = ev
                    frame = {
                        "citations": ev["citations"],
                        "retrieval": ev["retrieval"],
                        "tools_used": ev["tools_used"],
                        "usage": _usage_response(usage).model_dump(),
                    }
                    if payload.debug:
                        frame["context_blocks"] = ev["context_blocks"]
                    yield {"event": "done", "data": json.dumps(frame)}
        except AgentTimeout:
            yield {
                "event": "error",
                "data": json.dumps(
                    {
                        "code": "assistant_timeout",
                        "message": "That took too long, please try again.",
                    }
                ),
            }
        except AgentUnavailable:
            yield {
                "event": "error",
                "data": json.dumps(
                    {
                        "code": "assistant_unavailable",
                        "message": "Assistant is busy, please try again.",
                    }
                ),
            }
        except Exception:
            logger.exception("LearnAssist stream error thread=%s", thread_id)
            yield {
                "event": "error",
                "data": json.dumps(
                    {
                        "code": "service_error",
                        "message": "Unable to process the request right now.",
                    }
                ),
            }

        # Persist only a completed turn (we have the full answer + usage). The
        # quota was already spent in _prepare_turn. A half-stream (client
        # disconnect or mid-stream error) leaves no row, matching the
        # non-streaming path's "never persist a turn that didn't finish".
        #
        # This runs after the try/except completes normally - deliberately NOT in
        # a finally. If the client disconnects mid-stream, GeneratorExit unwinds
        # through the suspended yield and this code never runs, so we never await a
        # DB write while the async generator is being torn down (which would raise
        # "async generator ignored GeneratorExit").
        if done is not None:
            # Store the student's text; fall back to a marker when only an image
            # was sent so history rows are never empty.
            persisted_question = payload.message or "[Image shared]"
            await persist_turn(
                firebase_uid=firebase_uid,
                thread_id=thread_id,
                agent=AGENT,
                question=persisted_question,
                answer=done["answer"],
                citations=done["citations"],
                usage=done["usage"],
            )

    return EventSourceResponse(event_stream())


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
