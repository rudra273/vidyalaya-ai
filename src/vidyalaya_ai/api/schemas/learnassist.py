"""LearnAssist schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from vidyalaya_ai.api.schemas.me import UsageResponse


# Subjects present in the indexed textbook data.
KNOWN_SUBJECTS = frozenset(
    {"english", "hindi", "maths", "odia", "sanskrit", "science", "social_science"}
)

# A "channel" is the agent/product surface the student is talking to. The current
# study helper is "learn_assist"; the future tutoring agent will be "tutor".
LEARN_ASSIST_CHANNEL = "learn_assist"
KNOWN_CHANNELS = frozenset({LEARN_ASSIST_CHANNEL})

# Used in the thread id (and retrieval) when the student has not picked a subject -
# the cross-subject "ask anything" mode. Distinct, named scope so its memory never
# mixes with a specific subject's.
GENERAL_SUBJECT = "general"


class LearnAssistChatRequest(BaseModel):
    """LearnAssist chat request.

    Two orthogonal selectors:
    - ``channel``: which agent/surface this is (``learn_assist`` today; ``tutor``
      later). It is the top-level prefix of the memory thread.
    - ``subject``: the academic subject this conversation is about. Optional - when
      omitted the conversation is the cross-subject "ask anything" thread and
      retrieval is not filtered to a subject.

    Memory is scoped per ``(channel, board, class, subject-or-general)``, so subjects
    never leak into each other and a class/board change starts fresh.
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
        default=LEARN_ASSIST_CHANNEL,
        description="Agent/surface. Currently only '" + LEARN_ASSIST_CHANNEL + "'.",
        examples=[LEARN_ASSIST_CHANNEL],
    )
    subject: str | None = Field(
        default=None,
        max_length=64,
        description="Optional academic subject. One of: "
        + ", ".join(sorted(KNOWN_SUBJECTS))
        + ". Omit/null for cross-subject 'ask anything' (no subject filter). "
        "Unknown values are treated as no subject.",
        examples=["science", None],
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
        """Normalize/validate the channel (agent); empty or missing -> learn_assist."""
        if value is None:
            return LEARN_ASSIST_CHANNEL
        if not isinstance(value, str):
            raise ValueError("channel must be a string")
        normalized = value.strip().lower()
        if not normalized:
            return LEARN_ASSIST_CHANNEL
        if normalized not in KNOWN_CHANNELS:
            raise ValueError(
                "channel must be one of: " + ", ".join(sorted(KNOWN_CHANNELS))
            )
        return normalized

    @field_validator("subject")
    @classmethod
    def normalize_subject(cls, value: str | None) -> str | None:
        """Lowercase the subject; drop unknown values so they don't filter to nothing."""
        if not value:
            return None
        normalized = value.lower()
        return normalized if normalized in KNOWN_SUBJECTS else None

    @property
    def thread_subject(self) -> str:
        """The subject segment used in the memory thread id.

        A concrete subject when one is selected, else the literal ``general`` so the
        cross-subject conversation is its own named, isolated thread.
        """
        return self.subject or GENERAL_SUBJECT


class LearnAssistChatResponse(BaseModel):
    """LearnAssist chat response."""

    answer: str
    citations: list[dict[str, Any]]
    retrieval: dict[str, Any]
    usage: UsageResponse | None = None
    context_blocks: list[dict[str, Any]] | None = None


class MemoryResetRequest(BaseModel):
    """Request to manually clear the agent's working memory for a thread.

    Mirrors the selectors the chat endpoint uses so the server can reconstruct
    the exact thread id. The permanent ``messages`` table is never affected.
    """

    board: str = Field(..., min_length=1, examples=["scert_odisha"])
    class_no: int = Field(..., ge=1, le=12, examples=[8])
    channel: str = Field(default=LEARN_ASSIST_CHANNEL, examples=[LEARN_ASSIST_CHANNEL])
    subject: str | None = Field(
        default=None,
        max_length=64,
        description="Subject to clear, or omit/null for the general thread.",
        examples=["science", None],
    )

    @field_validator("board")
    @classmethod
    def validate_board(cls, value: str) -> str:
        if value != "scert_odisha":
            raise ValueError("board must be one of: scert_odisha")
        return value

    @field_validator("channel", mode="before")
    @classmethod
    def normalize_channel(cls, value: str | None) -> str:
        if value is None:
            return LEARN_ASSIST_CHANNEL
        normalized = str(value).strip().lower() or LEARN_ASSIST_CHANNEL
        if normalized not in KNOWN_CHANNELS:
            raise ValueError("channel must be one of: " + ", ".join(sorted(KNOWN_CHANNELS)))
        return normalized

    @field_validator("subject")
    @classmethod
    def normalize_subject(cls, value: str | None) -> str | None:
        if not value:
            return None
        normalized = value.lower()
        return normalized if normalized in KNOWN_SUBJECTS else None

    @property
    def thread_subject(self) -> str:
        return self.subject or GENERAL_SUBJECT


class MemoryResetResponse(BaseModel):
    """Response after a manual memory reset."""

    reset: bool
