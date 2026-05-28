"""Authentication routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from vidyalaya_ai.api.dependencies import get_current_user
from vidyalaya_ai.api.schemas.auth import AuthenticatedUserResponse
from vidyalaya_ai.auth.models import AuthenticatedUser


router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=AuthenticatedUserResponse)
def me(current_user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    """Return the authenticated user."""
    return current_user
