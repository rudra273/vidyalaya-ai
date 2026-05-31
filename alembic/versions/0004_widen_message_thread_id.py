"""widen messages.thread_id for channel-scoped thread ids

Revision ID: 0004_widen_message_thread_id
Revises: 0003_subscriptions
Create Date: 2026-05-31

Channel memory architecture (plan.md §4b): thread ids are now
``{channel}:{uid}:{board}:{class_no}:{subject}`` which can reach ~172 chars, so
the 160-char column must grow. 200 leaves headroom.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0004_widen_message_thread_id"
down_revision: Union[str, None] = "0003_subscriptions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "messages",
        "thread_id",
        existing_type=sa.String(length=160),
        type_=sa.String(length=200),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "messages",
        "thread_id",
        existing_type=sa.String(length=200),
        type_=sa.String(length=160),
        existing_nullable=False,
    )
