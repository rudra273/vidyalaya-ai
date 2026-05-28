"""Reusable FastAPI dependencies."""

from __future__ import annotations

import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as firebase_auth

from vidyalaya_ai.auth.firebase import verify_firebase_id_token
from vidyalaya_ai.auth.models import AuthenticatedUser


logger = logging.getLogger("vidyalaya_ai.api")
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthenticatedUser:
    """Return the authenticated Firebase user for protected routes."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
        )

    try:
        user = verify_firebase_id_token(credentials.credentials)
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

    return user
