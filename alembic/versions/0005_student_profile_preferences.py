"""Add memory preference columns to student_profiles

Revision ID: 0005_student_profile_preferences
Revises: 0004_widen_message_thread_id
Create Date: 2026-06-02

Adds memory_reset_enabled (bool, default true) and memory_reset_minutes (int,
default 30) to student_profiles so students can control the 30-min inactivity
memory reset from the app settings. Existing rows are backfilled to the defaults
so no row is left with NULL.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0005_student_profile_preferences"
down_revision: Union[str, None] = "0004_widen_message_thread_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "student_profiles",
        sa.Column(
            "memory_reset_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "student_profiles",
        sa.Column(
            "memory_reset_minutes",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("30"),
        ),
    )


def downgrade() -> None:
    op.drop_column("student_profiles", "memory_reset_minutes")
    op.drop_column("student_profiles", "memory_reset_enabled")
