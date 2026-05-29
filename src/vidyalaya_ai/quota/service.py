"""Daily quota service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from pymongo import ReturnDocument

from vidyalaya_ai.auth.models import AuthenticatedUser
from vidyalaya_ai.db.mongo import get_db
from vidyalaya_ai.quota.config import load_quota_config
from vidyalaya_ai.quota.exceptions import QuotaExceeded


IST = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True)
class UsageView:
    """API-facing usage summary."""

    date_ist: str
    used: int
    limit: int | None
    remaining: int | None
    unlimited: bool


def _now() -> datetime:
    return datetime.now(UTC)


def _today_ist(now: datetime | None = None) -> str:
    return (now or _now()).astimezone(IST).date().isoformat()


def _next_midnight_ist(now: datetime | None = None) -> str:
    local_now = (now or _now()).astimezone(IST)
    tomorrow = local_now.date() + timedelta(days=1)
    retry_at = datetime.combine(tomorrow, time.min, tzinfo=IST)
    return retry_at.isoformat()


def _limit_for_user(user: AuthenticatedUser) -> int | None:
    override = user.quota_override
    if override == "unlimited":
        return None
    # bool is a subclass of int; exclude it so quota_override=true is not read as limit=1.
    if isinstance(override, int) and not isinstance(override, bool):
        return max(0, override)
    return load_quota_config().default_daily_limit


async def check_and_increment(
    firebase_uid: str,
    agent: str,
    user: AuthenticatedUser,
) -> UsageView:
    """Atomically spend one daily quota unit and return usage."""
    limit = _limit_for_user(user)
    now = _now()
    date_ist = _today_ist(now)

    if limit is None:
        used = await _read_count(firebase_uid, agent, date_ist)
        return UsageView(
            date_ist=date_ist,
            used=used,
            limit=None,
            remaining=None,
            unlimited=True,
        )

    document = await get_db().daily_usage.find_one_and_update(
        {"firebase_uid": firebase_uid, "date_ist": date_ist, "agent": agent},
        {
            "$inc": {"count": 1},
            "$set": {"last_at": now},
            "$setOnInsert": {"first_at": now},
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    used = int(document.get("count", 0))
    if used > limit:
        raise QuotaExceeded(used=used, limit=limit, retry_at_ist=_next_midnight_ist(now))

    return UsageView(
        date_ist=date_ist,
        used=used,
        limit=limit,
        remaining=max(0, limit - used),
        unlimited=False,
    )


async def get_usage(firebase_uid: str, agent: str, user: AuthenticatedUser) -> UsageView:
    """Return current daily usage without spending quota."""
    limit = _limit_for_user(user)
    date_ist = _today_ist()
    used = await _read_count(firebase_uid, agent, date_ist)
    return UsageView(
        date_ist=date_ist,
        used=used,
        limit=limit,
        remaining=None if limit is None else max(0, limit - used),
        unlimited=limit is None,
    )


async def _read_count(firebase_uid: str, agent: str, date_ist: str) -> int:
    document = await get_db().daily_usage.find_one(
        {"firebase_uid": firebase_uid, "date_ist": date_ist, "agent": agent},
        {"count": 1},
    )
    if document is None:
        return 0
    return int(document.get("count", 0))
