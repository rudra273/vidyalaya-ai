"""Typed agent errors so the API can return clean responses, never a raw 500.

The runner classifies whatever the agent/LLM/provider raises into one of these
and re-raises it; the API layer maps each to a friendly status code:

- ``AgentTimeout``     -> 504 "That took too long, please try again."
- ``AgentUnavailable`` -> 503 "Assistant is busy, please try again."

Anything not classified falls through to the generic 500 handler (still safe
text; full detail logged server-side only).
"""

from __future__ import annotations


class AgentError(Exception):
    """Base class for LearnAssist agent failures surfaced to the API."""


class AgentTimeout(AgentError):
    """The agent turn exceeded its time budget."""


class AgentUnavailable(AgentError):
    """The model/provider was unreachable, rate-limited, or transiently failing."""
