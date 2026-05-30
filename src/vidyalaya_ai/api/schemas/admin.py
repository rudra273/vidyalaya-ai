"""Schemas for the admin API (Phase 6)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


class AdminUserSummary(BaseModel):
    """One user in the admin list."""

    id: str
    firebase_uid: str
    email: str | None = None
    display_name: str | None = None
    role: str
    status: str
    quota_override: str | None = None
    plan_key: str | None = None
    created_at: datetime
    last_seen_at: datetime


class AdminUserList(BaseModel):
    """Paged user list."""

    users: list[AdminUserSummary]
    total: int
    limit: int
    offset: int


class AdminProfile(BaseModel):
    """Profile block in the user detail view."""

    board: str
    class_no: int
    preferred_language: str
    school_name: str | None = None


class AdminSubscription(BaseModel):
    """Current subscription block in the user detail view."""

    plan_key: str
    status: str
    source: str
    current_period_end: datetime | None = None
    cancel_at_period_end: bool
    started_at: datetime


class AdminUserDetail(BaseModel):
    """Full user detail: identity + profile + current subscription."""

    user: AdminUserSummary
    profile: AdminProfile | None = None
    subscription: AdminSubscription | None = None


class UsageRollupItem(BaseModel):
    """Usage aggregated by day + agent."""

    day: str
    agent: str
    requests: int
    llm_calls: int
    tool_calls: int
    tokens_input: int
    tokens_output: int
    tokens_total: int


class UsageRollupResponse(BaseModel):
    """A user's usage rollup over a window."""

    firebase_uid: str
    days: int
    items: list[UsageRollupItem]


class UpdateUserRequest(BaseModel):
    """Set quota override and/or account status.

    ``quota_override`` accepts ``"unlimited"`` or an integer-as-string; pass
    ``null`` with ``clear_quota_override=true`` to remove it. ``status`` is one
    of active/suspended/deleted.
    """

    quota_override: str | None = None
    clear_quota_override: bool = False
    status: str | None = Field(default=None)

    @model_validator(mode="after")
    def validate_status(self) -> "UpdateUserRequest":
        if self.status is not None and self.status not in {
            "active",
            "suspended",
            "deleted",
        }:
            raise ValueError("status must be active, suspended, or deleted")
        if self.quota_override is not None and self.quota_override != "unlimited":
            try:
                int(self.quota_override)
            except ValueError as exc:
                raise ValueError(
                    "quota_override must be 'unlimited' or an integer string"
                ) from exc
        return self


class AssignPlanRequest(BaseModel):
    """Manually assign a subscription plan to a user."""

    plan_key: str
    status: str = "active"
    current_period_end: datetime | None = None


class CheckpointCleanupResponse(BaseModel):
    """Result of a checkpoint cleanup run."""

    checkpoints_deleted: int
    writes_deleted: int
    blobs_deleted: int


class AdminStats(BaseModel):
    """Platform stats over a window."""

    window_days: int
    total_users: int
    active_users: int
    requests: int
    tokens_total: int
    llm_calls: int
    per_agent: list[dict[str, Any]]
    top_users: list[dict[str, Any]]
