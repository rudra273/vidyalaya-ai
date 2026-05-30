"""Subscription resolution + assignment.

``resolve_plan`` reads a user's *current* subscription row (``ended_at IS NULL``)
and returns the effective :class:`Plan`. No current row, or a current row whose
status is not entitled (cancelled/expired/past_due), resolves to ``free``.

``assign_plan`` is the admin write path: it closes the user's current row and
inserts a new current row (audit trail), so plan history is preserved.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, update

from vidyalaya_ai.db.engine import session_scope
from vidyalaya_ai.db.models import Subscription
from vidyalaya_ai.subscriptions.plans import (
    DEFAULT_PLAN_KEY,
    ENTITLED_STATUSES,
    Plan,
    get_plan,
)


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class SubscriptionView:
    """API-facing view of a user's current subscription."""

    plan_key: str
    status: str
    source: str
    current_period_end: datetime | None
    cancel_at_period_end: bool
    started_at: datetime


async def _current_row(session, firebase_uid: str) -> Subscription | None:
    result = await session.execute(
        select(Subscription)
        .where(
            Subscription.firebase_uid == firebase_uid,
            Subscription.ended_at.is_(None),
        )
        .order_by(Subscription.started_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def resolve_plan(firebase_uid: str) -> Plan:
    """Return the user's effective plan (free when no entitled subscription)."""
    async with session_scope() as session:
        row = await _current_row(session, firebase_uid)
    if row is None or row.status not in ENTITLED_STATUSES:
        return get_plan(DEFAULT_PLAN_KEY)
    return get_plan(row.plan_key)


async def get_current_subscription(firebase_uid: str) -> SubscriptionView | None:
    """Return the user's current subscription row, or None (implicit free)."""
    async with session_scope() as session:
        row = await _current_row(session, firebase_uid)
    if row is None:
        return None
    return SubscriptionView(
        plan_key=row.plan_key,
        status=row.status,
        source=row.source,
        current_period_end=row.current_period_end,
        cancel_at_period_end=row.cancel_at_period_end,
        started_at=row.started_at,
    )


async def assign_plan(
    *,
    firebase_uid: str,
    user_id: str,
    plan_key: str,
    status: str = "active",
    source: str = "admin",
    current_period_end: datetime | None = None,
) -> SubscriptionView:
    """Assign a plan: close the current row and insert a new current row.

    Idempotent in spirit but always creates a new row so the assignment history
    is auditable. Callers validate ``plan_key`` against the defined plans first.
    """
    now = _now()
    async with session_scope() as session:
        # Close any open current rows for this user.
        await session.execute(
            update(Subscription)
            .where(
                Subscription.firebase_uid == firebase_uid,
                Subscription.ended_at.is_(None),
            )
            .values(ended_at=now, updated_at=now)
        )
        row = Subscription(
            user_id=user_id,
            firebase_uid=firebase_uid,
            plan_key=plan_key,
            status=status,
            source=source,
            current_period_end=current_period_end,
            started_at=now,
        )
        session.add(row)
        await session.commit()
        return SubscriptionView(
            plan_key=row.plan_key,
            status=row.status,
            source=row.source,
            current_period_end=row.current_period_end,
            cancel_at_period_end=row.cancel_at_period_end,
            started_at=row.started_at,
        )
