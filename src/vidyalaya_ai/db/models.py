"""SQLAlchemy ORM models for app-owned tables.

Phase 1 covers identity + quota: ``users``, ``student_profiles``, ``daily_usage``.
The LangGraph checkpoint tables are created and owned by ``AsyncPostgresSaver``
(``await saver.setup()``), not declared here. Later phases add ``messages`` and
``usage_events``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
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
