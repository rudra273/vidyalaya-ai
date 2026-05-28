"""Quota-related exceptions."""

from __future__ import annotations


class QuotaExceeded(Exception):
    """Raised when a user has exhausted their daily quota."""

    def __init__(self, *, used: int, limit: int, retry_at_ist: str) -> None:
        self.used = used
        self.limit = limit
        self.retry_at_ist = retry_at_ist
        super().__init__("Daily LearnAssist quota exceeded.")
