"""SQLAlchemy ORM models for app-owned tables.

Identity + quota: ``users``, ``student_profiles``, ``daily_usage``. Chat history
+ analytics: ``messages``, ``usage_events``. Plan assignment: ``subscriptions``.
The LangGraph checkpoint tables are created and owned by ``AsyncPostgresSaver``
(``await saver.setup()``), not declared here.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vidyalaya_ai.db.base import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class User(Base):
    """Application user — identity, role, status, and per-user overrides."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    firebase_uid: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    # Non-unique on purpose: one email can map to multiple Firebase UIDs across
    # providers; identity is keyed by firebase_uid.
    email: Mapped[str | None] = mapped_column(String(320), index=True, default=None)
    display_name: Mapped[str | None] = mapped_column(String(256), default=None)
    role: Mapped[str] = mapped_column(String(16), default="student")
    status: Mapped[str] = mapped_column(String(16), default="active")
    # Quota override: NULL = default limit, "unlimited", or an integer-as-text.
    quota_override: Mapped[str | None] = mapped_column(String(32), default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    profile: Mapped["StudentProfile | None"] = relationship(
        back_populates="user", uselist=False
    )


class Subscription(Base):
    """Plan assignment for a user — chooses quota + LLM provider/model.

    One *current* row per user has ``ended_at IS NULL``; assigning a new plan
    closes the previous current row and inserts a new one (audit trail). The
    plan itself (quota numbers, model id) is defined in code
    (``subscriptions/plans.py``); this table only records which ``plan_key`` a
    user holds and its lifecycle. Columns beyond plan_key/status are present now
    so a payment provider (Razorpay/Stripe) can be wired in later without a
    schema change.
    """

    __tablename__ = "subscriptions"
    __table_args__ = (
        # Resolving a user's current plan: filter by user, current row first.
        Index("ix_subscriptions_user_ended", "firebase_uid", "ended_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    firebase_uid: Mapped[str] = mapped_column(String(128), index=True)
    plan_key: Mapped[str] = mapped_column(String(32))  # free | plus | pro
    # active | trialing | past_due | cancelled | expired
    status: Mapped[str] = mapped_column(String(16), default="active")
    source: Mapped[str] = mapped_column(String(32), default="admin")  # admin | manual | razorpay | stripe
    current_period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # NULL marks the user's current assignment; set when superseded/cancelled.
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    extra_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class StudentProfile(Base):
    """Student onboarding/profile: board, class, language."""

    __tablename__ = "student_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
    )
    firebase_uid: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    board: Mapped[str] = mapped_column(String(64))
    class_no: Mapped[int] = mapped_column(Integer)
    preferred_language: Mapped[str] = mapped_column(String(32))
    school_name: Mapped[str | None] = mapped_column(String(128), default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="profile")


class DailyUsage(Base):
    """Per-user, per-day, per-agent quota counter (blocking hot path)."""

    __tablename__ = "daily_usage"
    __table_args__ = (
        UniqueConstraint(
            "firebase_uid", "date_ist", "agent", name="uq_daily_usage_user_date_agent"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    firebase_uid: Mapped[str] = mapped_column(String(128), index=True)
    date_ist: Mapped[str] = mapped_column(String(10))  # YYYY-MM-DD in IST
    agent: Mapped[str] = mapped_column(String(64))
    count: Mapped[int] = mapped_column(Integer, default=0)
    first_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Message(Base):
    """Permanent, display-only chat history for scroll-back.

    Independent of the agent checkpointer: checkpoints can be pruned for cost
    without losing what the student sees. One continuous chat per student, so
    ``thread_id`` is currently ``learnassist:{firebase_uid}`` but stored so other
    agents/threads can be added later.
    """

    __tablename__ = "messages"
    __table_args__ = (
        # Scroll-back queries page by user, newest-first, then reverse.
        Index("ix_messages_user_created", "firebase_uid", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    firebase_uid: Mapped[str] = mapped_column(String(128))
    # {channel}:{uid<=128}:{board}:{class}:{subject} -> up to ~172 chars; 200 leaves headroom.
    thread_id: Mapped[str] = mapped_column(String(200))
    agent: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(16))  # "human" | "ai"
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[list | None] = mapped_column(JSONB, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class UsageEvent(Base):
    """Per-turn analytics log (written non-blocking after the response).

    Distinct from ``daily_usage``: that is the blocking quota counter on the hot
    path; this is fire-and-forget analytics, so a rare lost row never affects
    quota or correctness.
    """

    __tablename__ = "usage_events"
    __table_args__ = (
        Index("ix_usage_events_user_created", "firebase_uid", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    firebase_uid: Mapped[str] = mapped_column(String(128))
    agent: Mapped[str] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(128), default=None)
    llm_calls: Mapped[int] = mapped_column(Integer, default=0)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    tokens_input: Mapped[int] = mapped_column(Integer, default=0)
    tokens_output: Mapped[int] = mapped_column(Integer, default=0)
    tokens_total: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
