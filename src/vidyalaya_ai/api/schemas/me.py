"""Schemas for authenticated user-owned resources."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


SUPPORTED_BOARDS = {"scert_odisha"}


class ProfileRequest(BaseModel):
    """Create or update a student profile."""

    board: str = Field(..., min_length=1)
    class_no: int = Field(..., ge=1, le=12)
    preferred_language: str = Field(..., min_length=2, max_length=8)
    school_name: str | None = Field(default=None, max_length=200)

    @field_validator("board", "preferred_language", "school_name", mode="before")
    @classmethod
    def strip_text(cls, value):
        """Normalize profile text inputs."""
        if value is None or not isinstance(value, str):
            return value
        cleaned = value.strip()
        return cleaned or None

    @field_validator("board")
    @classmethod
    def validate_board(cls, value: str) -> str:
        """Require a supported board."""
        if value not in SUPPORTED_BOARDS:
            raise ValueError(f"board must be one of: {', '.join(sorted(SUPPORTED_BOARDS))}")
        return value


class ProfileResponse(BaseModel):
    """Student profile response."""

    board: str
    class_no: int
    preferred_language: str
    school_name: str | None = None
    onboarding_completed: bool
    created_at: datetime
    updated_at: datetime


class UsageResponse(BaseModel):
    """Daily usage response."""

    date_ist: str
    used: int
    limit: int | None
    remaining: int | None
    unlimited: bool
