"""LearnAssist routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from vidyalaya_ai.agents import LearnAssistInput, answer_with_learnassist
from vidyalaya_ai.api.dependencies import get_current_user
from vidyalaya_ai.api.schemas.learnassist import LearnAssistChatRequest, LearnAssistChatResponse
from vidyalaya_ai.auth.models import AuthenticatedUser


logger = logging.getLogger("vidyalaya_ai.api")
router = APIRouter(prefix="/learnassist", tags=["learnassist"])


@router.post("/chat", response_model=LearnAssistChatResponse)
def learnassist_chat(
    payload: LearnAssistChatRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    """Answer a student query with LearnAssist."""
    logger.info(
        "LearnAssist request user=%s board=%s class=%s subject=%s debug=%s",
        current_user.user_id,
        payload.board,
        payload.class_no,
        payload.subject,
        payload.debug,
    )
    result = answer_with_learnassist(
        LearnAssistInput(
            query=payload.query,
            board=payload.board,
            class_no=payload.class_no,
            subject=payload.subject,
            language=payload.language,
        )
    )

    if not payload.debug:
        result.pop("context_blocks", None)

    return result
