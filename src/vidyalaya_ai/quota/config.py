"""Quota configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


@dataclass(frozen=True)
class QuotaConfig:
    """Daily quota settings."""

    default_daily_limit: int = 3


@lru_cache(maxsize=1)
def load_quota_config() -> QuotaConfig:
    """Load quota config from the environment."""
    load_dotenv()
    raw_limit = os.getenv("LEARNASSIST_DAILY_LIMIT", "3").strip()
    return QuotaConfig(default_daily_limit=max(0, int(raw_limit)))
