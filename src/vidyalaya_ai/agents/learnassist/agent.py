"""LearnAssist agent built with the LangChain ``create_agent`` runtime."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import (
    ModelRetryMiddleware,
    before_model,
    dynamic_prompt,
    wrap_model_call,
)
from langchain_core.messages import AIMessage, RemoveMessage, ToolMessage, trim_messages

from vidyalaya_ai.agents.checkpointer import get_checkpointer
from vidyalaya_ai.agents.learnassist.context import LearnAssistContext
from vidyalaya_ai.agents.learnassist.prompt import build_system_prompt
from vidyalaya_ai.agents.tools.retrieve_textbook import search_textbook
from vidyalaya_ai.llm import LLMConfig, create_chat_model


logger = logging.getLogger("vidyalaya_ai.agents")

# How many recent messages to send to the model (~5 exchanges). Full history is
# always kept in the checkpointer; this only bounds what each request sends to
# the LLM.
MAX_MODEL_MESSAGES = 10


@dynamic_prompt
def _learnassist_prompt(request: Any) -> str:
    """Build the system prompt per request from the runtime context."""
    return build_system_prompt(request.runtime.context)


@wrap_model_call
async def _trim_to_recent(request: Any, handler: Any) -> Any:
    """Send only the last MAX_MODEL_MESSAGES to the model, not the whole thread.

    Trimming happens only on the request to the model - the persisted checkpoint
    keeps the full history. ``start_on=("human", "tool")`` keeps the window on a
    valid boundary so a tool call is never split from its result.

    Async because the agent is invoked with ``ainvoke``; the sync variant of this
    hook is not used in an async run.
    """
    trimmed = trim_messages(
        request.messages,
        max_tokens=MAX_MODEL_MESSAGES,
        token_counter=len,  # count messages, not tokens
        strategy="last",
        start_on=("human", "tool"),
        include_system=False,
        allow_partial=False,
    )
    return await handler(request.override(messages=trimmed or request.messages))


def heal_messages(messages: list[Any]) -> list[str]:
    """Return ids of messages belonging to an incomplete previous turn, if any.

    A turn that died before producing its final answer (e.g. the request timed
    out mid-flight, or the process crashed) is still persisted by the
    checkpointer. It leaves one of:
      - an orphaned ``AIMessage(tool_calls)`` (+ ``ToolMessage``) with no answer, or
      - a bare ``HumanMessage`` whose answer never came.
    Left in history, this incomplete turn leaks stale context into the next, new
    question - this is what made a fresh "hi" answer a previous, timed-out
    textbook question.

    We treat the run of messages BEFORE the latest human turn as a sequence of
    completed turns. Walking back from there, we collect every trailing message
    that is part of an *incomplete* turn - tool calls/results AND the dangling
    ``HumanMessage`` that started it - stopping at the first terminal answer (an
    ``AIMessage`` with no ``tool_calls``), which marks the last good turn.

    Loop-safety: only messages strictly BEFORE the latest ``HumanMessage`` are
    considered. The current turn's own in-progress human/tool/AI messages sit AT
    or AFTER that index, so they are never returned - this can run on every model
    step without removing the work the agent is mid-way through.

    Pure and side-effect free so it can be unit-tested directly; the
    ``@before_model`` wrapper below adapts it to the middleware interface.
    """
    from langchain_core.messages import HumanMessage

    last_human = _last_human_index(messages)
    if last_human <= 0:
        return []

    remove_ids: list[str] = []
    for message in reversed(messages[:last_human]):
        # A terminal AI answer (no pending tool calls) ends the last good turn.
        if isinstance(message, AIMessage) and not getattr(message, "tool_calls", None):
            break
        # Everything else trailing here belongs to an incomplete turn: orphaned
        # tool calls/results, plus the HumanMessage that started the dead turn.
        if isinstance(message, (ToolMessage, AIMessage, HumanMessage)):
            if message.id:
                remove_ids.append(message.id)
            continue
        break  # any other terminal message ends the last good turn

    return remove_ids


@before_model
def _heal_history(state: dict, runtime: Any) -> dict | None:
    """Drop an incomplete previous turn left by a crash or timeout (see
    :func:`heal_messages`)."""
    remove_ids = heal_messages(state.get("messages", []))
    if not remove_ids:
        return None

    logger.warning(
        "Healing thread: dropping %d message(s) from an incomplete previous turn",
        len(remove_ids),
    )
    return {"messages": [RemoveMessage(id=mid) for mid in remove_ids]}


def _last_human_index(messages: list[Any]) -> int:
    from langchain_core.messages import HumanMessage

    for index in range(len(messages) - 1, -1, -1):
        if isinstance(messages[index], HumanMessage):
            return index
    return -1


# Retry transient model/provider failures (rate limits, 5xx, network blips)
# with exponential backoff + jitter, on top of the SDK's own per-call retries.
# A turn that still fails after this is treated as "provider unavailable" by the
# runner. Kept small so a genuinely-down provider fails fast rather than holding
# the request open near the turn timeout.
_model_retry = ModelRetryMiddleware(
    max_retries=2,
    initial_delay=0.5,
    backoff_factor=2.0,
    max_delay=8.0,
)


def build_agent(
    checkpointer: Any | None = None,
    *,
    provider: str | None = None,
    model: str | None = None,
) -> Any:
    """Compile the LearnAssist agent for a given provider/model.

    ``provider``/``model`` of ``None`` fall back to the env-configured defaults
    in :class:`LLMConfig`, so a plan that doesn't pin a model inherits the app
    default.
    """
    base = LLMConfig()
    config = LLMConfig(
        provider=provider or base.provider,
        model=model or base.model,
    )
    chat_model = create_chat_model(config)
    return create_agent(
        model=chat_model,
        tools=[search_textbook],
        middleware=[_heal_history, _model_retry, _trim_to_recent, _learnassist_prompt],
        context_schema=LearnAssistContext,
        checkpointer=checkpointer,
    )


@lru_cache(maxsize=8)
def get_agent_for(provider: str | None, model: str | None) -> Any:
    """Return a compiled agent for (provider, model), cached per combination.

    The checkpointer is shared (process-wide), so only the bound chat model
    differs between cached agents. ``maxsize`` comfortably covers the handful of
    plan tiers; distinct (provider, model) pairs are few and stable.
    """
    return build_agent(get_checkpointer(), provider=provider, model=model)


def get_agent() -> Any:
    """Return the agent bound to the default (env-configured) provider/model."""
    return get_agent_for(None, None)
