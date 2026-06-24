"""Unit tests for the 30-minute inactivity session reset logic.

Tests the pure decision function and the checkpoint reset helper.
No database or network required.

Run directly:
    .venv/bin/python tests/test_session_reset.py
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from vidyalaya_ai.api.routers.learnassist import should_reset_session


# ---------------------------------------------------------------------------
# Tests for should_reset_session
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=timezone.utc)
_TIMEOUT = 30


def test_no_history_never_resets() -> None:
    assert not should_reset_session(None, _NOW, _TIMEOUT)


def test_timeout_disabled_never_resets() -> None:
    last = _NOW - timedelta(minutes=60)
    assert not should_reset_session(last, _NOW, 0)
    assert not should_reset_session(last, _NOW, -1)


def test_recent_activity_no_reset() -> None:
    last = _NOW - timedelta(minutes=10)
    assert not should_reset_session(last, _NOW, _TIMEOUT)


def test_exactly_at_boundary_no_reset() -> None:
    # Boundary is exclusive: > not >=
    last = _NOW - timedelta(minutes=30)
    assert not should_reset_session(last, _NOW, _TIMEOUT)


def test_one_second_past_boundary_resets() -> None:
    last = _NOW - timedelta(minutes=30, seconds=1)
    assert should_reset_session(last, _NOW, _TIMEOUT)


def test_long_inactivity_resets() -> None:
    last = _NOW - timedelta(hours=2)
    assert should_reset_session(last, _NOW, _TIMEOUT)


def test_custom_timeout() -> None:
    last = _NOW - timedelta(minutes=10)
    assert not should_reset_session(last, _NOW, timeout_minutes=15)
    assert should_reset_session(last, _NOW, timeout_minutes=5)


# ---------------------------------------------------------------------------
# Test reset_thread_checkpoint with InMemorySaver
# ---------------------------------------------------------------------------

def test_reset_thread_checkpoint_with_in_memory_saver() -> None:
    """reset_thread_checkpoint works against InMemorySaver (no crash, no-op ok)."""
    from langgraph.checkpoint.memory import InMemorySaver
    from unittest.mock import patch

    saver = InMemorySaver()

    async def _run() -> None:
        import vidyalaya_ai.agents.checkpointer as cp_module
        with patch.object(cp_module, "_checkpointer", saver):
            from vidyalaya_ai.agents.checkpointer import reset_thread_checkpoint
            await reset_thread_checkpoint("test:uid:scert:8:science")

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _run_all() -> None:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except Exception as exc:
            failures += 1
            print(f"FAIL  {test.__name__}: {exc}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    _run_all()
