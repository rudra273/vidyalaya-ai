"""Per-request context for the LearnAssist agent.

These values change every turn (a student may switch subject or language at any
time), so they are passed via the agent's ``context`` at invoke time rather than
stored in the checkpointed conversation state.
"""

from __future__ import annotations

from dataclasses import dataclass


AGENT = "learnassist"


def build_thread_id(
    *,
    channel: str,
    firebase_uid: str,
    board: str,
    class_no: int,
    subject: str,
) -> str:
    """Build the memory thread id for a conversation.

    Shape: ``{channel}:{uid}:{board}:{class_no}:{subject}`` where ``channel`` is the
    agent/surface (``learn_assist``, ``tutor`` …) and ``subject`` is the academic
    subject or the literal ``general`` for the cross-subject thread. Scoping per
    (channel, board, class, subject) keeps subjects from leaking into each other and
    makes a class/board change start fresh - ``board``/``class_no`` are in the key
    (not just the uid) because the profile is updateable.

    Single source of truth for the thread id: both the chat endpoint (which writes
    memory) and the history endpoint (which reads display history) call this, so the
    two can never drift out of sync.
    """
    return f"{channel}:{firebase_uid}:{board}:{class_no}:{subject}"


@dataclass
class LearnAssistContext:
    """Runtime inputs supplied by the client on each chat request."""

    board: str
    class_no: int
    subject: str | None = None
    language: str | None = None
