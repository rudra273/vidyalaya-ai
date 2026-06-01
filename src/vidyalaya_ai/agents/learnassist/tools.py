"""Tools available to the LearnAssist agent."""

from __future__ import annotations

import logging

from langchain.tools import ToolRuntime, tool
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from vidyalaya_ai.agents.learnassist.context import LearnAssistContext
from vidyalaya_ai.agents.learnassist.prompt import build_retrieval_metadata, format_context
from vidyalaya_ai.rag.config import RagConfig
from vidyalaya_ai.tools.retrieve_textbook import retrieve_textbook


logger = logging.getLogger("vidyalaya_ai.agents")

# Marks a ToolMessage as produced by search_textbook so the runner can find this
# turn's retrieval in the returned messages. The structured data rides in the
# message's ``artifact`` field (the LLM only sees ``content``).
SEARCH_TOOL_NAME = "search_textbook"


@tool
def search_textbook(query: str, runtime: ToolRuntime[LearnAssistContext]) -> Command:
    """Search the student's textbook for passages that answer a curriculum question.

    Use only for substantive subject or textbook questions (concepts, definitions,
    facts, exercise questions). Do NOT use for greetings, thanks, small talk, or
    follow-ups already answerable from the conversation.

    You may call this tool more than once per turn — for example, first to retrieve
    the table of contents (suchipatra), then again to retrieve the actual chapter.

    Args:
        query: A focused search query in the native script of the textbook language.
            Odia books -> Odia script. Hindi books -> Devanagari. English -> English.
            If the student wrote in Roman script (e.g. "kabir das ke dohe"), convert
            to the correct script before passing here. Use multiple keywords and
            synonyms for better retrieval (e.g. "कबीर दास दोहे गुरु गोविंद साखी").
    """
    ctx = runtime.context
    logger.info(
        "search_textbook query=%r board=%s class=%s subject=%s",
        query,
        ctx.board,
        ctx.class_no,
        ctx.subject,
    )

    result = retrieve_textbook(
        query=query,
        board=ctx.board,
        class_no=ctx.class_no,
        subject=ctx.subject,
    )
    blocks = result["context_blocks"]
    tool_text = format_context(blocks, RagConfig()) or "(no relevant textbook passages found)"

    # content -> what the LLM reads; artifact -> structured data for the runner.
    # Both travel inside the ToolMessage, so retrieval is scoped to this turn only
    # and can never leak from a prior turn via the checkpoint.
    artifact = {
        "context_blocks": blocks,
        "retrieval": build_retrieval_metadata(result, tool_used=True),
    }
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=tool_text,
                    tool_call_id=runtime.tool_call_id,
                    name=SEARCH_TOOL_NAME,
                    artifact=artifact,
                )
            ]
        }
    )
