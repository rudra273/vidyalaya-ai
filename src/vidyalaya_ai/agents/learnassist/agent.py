"""LearnAssist agent built with the LangChain ``create_agent`` runtime."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import before_model, dynamic_prompt, wrap_model_call
from langchain_core.messages import AIMessage, RemoveMessage, ToolMessage, trim_messages

from vidyalaya_ai.agents.learnassist.checkpointer import get_checkpointer
from vidyalaya_ai.agents.learnassist.context import LearnAssistContext
from vidyalaya_ai.agents.learnassist.prompt import build_system_prompt
from vidyalaya_ai.agents.learnassist.tools import search_textbook
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


@before_model
def _heal_history(state: dict, runtime: Any) -> dict | None:
    """Drop an orphaned tool turn left by a previous crashed turn.

    A turn that died after a tool call but before its answer (e.g. token limit)
    leaves a dangling AIMessage(tool_calls)+ToolMessage with no final answer. Left
    in history it wastes a tool result and leaks stale context into the next, new
    question.

    Loop-safety: we only strip orphans that sit BEFORE the latest HumanMessage.
    The current turn's own in-progress tool call/result come AFTER the latest
    human message, so they are never touched - this hook can run on every model
    step without ever removing the work the agent is mid-way through.
    """
    messages = state.get("messages", [])
    last_human = _last_human_index(messages)
    if last_human <= 0:
        return None

    # Look at the run of messages immediately before the latest human turn.
    remove_ids: list[str] = []
    for message in reversed(messages[:last_human]):
        if isinstance(message, ToolMessage):
            remove_ids.append(message.id)
            continue
        if isinstance(message, AIMessage) and getattr(message, "tool_calls", None):
            remove_ids.append(message.id)
            continue
        break  # reached a complete message; nothing orphaned before the human turn

    if not remove_ids:
        return None

    logger.warning("Healing thread: dropping %d orphaned message(s)", len(remove_ids))
    return {"messages": [RemoveMessage(id=mid) for mid in remove_ids if mid]}


def _last_human_index(messages: list[Any]) -> int:
    from langchain_core.messages import HumanMessage

    for index in range(len(messages) - 1, -1, -1):
        if isinstance(messages[index], HumanMessage):
            return index
    return -1


def build_agent(checkpointer: Any | None = None) -> Any:
    """Compile the LearnAssist agent."""
    model = create_chat_model(LLMConfig())
    return create_agent(
        model=model,
        tools=[search_textbook],
        middleware=[_heal_history, _trim_to_recent, _learnassist_prompt],
        context_schema=LearnAssistContext,
        checkpointer=checkpointer,
    )


@lru_cache(maxsize=1)
def get_agent() -> Any:
    """Return the process-wide compiled LearnAssist agent."""
    return build_agent(get_checkpointer())
