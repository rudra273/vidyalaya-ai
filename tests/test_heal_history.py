"""Regression tests for `_heal_history` (Phase A reliability fix).

The bug: a timed-out / crashed turn is still persisted by the checkpointer, so a
fresh next message ("hi") could answer the previous, abandoned question. Healing
must strip an incomplete previous turn - including the dangling HumanMessage that
started it - while never touching completed turns or the current in-flight turn.

Dependency-light: uses only langchain_core message types (already a project dep)
and asserts with plain `assert`, so it runs under the project venv without pytest:

    .venv/bin/python tests/test_heal_history.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from vidyalaya_ai.agents.learnassist.agent import heal_messages


def _removed_ids(messages: list) -> set[str]:
    return set(heal_messages(messages))


def _ai(content: str, *, tool_calls=None, mid: str) -> AIMessage:
    return AIMessage(content=content, tool_calls=tool_calls or [], id=mid)


def _tool_call(name: str, call_id: str) -> dict:
    return {"name": name, "args": {}, "id": call_id, "type": "tool_call"}


def test_strips_timed_out_textbook_turn_before_fresh_greeting() -> None:
    """The core bug: 'how many chapters' timed out, then 'hi' arrives.

    The failed turn (Human + orphaned tool call/result, no answer) must be fully
    removed so the model sees only the greeting.
    """
    messages = [
        HumanMessage("what is photosynthesis?", id="h0"),
        _ai("Photosynthesis is ...", mid="a0"),  # completed good turn
        HumanMessage("how many chapters in science?", id="h1"),  # timed out
        _ai("", tool_calls=[_tool_call("search_textbook", "c1")], mid="a1"),
        ToolMessage("(passages)", tool_call_id="c1", name="search_textbook", id="t1"),
        HumanMessage("hi", id="h2"),  # fresh latest turn
    ]

    removed = _removed_ids(messages)

    assert removed == {"h1", "a1", "t1"}, removed
    # The good turn and the current greeting are untouched.
    assert "h0" not in removed and "a0" not in removed and "h2" not in removed


def test_keeps_completed_tool_turn() -> None:
    """A previous turn that used the tool AND produced an answer is preserved."""
    messages = [
        HumanMessage("explain gravity", id="h0"),
        _ai("", tool_calls=[_tool_call("search_textbook", "c0")], mid="a0"),
        ToolMessage("(passages)", tool_call_id="c0", name="search_textbook", id="t0"),
        _ai("Gravity is ... [1]", mid="a1"),  # terminal answer -> turn complete
        HumanMessage("hi", id="h1"),
    ]

    assert _removed_ids(messages) == set(), "completed tool turn must not be healed"


def test_strips_orphaned_tool_call_keeps_its_human_if_answered_later() -> None:
    """Orphaned tool call with no answer is stripped down to the last good answer."""
    messages = [
        HumanMessage("q1", id="h0"),
        _ai("answer 1", mid="a0"),  # last good turn
        _ai("", tool_calls=[_tool_call("search_textbook", "c1")], mid="a1"),  # orphan
        ToolMessage("(passages)", tool_call_id="c1", name="search_textbook", id="t1"),
        HumanMessage("hi", id="h1"),
    ]

    removed = _removed_ids(messages)

    assert removed == {"a1", "t1"}, removed
    assert "a0" not in removed


def test_noop_when_history_is_clean() -> None:
    """No incomplete turn -> nothing removed."""
    messages = [
        HumanMessage("q1", id="h0"),
        _ai("answer 1", mid="a0"),
        HumanMessage("q2", id="h1"),
    ]

    assert _removed_ids(messages) == set()


def test_noop_on_first_turn() -> None:
    """Only the current human message present -> nothing to heal."""
    messages = [HumanMessage("hi", id="h0")]

    assert _removed_ids(messages) == set()


def test_strips_multiple_incomplete_turns() -> None:
    """Two stacked failed turns before the fresh message are both cleared."""
    messages = [
        HumanMessage("good q", id="h0"),
        _ai("good answer", mid="a0"),  # last good turn
        HumanMessage("failed q1", id="h1"),  # incomplete
        _ai("", tool_calls=[_tool_call("search_textbook", "c1")], mid="a1"),
        ToolMessage("(passages)", tool_call_id="c1", name="search_textbook", id="t1"),
        HumanMessage("failed q2", id="h2"),  # incomplete, bare human (timed out early)
        HumanMessage("hi", id="h3"),  # fresh latest
    ]

    removed = _removed_ids(messages)

    assert removed == {"h1", "a1", "t1", "h2"}, removed
    assert "h0" not in removed and "a0" not in removed and "h3" not in removed


def _run_all() -> None:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL  {test.__name__}: {exc}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    _run_all()
