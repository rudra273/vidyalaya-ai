"""Admin API (Phase 6) — JSON only, gated by ``role == "admin"``.

Become an admin by setting ``users.role = 'admin'`` in the database. Every
route here depends on :func:`require_admin`, which 403s non-admins.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from vidyalaya_ai.admin import service as admin_service
from vidyalaya_ai.api.dependencies import require_admin
from vidyalaya_ai.api.schemas.admin import (
    AdminProfile,
    AdminStats,
    AdminSubscription,
    AdminUserDetail,
    AdminUserList,
    AdminUserSummary,
    AssignPlanRequest,
    CheckpointCleanupResponse,
    UpdateUserRequest,
    UsageRollupItem,
    UsageRollupResponse,
)
from vidyalaya_ai.maintenance import run_checkpoint_cleanup
from vidyalaya_ai.subscriptions import (
    assign_plan,
    is_valid_plan_key,
)


logger = logging.getLogger("vidyalaya_ai.api")
router = APIRouter(
    prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)]
)


def _summary(row: admin_service.AdminUserRow) -> AdminUserSummary:
    return AdminUserSummary(
        id=row.id,
        firebase_uid=row.firebase_uid,
        email=row.email,
        display_name=row.display_name,
        role=row.role,
        status=row.status,
        quota_override=row.quota_override,
        plan_key=row.plan_key,
        created_at=row.created_at,
        last_seen_at=row.last_seen_at,
    )


@router.get("/users", response_model=AdminUserList)
async def list_users(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, description="Filter by email or uid."),
) -> AdminUserList:
    """Paged user list (newest first), optionally filtered by email/uid."""
    rows, total = await admin_service.list_users(limit=limit, offset=offset, query=q)
    return AdminUserList(
        users=[_summary(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/stats", response_model=AdminStats)
async def stats(
    days: int = Query(default=1, ge=1, le=90),
) -> AdminStats:
    """Platform activity over the last ``days`` (default: today)."""
    data = await admin_service.global_stats(days=days)
    return AdminStats(**data)


@router.post("/maintenance/checkpoint-cleanup", response_model=CheckpointCleanupResponse)
async def checkpoint_cleanup(
    keep: int = Query(default=50, ge=1, le=1000),
    idle_days: int = Query(default=90, ge=1, le=3650),
) -> CheckpointCleanupResponse:
    """Prune LangGraph checkpoints (keep last N/thread; expire idle threads).

    Safe to call from a scheduler (e.g. Railway cron) with admin credentials.
    """
    result = await run_checkpoint_cleanup(keep_last_n=keep, idle_expire_days=idle_days)
    return CheckpointCleanupResponse(
        checkpoints_deleted=result.checkpoints_deleted,
        writes_deleted=result.writes_deleted,
        blobs_deleted=result.blobs_deleted,
    )


@router.get("/users/{firebase_uid}", response_model=AdminUserDetail)
async def get_user(firebase_uid: str) -> AdminUserDetail:
    """User identity + profile + current subscription."""
    detail = await admin_service.get_user_detail(firebase_uid)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    user = detail["user"]
    profile = detail["profile"]
    sub = detail["subscription"]
    return AdminUserDetail(
        user=AdminUserSummary(
            id=str(user.id),
            firebase_uid=user.firebase_uid,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            status=user.status,
            quota_override=user.quota_override,
            plan_key=sub.plan_key if sub is not None else None,
            created_at=user.created_at,
            last_seen_at=user.last_seen_at,
        ),
        profile=(
            AdminProfile(
                board=profile.board,
                class_no=profile.class_no,
                preferred_language=profile.preferred_language,
                school_name=profile.school_name,
            )
            if profile is not None
            else None
        ),
        subscription=(
            AdminSubscription(
                plan_key=sub.plan_key,
                status=sub.status,
                source=sub.source,
                current_period_end=sub.current_period_end,
                cancel_at_period_end=sub.cancel_at_period_end,
                started_at=sub.started_at,
            )
            if sub is not None
            else None
        ),
    )


@router.get("/users/{firebase_uid}/usage", response_model=UsageRollupResponse)
async def user_usage(
    firebase_uid: str,
    days: int = Query(default=30, ge=1, le=365),
) -> UsageRollupResponse:
    """Usage rolled up by day + agent for a user."""
    rows = await admin_service.usage_rollup(firebase_uid, days=days)
    return UsageRollupResponse(
        firebase_uid=firebase_uid,
        days=days,
        items=[
            UsageRollupItem(
                day=r.day,
                agent=r.agent,
                requests=r.requests,
                llm_calls=r.llm_calls,
                tool_calls=r.tool_calls,
                tokens_input=r.tokens_input,
                tokens_output=r.tokens_output,
                tokens_total=r.tokens_total,
            )
            for r in rows
        ],
    )


@router.patch("/users/{firebase_uid}", response_model=AdminUserSummary)
async def update_user(
    firebase_uid: str,
    payload: UpdateUserRequest,
) -> AdminUserSummary:
    """Set a user's quota override and/or account status."""
    user = await admin_service.set_user_admin_fields(
        firebase_uid,
        quota_override=payload.quota_override,
        status=payload.status,
        clear_quota_override=payload.clear_quota_override,
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    # The auth cache may hold a stale copy; it expires within the TTL.
    return AdminUserSummary(
        id=str(user.id),
        firebase_uid=user.firebase_uid,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        status=user.status,
        quota_override=user.quota_override,
        plan_key=None,
        created_at=user.created_at,
        last_seen_at=user.last_seen_at,
    )


@router.patch("/users/{firebase_uid}/subscription", response_model=AdminSubscription)
async def assign_user_plan(
    firebase_uid: str,
    payload: AssignPlanRequest,
) -> AdminSubscription:
    """Assign a plan: closes the current subscription row and opens a new one."""
    if not is_valid_plan_key(payload.plan_key):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unknown plan_key.",
        )
    detail = await admin_service.get_user_detail(firebase_uid)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    view = await assign_plan(
        firebase_uid=firebase_uid,
        user_id=str(detail["user"].id),
        plan_key=payload.plan_key,
        status=payload.status,
        source="admin",
        current_period_end=payload.current_period_end,
    )
    return AdminSubscription(
        plan_key=view.plan_key,
        status=view.status,
        source=view.source,
        current_period_end=view.current_period_end,
        cancel_at_period_end=view.cancel_at_period_end,
        started_at=view.started_at,
    )
