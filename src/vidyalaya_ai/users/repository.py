"""Postgres repository functions for users and profiles.

Signatures match the previous Mongo repository so routers/dependencies are
unchanged. Upserts use ``INSERT ... ON CONFLICT DO UPDATE ... RETURNING`` for an
atomic create-or-refresh in one round trip.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from vidyalaya_ai.db.engine import session_scope
from vidyalaya_ai.db.models import StudentProfile, User
from vidyalaya_ai.users.models import PreferencesDoc, QuotaOverride, StudentProfileDoc, UserDoc


def _now() -> datetime:
    return datetime.now(UTC)


def _parse_quota_override(raw: str | None) -> QuotaOverride:
    """Convert the text-stored override back to its typed form."""
    if raw is None:
        return None
    if raw == "unlimited":
        return "unlimited"
    try:
        return int(raw)
    except ValueError:
        return None


def _user_to_doc(user: User) -> UserDoc:
    return UserDoc(
        id=str(user.id),
        firebase_uid=user.firebase_uid,
        email=user.email,
        display_name=user.display_name,
        role=user.role,  # type: ignore[arg-type]
        status=user.status,  # type: ignore[arg-type]
        quota_override=_parse_quota_override(user.quota_override),
        created_at=user.created_at,
        last_seen_at=user.last_seen_at,
    )


def _profile_to_doc(profile: StudentProfile) -> StudentProfileDoc:
    return StudentProfileDoc(
        id=str(profile.id),
        user_id=str(profile.user_id),
        firebase_uid=profile.firebase_uid,
        board=profile.board,
        class_no=profile.class_no,
        preferred_language=profile.preferred_language,
        school_name=profile.school_name,
        onboarding_completed=True,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


async def upsert_user_from_token(
    firebase_uid: str,
    email: str | None,
    name: str | None,
) -> UserDoc:
    """Create or refresh a user from a verified Firebase identity."""
    now = _now()
    # On insert: seed identity + defaults. On conflict: refresh the mutable
    # identity fields (display_name, last_seen, and email when present) but never
    # touch role/status/quota_override set elsewhere.
    update_on_conflict: dict[str, object] = {"display_name": name, "last_seen_at": now}
    if email is not None:
        update_on_conflict["email"] = email

    stmt = (
        insert(User)
        .values(
            firebase_uid=firebase_uid,
            email=email,
            display_name=name,
            role="student",
            status="active",
            quota_override=None,
            created_at=now,
            last_seen_at=now,
        )
        .on_conflict_do_update(
            index_elements=[User.firebase_uid],
            set_=update_on_conflict,
        )
        .returning(User)
    )

    async with session_scope() as session:
        result = await session.execute(stmt)
        user = result.scalar_one()
        await session.commit()
        return _user_to_doc(user)


async def get_user_by_firebase_uid(firebase_uid: str) -> UserDoc | None:
    """Fetch a user by Firebase UID."""
    async with session_scope() as session:
        result = await session.execute(
            select(User).where(User.firebase_uid == firebase_uid)
        )
        user = result.scalar_one_or_none()
        return _user_to_doc(user) if user is not None else None


async def get_profile(firebase_uid: str) -> StudentProfileDoc | None:
    """Fetch a student profile by Firebase UID."""
    async with session_scope() as session:
        result = await session.execute(
            select(StudentProfile).where(StudentProfile.firebase_uid == firebase_uid)
        )
        profile = result.scalar_one_or_none()
        return _profile_to_doc(profile) if profile is not None else None


async def get_preferences(firebase_uid: str) -> PreferencesDoc:
    """Return the student's session memory preferences.

    Falls back to defaults when the student has no profile yet so callers never
    need to handle None — a student without a profile gets the global defaults.
    """
    async with session_scope() as session:
        result = await session.execute(
            select(StudentProfile).where(StudentProfile.firebase_uid == firebase_uid)
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            # No profile → no student preference; caller uses env default.
            return PreferencesDoc(has_preference=False)
        return PreferencesDoc(
            memory_reset_enabled=profile.memory_reset_enabled,
            memory_reset_minutes=profile.memory_reset_minutes,
            has_preference=True,
        )


async def upsert_preferences(
    *,
    firebase_uid: str,
    memory_reset_enabled: bool,
    memory_reset_minutes: int,
) -> PreferencesDoc:
    """Update only the session memory preference columns on the student's profile.

    Raises 404 if the student has no profile (preferences require onboarding first).
    """
    now = _now()
    async with session_scope() as session:
        result = await session.execute(
            select(StudentProfile).where(StudentProfile.firebase_uid == firebase_uid)
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            raise ValueError("Profile not found; complete onboarding before updating preferences.")
        profile.memory_reset_enabled = memory_reset_enabled
        profile.memory_reset_minutes = memory_reset_minutes
        profile.updated_at = now
        await session.commit()
        return PreferencesDoc(
            memory_reset_enabled=profile.memory_reset_enabled,
            memory_reset_minutes=profile.memory_reset_minutes,
        )


async def upsert_profile(
    *,
    firebase_uid: str,
    user_id: str,
    board: str,
    class_no: int,
    preferred_language: str,
    school_name: str | None = None,
) -> StudentProfileDoc:
    """Create or update a student profile."""
    now = _now()
    stmt = (
        insert(StudentProfile)
        .values(
            user_id=user_id,
            firebase_uid=firebase_uid,
            board=board,
            class_no=class_no,
            preferred_language=preferred_language,
            school_name=school_name,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=[StudentProfile.firebase_uid],
            set_={
                "user_id": user_id,
                "board": board,
                "class_no": class_no,
                "preferred_language": preferred_language,
                "school_name": school_name,
                "updated_at": now,
            },
        )
        .returning(StudentProfile)
    )

    async with session_scope() as session:
        result = await session.execute(stmt)
        profile = result.scalar_one()
        await session.commit()
        return _profile_to_doc(profile)
