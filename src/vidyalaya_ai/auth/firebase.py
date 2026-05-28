"""Firebase Admin token verification."""

from __future__ import annotations

import base64
import json
import logging
from functools import lru_cache
from typing import Any

import firebase_admin
from firebase_admin import auth, credentials

from vidyalaya_ai.auth.config import FirebaseAuthConfig, load_firebase_auth_config
from vidyalaya_ai.auth.models import AuthenticatedUser


logger = logging.getLogger("vidyalaya_ai.api")


@lru_cache(maxsize=1)
def initialize_firebase_app() -> firebase_admin.App:
    """Initialize Firebase Admin once."""
    if firebase_admin._apps:
        return firebase_admin.get_app()

    config = load_firebase_auth_config()
    service_account_info = _decode_service_account(config)
    app = firebase_admin.initialize_app(credentials.Certificate(service_account_info))
    logger.info("Firebase Admin initialized")
    return app


def verify_firebase_id_token(id_token: str) -> AuthenticatedUser:
    """Verify a Firebase ID token and return user identity."""
    app = initialize_firebase_app()
    decoded_token = auth.verify_id_token(id_token, app=app)
    return _user_from_decoded_token(decoded_token)


def _decode_service_account(config: FirebaseAuthConfig) -> dict[str, Any]:
    """Decode base64 service account JSON from environment config."""
    try:
        decoded = base64.b64decode(config.service_account_json_base64).decode("utf-8")
        service_account_info = json.loads(decoded)
    except Exception as exc:
        raise RuntimeError("Invalid FIREBASE_SERVICE_ACCOUNT_JSON_BASE64 value.") from exc

    if not isinstance(service_account_info, dict):
        raise RuntimeError("Firebase service account must decode to a JSON object.")

    return service_account_info


def _user_from_decoded_token(decoded_token: dict[str, Any]) -> AuthenticatedUser:
    """Build an authenticated user from a decoded Firebase token."""
    uid = decoded_token.get("uid") or decoded_token.get("sub")
    if not uid:
        raise RuntimeError("Firebase token does not contain uid.")

    return AuthenticatedUser(
        user_id=str(uid),
        firebase_uid=str(uid),
        email=decoded_token.get("email"),
        name=decoded_token.get("name"),
    )
