"""Per-request context for the LearnAssist agent.

These values change every turn (a student may switch subject or language at any
time), so they are passed via the agent's ``context`` at invoke time rather than
stored in the checkpointed conversation state.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LearnAssistContext:
    """Runtime inputs supplied by the client on each chat request."""

    board: str
    class_no: int
    subject: str | None = None
    language: str | None = None
