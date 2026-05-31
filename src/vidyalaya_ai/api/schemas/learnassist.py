"""LearnAssist schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from vidyalaya_ai.api.schemas.me import UsageResponse


# Subjects present in the indexed textbook data.
KNOWN_SUBJECTS = frozenset(
    {"english", "hindi", "maths", "odia", "sanskrit", "science", "social_science"}
)

# The "ask anything" channel: cross-subject Q&A, no subject filter. Distinct from
# the subject channels so its memory never mixes with theirs.
GENERAL_CHANNEL = "general"

# Valid channel values: the general channel, or any known subject.
KNOWN_CHANNELS = frozenset({GENERAL_CHANNEL}) | KNOWN_SUBJECTS


class LearnAssistChatRequest(BaseModel):
    """LearnAssist chat request.

    ``channel`` is the single source of truth for *which conversation* this is and
    *which subject* (if any) retrieval is scoped to. The server derives the subject
    filter and the memory thread from it - there is deliberately no separate
    free-form ``subject`` field that could disagree with the channel.

    - ``channel="general"`` -> cross-subject "ask anything"; no subject filter.
    - ``channel="science"`` (any known subject) -> that subject only; filter enforced.
    """

    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        examples=["how many chapters are there in the science book?"],
    )
    board: str = Field(..., min_length=1, examples=["scert_odisha"])
    class_no: int = Field(..., ge=1, le=12, examples=[8])
    channel: str = Field(
        default=GENERAL_CHANNEL,
        description="Conversation/channel. '" + GENERAL_CHANNEL + "' for cross-subject "
        "help, or one of: " + ", ".join(sorted(KNOWN_SUBJECTS)) + ".",
        examples=[GENERAL_CHANNEL, "science"],
    )
    language: str | None = Field(default=None, examples=["en", "or", None])
    debug: bool = False

    @field_validator("message", "board", "language", mode="before")
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

    @field_validator("channel", mode="before")
    @classmethod
    def normalize_channel(cls, value: str | None) -> str:
        """Normalize/validate the channel; empty or missing means the general channel."""
        if value is None:
            return GENERAL_CHANNEL
        if not isinstance(value, str):
            raise ValueError("channel must be a string")
        normalized = value.strip().lower()
        if not normalized:
            return GENERAL_CHANNEL
        if normalized not in KNOWN_CHANNELS:
            raise ValueError(
                "channel must be '"
                + GENERAL_CHANNEL
                + "' or one of: "
                + ", ".join(sorted(KNOWN_SUBJECTS))
            )
        return normalized

    @property
    def subject(self) -> str | None:
        """The retrieval subject filter derived from the channel.

        The general channel has no subject filter; a subject channel filters to
        exactly its subject (never "search all subjects").
        """
        return None if self.channel == GENERAL_CHANNEL else self.channel


class LearnAssistChatResponse(BaseModel):
    """LearnAssist chat response."""

    answer: str
    citations: list[dict[str, Any]]
    retrieval: dict[str, Any]
    usage: UsageResponse | None = None
    context_blocks: list[dict[str, Any]] | None = None
