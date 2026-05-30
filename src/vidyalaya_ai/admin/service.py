"""Admin read/write queries over users, subscriptions, and usage.

Thin data layer for the admin API (Phase 6). Reads are paged/rolled-up;
writes (quota override, status, plan assignment) go through here or the
subscriptions service so the admin router stays declarative.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, update

from vidyalaya_ai.db.engine import session_scope
from vidyalaya_ai.db.models import (
    DailyUsage,
    StudentProfile,
    Subscription,
    UsageEvent,
    User,
)


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class AdminUserRow:
    """One row of the admin user list."""

    id: str
    firebase_uid: str
    email: str | None
    display_name: str | None
    role: str
    status: str
    quota_override: str | None
    plan_key: str | None
    created_at: datetime
    last_seen_at: datetime


@dataclass(frozen=True)
class UsageRollupRow:
    """Usage aggregated by day + agent."""

    day: str
    agent: str
    requests: int
    llm_calls: int
    tool_calls: int
    tokens_input: int
    tokens_output: int
    tokens_total: int


async def list_users(
    *, limit: int, offset: int, query: str | None = None
) -> tuple[list[AdminUserRow], int]:
    """Return a page of users (newest first) plus the total count.

    ``query`` filters by email or firebase_uid substring (case-insensitive).
    Each row's ``plan_key`` is its current subscription plan, or None (free).
    """
    async with session_scope() as session:
        base = select(User)
        count_stmt = select(func.count()).select_from(User)
        if query:
            pattern = f"%{query.strip()}%"
            cond = User.email.ilike(pattern) | User.firebase_uid.ilike(pattern)
            base = base.where(cond)
            count_stmt = count_stmt.where(cond)

        total = int((await session.execute(count_stmt)).scalar_one())
        rows = (
            (
                await session.execute(
                    base.order_by(User.created_at.desc()).limit(limit).offset(offset)
                )
            )
            .scalars()
            .all()
        )

        # Current plan per listed user in one query.
        uids = [u.firebase_uid for u in rows]
        plan_by_uid: dict[str, str] = {}
        if uids:
            sub_rows = (
                (
                    await session.execute(
                        select(Subscription.firebase_uid, Subscription.plan_key).where(
                            Subscription.firebase_uid.in_(uids),
                            Subscription.ended_at.is_(None),
                        )
                    )
                )
                .all()
            )
            plan_by_uid = {uid: plan for uid, plan in sub_rows}

    return (
        [
            AdminUserRow(
                id=str(u.id),
                firebase_uid=u.firebase_uid,
                email=u.email,
                display_name=u.display_name,
                role=u.role,
                status=u.status,
                quota_override=u.quota_override,
                plan_key=plan_by_uid.get(u.firebase_uid),
                created_at=u.created_at,
                last_seen_at=u.last_seen_at,
            )
            for u in rows
        ],
        total,
    )


async def get_user_detail(firebase_uid: str) -> dict[str, Any] | None:
    """Return a user with profile, current subscription, and recent usage.

    None if the user does not exist.
    """
    async with session_scope() as session:
        user = (
            await session.execute(
                select(User).where(User.firebase_uid == firebase_uid)
            )
        ).scalar_one_or_none()
        if user is None:
            return None

        profile = (
            await session.execute(
                select(StudentProfile).where(
                    StudentProfile.firebase_uid == firebase_uid
                )
            )
        ).scalar_one_or_none()

        sub = (
            await session.execute(
                select(Subscription)
                .where(
                    Subscription.firebase_uid == firebase_uid,
                    Subscription.ended_at.is_(None),
                )
                .order_by(Subscription.started_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    return {
        "user": user,
        "profile": profile,
        "subscription": sub,
    }


async def usage_rollup(
    firebase_uid: str, *, days: int = 30
) -> list[UsageRollupRow]:
    """Aggregate a user's usage_events by day + agent over the last ``days``."""
    since = _now() - timedelta(days=days)
    day_col = func.to_char(
        func.date_trunc("day", UsageEvent.created_at), "YYYY-MM-DD"
    ).label("day")
    async with session_scope() as session:
        rows = (
            await session.execute(
                select(
                    day_col,
                    UsageEvent.agent,
                    func.count().label("requests"),
                    func.coalesce(func.sum(UsageEvent.llm_calls), 0),
                    func.coalesce(func.sum(UsageEvent.tool_calls), 0),
                    func.coalesce(func.sum(UsageEvent.tokens_input), 0),
                    func.coalesce(func.sum(UsageEvent.tokens_output), 0),
                    func.coalesce(func.sum(UsageEvent.tokens_total), 0),
                )
                .where(
                    UsageEvent.firebase_uid == firebase_uid,
                    UsageEvent.created_at >= since,
                )
                .group_by(day_col, UsageEvent.agent)
                .order_by(day_col)
            )
        ).all()

    return [
        UsageRollupRow(
            day=r[0],
            agent=r[1],
            requests=int(r[2]),
            llm_calls=int(r[3]),
            tool_calls=int(r[4]),
            tokens_input=int(r[5]),
            tokens_output=int(r[6]),
            tokens_total=int(r[7]),
        )
        for r in rows
    ]


