"""Hardcoded subscription plan definitions.

Each plan maps a ``plan_key`` to its entitlements: a daily LearnAssist quota and
the LLM provider/model used for that tier. Plans are defined in code (not the DB)
so changing a tier's quota or model is a code change, reviewed and deployed —
the ``subscriptions`` table only records *which* plan a user holds.

A ``daily_limit`` of ``None`` means unlimited. Free users use the direct Google
Gemini provider, while paid tiers route the same Gemini 2.0 Flash model through
OpenRouter. Later, paid tiers can be moved to larger models by changing only
these plan definitions.

These are sensible starting values — tune the numbers and model ids freely; the
schema and resolution logic do not depend on the specific values.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Plan:
    """Entitlements for a subscription tier."""

    key: str
    daily_limit: int | None  # None = unlimited
    provider: str | None = None  # None = app default (LLMConfig)
    model: str | None = None  # None = app default (LLMConfig)


# Direct Gemini provider model id (LangChain Google provider).
GOOGLE_GEMINI_2_FLASH = "gemini-2.0-flash"

# OpenRouter model id for the same Gemini 2.0 Flash family.
OPENROUTER_GEMINI_2_FLASH = "google/gemini-2.0-flash-001"


# free  — low daily cap on direct Gemini, suitable for the free API key.
# plus  — higher cap through OpenRouter, same model for now.
# pro   — highest cap through OpenRouter, same model for now.
PLANS: dict[str, Plan] = {
    "free": Plan(
        key="free",
        daily_limit=3,
        provider="google",
        model=GOOGLE_GEMINI_2_FLASH,
    ),
    "plus": Plan(
        key="plus",
        daily_limit=25,
        provider="openrouter",
        model=OPENROUTER_GEMINI_2_FLASH,
    ),
    "pro": Plan(
        key="pro",
        daily_limit=100,
        provider="openrouter",
        model=OPENROUTER_GEMINI_2_FLASH,
    ),
}

DEFAULT_PLAN_KEY = "free"

# Subscription statuses that grant the plan's entitlements. Anything else
# (cancelled, expired, past_due) falls back to the free plan.
ENTITLED_STATUSES: frozenset[str] = frozenset({"active", "trialing"})


def get_plan(plan_key: str | None) -> Plan:
    """Return the plan for ``plan_key``, falling back to free for unknown keys."""
    if plan_key is None:
        return PLANS[DEFAULT_PLAN_KEY]
    return PLANS.get(plan_key, PLANS[DEFAULT_PLAN_KEY])


def is_valid_plan_key(plan_key: str) -> bool:
    """Whether ``plan_key`` names a defined plan."""
    return plan_key in PLANS
