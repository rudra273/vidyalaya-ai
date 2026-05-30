"""Authentication data models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator


class AuthenticatedUser(BaseModel):
    """Verified Firebase user identity."""

    user_id: str
    firebase_uid: str | None = None
    # Internal DB primary key (Postgres users.id); distinct from the Firebase
    # user_id above, which is the external identity.
    db_id: str | None = None
    email: str | None = None
    name: str | None = None
    role: str = "student"
    status: str = "active"
    quota_override: Literal["unlimited"] | int | None = None

    @field_validator("quota_override", mode="before")
    @classmethod
    def reject_bool_override(cls, value: object) -> object:
        """Treat a stray boolean override as 'no override' instead of int 1/0."""
        if isinstance(value, bool):
            return None
        return value
