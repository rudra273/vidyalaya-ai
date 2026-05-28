"""MongoDB repository functions for users and profiles."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pymongo import ReturnDocument

from vidyalaya_ai.db.mongo import get_db
from vidyalaya_ai.users.models import StudentProfileDoc, UserDoc


def _now() -> datetime:
    return datetime.now(UTC)


def _stringify_id(document: dict[str, Any]) -> dict[str, Any]:
    document = dict(document)
    document["_id"] = str(document["_id"])
    if "user_id" in document:
        document["user_id"] = str(document["user_id"])
    return document


async def upsert_user_from_token(
    firebase_uid: str,
    email: str | None,
    name: str | None,
) -> UserDoc:
    """Create or refresh a user from a verified Firebase identity."""
    now = _now()
    set_fields: dict[str, Any] = {
        "display_name": name,
        "last_seen_at": now,
    }
    if email is not None:
        set_fields["email"] = email

    update: dict[str, Any] = {
        "$set": set_fields,
        "$setOnInsert": {
            "firebase_uid": firebase_uid,
            "role": "student",
            "status": "active",
            "quota_override": None,
            "created_at": now,
            "schema_version": 1,
        },
    }
    if email is None:
        update["$unset"] = {"email": ""}

    document = await get_db().users.find_one_and_update(
        {"firebase_uid": firebase_uid},
        update,
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return UserDoc.model_validate(_stringify_id(document))


async def get_user_by_firebase_uid(firebase_uid: str) -> UserDoc | None:
    """Fetch a user by Firebase UID."""
    document = await get_db().users.find_one({"firebase_uid": firebase_uid})
    if document is None:
        return None
    return UserDoc.model_validate(_stringify_id(document))


async def get_profile(firebase_uid: str) -> StudentProfileDoc | None:
    """Fetch a student profile by Firebase UID."""
    document = await get_db().student_profiles.find_one({"firebase_uid": firebase_uid})
    if document is None:
        return None
    return StudentProfileDoc.model_validate(_stringify_id(document))


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
    document = await get_db().student_profiles.find_one_and_update(
        {"firebase_uid": firebase_uid},
        {
            "$set": {
                "user_id": user_id,
                "board": board,
                "class_no": class_no,
                "preferred_language": preferred_language,
                "school_name": school_name,
                "onboarding_completed": True,
                "updated_at": now,
                "schema_version": 1,
            },
            "$setOnInsert": {
                "firebase_uid": firebase_uid,
                "created_at": now,
            },
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return StudentProfileDoc.model_validate(_stringify_id(document))
