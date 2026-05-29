"""LearnAssist schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from vidyalaya_ai.api.schemas.me import UsageResponse


# Subjects present in the indexed textbook data. Anything else is treated as
# "no subject filter" (search across all subjects) rather than filtering to a
# value that matches nothing.
KNOWN_SUBJECTS = frozenset(
    {"english", "hindi", "maths", "odia", "sanskrit", "science", "social_science"}
)


class LearnAssistChatRequest(BaseModel):
    """LearnAssist chat request."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        examples=["how many chapters are there in the science book?"],
    )
    board: str = Field(..., min_length=1, examples=["scert_odisha"])
    class_no: int = Field(..., ge=1, le=12, examples=[8])
    subject: str | None = Field(
        default=None,
        max_length=64,
        description="Optional. One of: " + ", ".join(sorted(KNOWN_SUBJECTS))
        + ". Unknown values are ignored (search all subjects).",
        examples=["science", None],
    )
    language: str | None = Field(default=None, examples=["en", "or", None])
    debug: bool = False

    @field_validator("message", "board", "subject", "language", mode="before")
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
        """Lowercase the subject; drop unknown values so they don't filter to nothing."""
        if not value:
            return None
        normalized = value.lower()
        return normalized if normalized in KNOWN_SUBJECTS else None


class LearnAssistChatResponse(BaseModel):
    """LearnAssist chat response."""

    answer: str
    citations: list[dict[str, Any]]
    retrieval: dict[str, Any]
    usage: UsageResponse | None = None
    context_blocks: list[dict[str, Any]] | None = None
