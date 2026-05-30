"""Authenticated user profile routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from vidyalaya_ai.api.dependencies import get_current_user
from vidyalaya_ai.api.schemas.me import ProfileRequest, ProfileResponse, UsageResponse
from vidyalaya_ai.auth.models import AuthenticatedUser
from vidyalaya_ai.quota.service import get_usage
from vidyalaya_ai.users.repository import get_profile, upsert_profile


router = APIRouter(prefix="/me", tags=["me"])


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
    usage = await get_usage(firebase_uid, "learnassist", current_user)
    return UsageResponse(
        date_ist=usage.date_ist,
        used=usage.used,
        limit=usage.limit,
        remaining=usage.remaining,
        unlimited=usage.unlimited,
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
