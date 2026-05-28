"""Authentication data models."""

from __future__ import annotations

from pydantic import BaseModel


class AuthenticatedUser(BaseModel):
    """Verified Firebase user identity."""

    user_id: str
    email: str | None = None
    name: str | None = None
