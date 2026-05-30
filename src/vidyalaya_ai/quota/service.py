"""Daily quota service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from vidyalaya_ai.auth.models import AuthenticatedUser
from vidyalaya_ai.db.engine import session_scope
from vidyalaya_ai.db.models import DailyUsage
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

    # Atomic spend: insert the day's row at count=1, or bump an existing row by
    # one, returning the post-increment count in a single round trip.
    stmt = (
        insert(DailyUsage)
        .values(
            firebase_uid=firebase_uid,
            date_ist=date_ist,
            agent=agent,
            count=1,
            first_at=now,
            last_at=now,
        )
        .on_conflict_do_update(
            constraint="uq_daily_usage_user_date_agent",
            set_={"count": DailyUsage.count + 1, "last_at": now},
        )
        .returning(DailyUsage.count)
    )
    async with session_scope() as session:
        result = await session.execute(stmt)
        used = int(result.scalar_one())
        await session.commit()

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
    async with session_scope() as session:
        result = await session.execute(
            select(DailyUsage.count).where(
                DailyUsage.firebase_uid == firebase_uid,
                DailyUsage.date_ist == date_ist,
                DailyUsage.agent == agent,
            )
        )
        count = result.scalar_one_or_none()
    return int(count) if count is not None else 0
