"""subscriptions

Revision ID: 0003_subscriptions
Revises: 0002_messages_usage_events
Create Date: 2026-05-31

Phase 5 (subscription plans for quota + model selection).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = "0003_subscriptions"
down_revision: Union[str, None] = "0002_messages_usage_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("firebase_uid", sa.String(length=128), nullable=False),
        sa.Column("plan_key", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="admin"),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "cancel_at_period_end",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", JSONB(), nullable=True),
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
    )
    op.create_index(
        "ix_subscriptions_firebase_uid", "subscriptions", ["firebase_uid"]
    )
    op.create_index(
        "ix_subscriptions_user_ended", "subscriptions", ["firebase_uid", "ended_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_subscriptions_user_ended", table_name="subscriptions")
    op.drop_index("ix_subscriptions_firebase_uid", table_name="subscriptions")
    op.drop_table("subscriptions")
