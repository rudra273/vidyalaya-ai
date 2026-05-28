"""Pydantic models for user-owned MongoDB documents."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


QuotaOverride = Literal["unlimited"] | int | None


class UserDoc(BaseModel):
    """Application user document."""

    id: str = Field(alias="_id")
    firebase_uid: str
    email: str | None = None
    display_name: str | None = None
    role: Literal["student", "admin"] = "student"
    status: Literal["active", "suspended", "deleted"] = "active"
    quota_override: QuotaOverride = None
    created_at: datetime
    last_seen_at: datetime
    schema_version: int = 1


class StudentProfileDoc(BaseModel):
    """Student onboarding/profile document."""

    id: str = Field(alias="_id")
    user_id: str
    firebase_uid: str
    board: str
    class_no: int
    preferred_language: str
    school_name: str | None = None
    onboarding_completed: bool = True
    created_at: datetime
    updated_at: datetime
    schema_version: int = 1
