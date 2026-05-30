"""baseline: users, student_profiles, daily_usage

Revision ID: 0001_baseline
Revises:
Create Date: 2026-05-30

Matches the initial Phase 1 schema. The LangGraph checkpoint tables are created
by AsyncPostgresSaver.setup(), not by Alembic.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("firebase_uid", sa.String(length=128), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("display_name", sa.String(length=256), nullable=True),
        sa.Column("role", sa.String(length=16), nullable=False, server_default="student"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("quota_override", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_users_firebase_uid", "users", ["firebase_uid"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=False)

    op.create_table(
        "student_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("firebase_uid", sa.String(length=128), nullable=False),
        sa.Column("board", sa.String(length=64), nullable=False),
        sa.Column("class_no", sa.Integer(), nullable=False),
        sa.Column("preferred_language", sa.String(length=32), nullable=False),
        sa.Column("school_name", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(
        "ix_student_profiles_firebase_uid",
        "student_profiles",
        ["firebase_uid"],
        unique=True,
    )

    op.create_table(
        "daily_usage",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("firebase_uid", sa.String(length=128), nullable=False),
        sa.Column("date_ist", sa.String(length=10), nullable=False),
        sa.Column("agent", sa.String(length=64), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "first_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "last_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "firebase_uid",
            "date_ist",
            "agent",
            name="uq_daily_usage_user_date_agent",
        ),
    )
    op.create_index(
        "ix_daily_usage_firebase_uid", "daily_usage", ["firebase_uid"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_daily_usage_firebase_uid", table_name="daily_usage")
    op.drop_table("daily_usage")
    op.drop_index("ix_student_profiles_firebase_uid", table_name="student_profiles")
    op.drop_table("student_profiles")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_firebase_uid", table_name="users")
    op.drop_table("users")
