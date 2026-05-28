"""Authentication schemas."""

from __future__ import annotations

from vidyalaya_ai.auth.models import AuthenticatedUser


class AuthenticatedUserResponse(AuthenticatedUser):
    """Authenticated user response."""
