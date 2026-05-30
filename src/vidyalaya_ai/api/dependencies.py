"""Reusable FastAPI dependencies."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as firebase_auth

from vidyalaya_ai.auth.firebase import verify_firebase_id_token
from vidyalaya_ai.auth.models import AuthenticatedUser
from vidyalaya_ai.subscriptions import resolve_plan
from vidyalaya_ai.users.repository import upsert_user_from_token


logger = logging.getLogger("vidyalaya_ai.api")
bearer_scheme = HTTPBearer(auto_error=False)
USER_CACHE_TTL_SECONDS = 60
USER_CACHE_MAX_SIZE = 10_000


@dataclass(frozen=True)
class _CachedUser:
    expires_at: float
    user: AuthenticatedUser


_user_cache: dict[str, _CachedUser] = {}


def _cache_user(firebase_uid: str, user: AuthenticatedUser) -> None:
    """Store a user in the bounded cache, evicting expired/oldest entries first."""
    now = time.monotonic()
    if len(_user_cache) >= USER_CACHE_MAX_SIZE:
        expired = [uid for uid, entry in _user_cache.items() if entry.expires_at <= now]
        for uid in expired:
            del _user_cache[uid]
        # Still full after pruning expired entries: drop the oldest to make room.
        while len(_user_cache) >= USER_CACHE_MAX_SIZE:
            oldest = min(_user_cache, key=lambda uid: _user_cache[uid].expires_at)
            del _user_cache[oldest]
    _user_cache[firebase_uid] = _CachedUser(
        expires_at=now + USER_CACHE_TTL_SECONDS,
        user=user,
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthenticatedUser:
    """Return the authenticated Firebase user for protected routes."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
        )

    try:
        firebase_user = verify_firebase_id_token(credentials.credentials)
    except (
        firebase_auth.InvalidIdTokenError,
        firebase_auth.ExpiredIdTokenError,
        firebase_auth.RevokedIdTokenError,
        firebase_auth.UserDisabledError,
        firebase_auth.CertificateFetchError,
        ValueError,
    ):
        logger.warning("Firebase token verification failed", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired bearer token.",
        ) from None

    firebase_uid = firebase_user.firebase_uid or firebase_user.user_id
    cached = _user_cache.get(firebase_uid)
    if cached and cached.expires_at > time.monotonic():
        logger.debug("Auth user cache hit uid=%s", firebase_uid)
        return cached.user

    user_doc = await upsert_user_from_token(
        firebase_uid=firebase_uid,
        email=firebase_user.email,
        name=firebase_user.name,
    )
    if user_doc.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active.",
        )

    # Resolve the effective plan once at auth time; cached with the user for the
    # cache TTL so a plan change takes effect within ~60s without per-request DB
    # reads on the chat hot path.
    plan = await resolve_plan(firebase_uid)

    user = AuthenticatedUser(
        user_id=firebase_uid,
        firebase_uid=firebase_uid,
        db_id=user_doc.id,
        email=user_doc.email,
        name=user_doc.display_name,
        role=user_doc.role,
        status=user_doc.status,
        quota_override=user_doc.quota_override,
        plan_key=plan.key,
        plan_daily_limit=plan.daily_limit,
        plan_provider=plan.provider,
        plan_model=plan.model,
    )
    _cache_user(firebase_uid, user)
    return user


async def require_admin(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    """Gate admin routes on ``role == "admin"`` (403 otherwise).

    Admin is granted by setting ``users.role = 'admin'`` directly in the DB.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return current_user
