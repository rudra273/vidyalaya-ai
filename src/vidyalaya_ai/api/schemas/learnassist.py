"""LearnAssist schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class LearnAssistChatRequest(BaseModel):
    """LearnAssist chat request."""

    query: str = Field(..., min_length=1)
    board: str = Field(..., min_length=1)
    class_no: int = Field(..., gt=0)
    subject: str | None = None
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


class LearnAssistChatResponse(BaseModel):
    """LearnAssist chat response."""

    answer: str
    citations: list[dict[str, Any]]
    retrieval: dict[str, Any]
    context_blocks: list[dict[str, Any]] | None = None
