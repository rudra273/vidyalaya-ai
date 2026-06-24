"""Per-turn usage accounting DTO.

A neutral leaf module: it imports nothing from ``agents`` or ``chatlog``, so both
layers can depend on it without forming an import cycle. The agent layer
(``agents.learnassist.runner``) produces a :class:`TurnUsage`; the persistence
layer (``chatlog.service``) consumes it. Keeping the shared DTO here — rather
than inside ``agents`` — is what lets ``chatlog`` stay free of any dependency on
the higher-level ``agents`` package.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TurnUsage:
    """Per-turn LLM/tool accounting, summed across the turn's AI messages."""

    llm_calls: int = 0
    tool_calls: int = 0
    tokens_input: int = 0
    tokens_output: int = 0
    tokens_total: int = 0
    model: str | None = None
