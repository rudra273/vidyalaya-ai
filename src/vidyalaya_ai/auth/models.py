"""Authentication data models."""

from __future__ import annotations

from pydantic import BaseModel


class AuthenticatedUser(BaseModel):
    """Verified Firebase user identity."""

    user_id: str
    firebase_uid: str | None = None
    mongo_id: str | None = None
    email: str | None = None
    name: str | None = None
    role: str = "student"
    status: str = "active"
    quota_override: str | int | None = None
