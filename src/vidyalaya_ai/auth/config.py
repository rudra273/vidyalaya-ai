"""Firebase authentication configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class FirebaseAuthConfig:
    """Runtime settings for Firebase Admin authentication."""

    service_account_json_base64: str


def load_firebase_auth_config(env_path: str = ".env") -> FirebaseAuthConfig:
    """Load Firebase auth settings from environment variables."""
    load_dotenv(env_path)
    service_account_json_base64 = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON_BASE64")
    if not service_account_json_base64:
        raise RuntimeError("FIREBASE_SERVICE_ACCOUNT_JSON_BASE64 is not set.")

    return FirebaseAuthConfig(service_account_json_base64=service_account_json_base64)