async def set_user_admin_fields(
    firebase_uid: str,
    *,
    quota_override: str | None = None,
    status: str | None = None,
    clear_quota_override: bool = False,
) -> User | None:
    """Update a user's quota_override and/or status. None if user missing.

    ``clear_quota_override=True`` removes the override (sets NULL); otherwise
    ``quota_override`` is applied only when provided.
    """
    values: dict[str, Any] = {}
    if clear_quota_override:
        values["quota_override"] = None
    elif quota_override is not None:
        values["quota_override"] = quota_override
    if status is not None:
        values["status"] = status

    async with session_scope() as session:
        if values:
            await session.execute(
                update(User)
                .where(User.firebase_uid == firebase_uid)
                .values(**values)
            )
            await session.commit()
        user = (
            await session.execute(
                select(User).where(User.firebase_uid == firebase_uid)
            )
        ).scalar_one_or_none()
    return user


async def global_stats(*, days: int = 1) -> dict[str, Any]:
    """Aggregate platform stats: today's activity, totals, per-agent split."""
    # Event-based window (usage_events.created_at); daily_usage uses IST date
    # strings and is the quota counter, not the analytics source.
    since = _now() - timedelta(days=days)
    async with session_scope() as session:
        total_users = int(
            (await session.execute(select(func.count()).select_from(User))).scalar_one()
        )
        active_users = int(
            (
                await session.execute(
                    select(func.count(func.distinct(UsageEvent.firebase_uid))).where(
                        UsageEvent.created_at >= since
                    )
                )
            ).scalar_one()
        )
        totals = (
            await session.execute(
                select(
                    func.count().label("requests"),
                    func.coalesce(func.sum(UsageEvent.tokens_total), 0),
                    func.coalesce(func.sum(UsageEvent.llm_calls), 0),
                ).where(UsageEvent.created_at >= since)
            )
        ).one()
        per_agent = (
            await session.execute(
                select(
                    UsageEvent.agent,
                    func.count(),
                    func.coalesce(func.sum(UsageEvent.tokens_total), 0),
                )
                .where(UsageEvent.created_at >= since)
                .group_by(UsageEvent.agent)
            )
        ).all()
        top_users = (
            await session.execute(
                select(
                    UsageEvent.firebase_uid,
                    func.count(),
                    func.coalesce(func.sum(UsageEvent.tokens_total), 0),
                )
                .where(UsageEvent.created_at >= since)
                .group_by(UsageEvent.firebase_uid)
                .order_by(func.count().desc())
                .limit(10)
            )
        ).all()

    return {
        "window_days": days,
        "total_users": total_users,
        "active_users": active_users,
        "requests": int(totals[0]),
        "tokens_total": int(totals[1]),
        "llm_calls": int(totals[2]),
        "per_agent": [
            {"agent": a, "requests": int(c), "tokens_total": int(t)}
            for a, c, t in per_agent
        ],
        "top_users": [
            {"firebase_uid": u, "requests": int(c), "tokens_total": int(t)}
            for u, c, t in top_users
        ],
    }
