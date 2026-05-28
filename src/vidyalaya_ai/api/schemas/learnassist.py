"""LearnAssist schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from vidyalaya_ai.api.schemas.me import UsageResponse


class LearnAssistChatRequest(BaseModel):
    """LearnAssist chat request."""

    query: str = Field(..., min_length=1, max_length=2000)
    board: str = Field(..., min_length=1)
    class_no: int = Field(..., ge=1, le=12)
    subject: str | None = Field(default=None, max_length=64)
    language: str | None = None
    debug: bool = False

    @field_validator("query", "board", "subject", "language", mode="before")
    @classmethod
    def strip_optional_text(cls, value):
        """Strip strings and convert empty optional strings to None."""
        if value is None:
            return None
        if not isinstance(value, str):
            return value

        cleaned = value.strip()
        return cleaned or None

    @field_validator("board")
    @classmethod
    def validate_board(cls, value: str) -> str:
        """Require a known board."""
        if value != "scert_odisha":
            raise ValueError("board must be one of: scert_odisha")
        return value

    @field_validator("subject")
    @classmethod
    def normalize_subject(cls, value: str | None) -> str | None:
        """Normalize subject filters for retrieval."""
        return value.lower() if value else None


class LearnAssistChatResponse(BaseModel):
    """LearnAssist chat response."""

    answer: str
    citations: list[dict[str, Any]]
    retrieval: dict[str, Any]
    usage: UsageResponse | None = None
    context_blocks: list[dict[str, Any]] | None = None
