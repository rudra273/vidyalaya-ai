"""Per-request context for the LearnAssist agent.

These values change every turn (a student may switch subject or language at any
time), so they are passed via the agent's ``context`` at invoke time rather than
stored in the checkpointed conversation state.
"""

from __future__ import annotations

from dataclasses import dataclass


AGENT = "learnassist"


def build_thread_id(
    *, firebase_uid: str, board: str, class_no: int, channel: str
) -> str:
    """Build the memory thread id for a (student, board, class, channel).

    Memory is scoped per channel and per board/class so subjects never leak into
    each other and a class/board change starts fresh. ``board``/``class_no`` are in
    the key (not just the uid) because the student's profile is updateable.

    Single source of truth for the thread id: both the chat endpoint (which writes
    memory) and the history endpoint (which reads display history) call this, so
    the two can never drift out of sync.
    """
    return f"{AGENT}:{firebase_uid}:{board}:{class_no}:{channel}"


@dataclass
class LearnAssistContext:
    """Runtime inputs supplied by the client on each chat request."""

    board: str
    class_no: int
    subject: str | None = None
    language: str | None = None
