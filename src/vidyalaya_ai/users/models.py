"""DTOs returned by the users repository.

These are plain Pydantic carriers over the SQLAlchemy rows, kept as the
repository's return contract so routers/dependencies stay unchanged across the
Mongo -> Postgres migration.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


QuotaOverride = Literal["unlimited"] | int | None


class UserDoc(BaseModel):
    """Application user record."""

    id: str
    firebase_uid: str
    email: str | None = None
    display_name: str | None = None
    role: Literal["student", "admin"] = "student"
    status: Literal["active", "suspended", "deleted"] = "active"
    quota_override: QuotaOverride = None
    created_at: datetime
    last_seen_at: datetime


class StudentProfileDoc(BaseModel):
    """Student onboarding/profile record."""

    id: str
    user_id: str
    firebase_uid: str
    board: str
    class_no: int
    preferred_language: str
    school_name: str | None = None
    onboarding_completed: bool = True
    created_at: datetime
    updated_at: datetime


class PreferencesDoc(BaseModel):
    """Session memory preferences for a student.

    ``has_preference`` is False when the student has no profile yet — the caller
    should fall back to the global env default rather than treating the defaults
    here as the student's explicit choice.
    """

    memory_reset_enabled: bool = True
    memory_reset_minutes: int = 30
    has_preference: bool = True
