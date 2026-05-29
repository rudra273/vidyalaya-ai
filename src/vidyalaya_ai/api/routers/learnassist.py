"""LearnAssist routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from vidyalaya_ai.agents import LearnAssistContext, run_learnassist
from vidyalaya_ai.api.dependencies import get_current_user
from vidyalaya_ai.api.schemas.learnassist import LearnAssistChatRequest, LearnAssistChatResponse
from vidyalaya_ai.api.schemas.me import UsageResponse
from vidyalaya_ai.auth.models import AuthenticatedUser
from vidyalaya_ai.quota.service import check_and_increment


logger = logging.getLogger("vidyalaya_ai.api")
router = APIRouter(prefix="/learnassist", tags=["learnassist"])


@router.post("/chat", response_model=LearnAssistChatResponse)
async def learnassist_chat(
    payload: LearnAssistChatRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> LearnAssistChatResponse:
    """Answer a student query with LearnAssist."""
    firebase_uid = current_user.firebase_uid or current_user.user_id
    logger.info(
        "LearnAssist request user=%s board=%s class=%s subject=%s debug=%s",
        firebase_uid,
        payload.board,
        payload.class_no,
        payload.subject,
        payload.debug,
    )

    usage = await check_and_increment(firebase_uid, "learnassist", current_user)
    result = await run_learnassist(
        payload.message,
        LearnAssistContext(
            board=payload.board,
            class_no=payload.class_no,
            subject=payload.subject,
            language=payload.language,
        ),
        thread_id=f"learnassist:{firebase_uid}",
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
