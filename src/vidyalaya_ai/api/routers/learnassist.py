"""LearnAssist routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends

from vidyalaya_ai.agents import AGENT, LearnAssistContext, build_thread_id, run_learnassist
from vidyalaya_ai.api.dependencies import get_current_user
from vidyalaya_ai.api.schemas.learnassist import LearnAssistChatRequest, LearnAssistChatResponse
from vidyalaya_ai.api.schemas.me import UsageResponse
from vidyalaya_ai.auth.models import AuthenticatedUser
from vidyalaya_ai.chatlog import persist_turn
from vidyalaya_ai.quota.service import check_and_increment


logger = logging.getLogger("vidyalaya_ai.api")
router = APIRouter(prefix="/learnassist", tags=["learnassist"])


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
