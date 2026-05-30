"""Authenticated user profile routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from vidyalaya_ai.api.dependencies import get_current_user
from vidyalaya_ai.api.schemas.me import (
    HistoryMessage,
    HistoryResponse,
    ProfileRequest,
    ProfileResponse,
    UsageResponse,
)
from vidyalaya_ai.auth.models import AuthenticatedUser
from vidyalaya_ai.chatlog import get_history
from vidyalaya_ai.quota.service import get_usage
from vidyalaya_ai.users.repository import get_profile, upsert_profile


router = APIRouter(prefix="/me", tags=["me"])
AGENT = "learnassist"


@router.get("/profile", response_model=ProfileResponse)
async def read_profile(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ProfileResponse:
    """Return the authenticated student's profile."""
    firebase_uid = current_user.firebase_uid or current_user.user_id
    profile = await get_profile(firebase_uid)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found.",
        )
    return ProfileResponse(
        board=profile.board,
        class_no=profile.class_no,
        preferred_language=profile.preferred_language,
        school_name=profile.school_name,
        onboarding_completed=profile.onboarding_completed,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.get("/usage", response_model=UsageResponse)
async def read_usage(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> UsageResponse:
    """Return current LearnAssist usage without spending quota."""
    firebase_uid = current_user.firebase_uid or current_user.user_id
    usage = await get_usage(firebase_uid, AGENT, current_user)
    return UsageResponse(
        date_ist=usage.date_ist,
        used=usage.used,
        limit=usage.limit,
        remaining=usage.remaining,
        unlimited=usage.unlimited,
    )


@router.get("/history", response_model=HistoryResponse)
async def read_history(
    limit: int = Query(default=30, ge=1, le=100),
    before: int | None = Query(
        default=None,
        ge=1,
        description="Message id cursor; returns messages older than this id.",
    ),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> HistoryResponse:
    """Return the student's chat history (oldest -> newest) for scroll-back.

    Single continuous chat per student, so no thread param. Page backwards by
    passing the returned ``next_before`` as ``before`` to load older messages.
    """
    firebase_uid = current_user.firebase_uid or current_user.user_id
    rows = await get_history(
        firebase_uid=firebase_uid,
        agent=AGENT,
        limit=limit,
        before_id=before,
    )
    # A full page implies there may be older messages; the oldest id in this page
    # (rows are chronological) is the cursor for the previous page.
    next_before = rows[0].id if len(rows) == limit else None
    return HistoryResponse(
        messages=[
            HistoryMessage(
                id=r.id,
                role=r.role,
                content=r.content,
                citations=r.citations,
                created_at=r.created_at,
            )
            for r in rows
        ],
        next_before=next_before,
    )


@router.put("/profile", response_model=ProfileResponse)
async def write_profile(
    payload: ProfileRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ProfileResponse:
    """Create or update the authenticated student's profile."""
    firebase_uid = current_user.firebase_uid or current_user.user_id
    if current_user.db_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authenticated user is missing database identity.",
        )

    profile = await upsert_profile(
        firebase_uid=firebase_uid,
        user_id=current_user.db_id,
        board=payload.board,
        class_no=payload.class_no,
        preferred_language=payload.preferred_language,
        school_name=payload.school_name,
    )
    return ProfileResponse(
        board=profile.board,
        class_no=profile.class_no,
        preferred_language=profile.preferred_language,
        school_name=profile.school_name,
        onboarding_completed=profile.onboarding_completed,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )
