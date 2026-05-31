"""Authenticated user profile routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from vidyalaya_ai.agents import build_thread_id
from vidyalaya_ai.api.dependencies import get_current_user
from vidyalaya_ai.api.schemas.learnassist import (
    GENERAL_SUBJECT,
    KNOWN_CHANNELS,
    KNOWN_SUBJECTS,
    LEARN_ASSIST_CHANNEL,
)
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
    board: str = Query(..., min_length=1, description="Same board the chat used."),
    class_no: int = Query(..., ge=1, le=12, description="Same class the chat used."),
    limit: int = Query(default=30, ge=1, le=100),
    before: int | None = Query(
        default=None,
        ge=1,
        description="Message id cursor; returns messages older than this id.",
    ),
    channel: str = Query(
        default=LEARN_ASSIST_CHANNEL,
        description="Agent/surface. Currently only '" + LEARN_ASSIST_CHANNEL + "'.",
    ),
    subject: str | None = Query(
        default=None,
        description="Academic subject to load history for, or omit/null for the "
        "cross-subject 'general' conversation. One of: "
        + ", ".join(sorted(KNOWN_SUBJECTS)),
    ),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> HistoryResponse:
    """Return one conversation's chat history (oldest -> newest) for scroll-back.

    History is scoped to the same ``(channel, board, class, subject)`` thread the
    chat endpoint wrote under, so each subject (or the general conversation) shows
    only its own messages. The client passes the same selectors it sends on chat, so
    the thread id is rebuilt with no extra DB read. Page backwards by passing the
    returned ``next_before`` as ``before`` to load older messages.
    """
    firebase_uid = current_user.firebase_uid or current_user.user_id

    normalized_channel = channel.strip().lower() or LEARN_ASSIST_CHANNEL
    if normalized_channel not in KNOWN_CHANNELS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="channel must be one of: " + ", ".join(sorted(KNOWN_CHANNELS)),
        )

    # Unknown/empty subject -> the general (cross-subject) thread, mirroring how the
    # chat request normalizes subject.
    normalized = (subject or "").strip().lower()
    thread_subject = normalized if normalized in KNOWN_SUBJECTS else GENERAL_SUBJECT

    # Rebuild the exact thread id the chat endpoint wrote under, from the same
    # request inputs the client already has - no profile lookup on this path.
    thread_id = build_thread_id(
        channel=normalized_channel,
        firebase_uid=firebase_uid,
        board=board,
        class_no=class_no,
        subject=thread_subject,
    )

    rows = await get_history(
        firebase_uid=firebase_uid,
        agent=AGENT,
        limit=limit,
        before_id=before,
        thread_id=thread_id,
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
