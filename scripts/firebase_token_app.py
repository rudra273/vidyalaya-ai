"""Streamlit helper for minting Firebase ID tokens and testing local APIs.

This is a developer-only tool. It uses the Firebase Admin service account from
``FIREBASE_SERVICE_ACCOUNT_JSON_BASE64`` to create/update a test Firebase user,
then exchanges a custom token for a Firebase ID token through Firebase Auth's
REST API.
"""

from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import firebase_admin
import streamlit as st
from dotenv import load_dotenv
from firebase_admin import auth

from vidyalaya_ai.auth.firebase import initialize_firebase_app


FIREBASE_EXCHANGE_URL = (
    "https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={api_key}"
)


def _load_settings() -> tuple[str | None, str]:
    load_dotenv(".env")
    return os.getenv("FIREBASE_WEB_API_KEY"), os.getenv(
        "VIDYALAYA_API_BASE_URL",
        "http://localhost:8000",
    )


def _json_request(
    url: str,
    payload: dict[str, Any] | None = None,
    *,
    bearer_token: str | None = None,
    method: str | None = None,
) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"

    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=60) as response:
            text = response.read().decode("utf-8")
            return json.loads(text) if text else {}
    except HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        try:
            detail: Any = json.loads(text)
        except json.JSONDecodeError:
            detail = text
        raise RuntimeError(f"{exc.code} {exc.reason}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Request failed: {exc.reason}") from exc


def _ensure_test_user(uid: str, email: str | None, display_name: str | None) -> None:
    initialize_firebase_app()
    update_kwargs: dict[str, Any] = {}
    if email:
        update_kwargs["email"] = email
        update_kwargs["email_verified"] = True
    if display_name:
        update_kwargs["display_name"] = display_name

    try:
        auth.get_user(uid)
        if update_kwargs:
            auth.update_user(uid, **update_kwargs)
    except auth.UserNotFoundError:
        auth.create_user(uid=uid, **update_kwargs)


def _mint_id_token(uid: str, api_key: str) -> dict[str, Any]:
    app = initialize_firebase_app()
    custom_token = auth.create_custom_token(uid, app=app).decode("utf-8")
    payload = {"token": custom_token, "returnSecureToken": True}
    return _json_request(FIREBASE_EXCHANGE_URL.format(api_key=api_key), payload)


def _api_get(api_base_url: str, path: str, id_token: str) -> dict[str, Any]:
    return _json_request(f"{api_base_url.rstrip('/')}{path}", bearer_token=id_token)


def _api_post(
    api_base_url: str,
    path: str,
    id_token: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return _json_request(
        f"{api_base_url.rstrip('/')}{path}",
        payload,
        bearer_token=id_token,
        method="POST",
    )


st.set_page_config(page_title="Vidyalaya Firebase Token Tester", page_icon="key", layout="wide")
st.title("Vidyalaya Firebase Token Tester")

firebase_web_api_key, default_api_base_url = _load_settings()

if not firebase_admin._apps:
    try:
        initialize_firebase_app()
    except Exception as exc:  # noqa: BLE001 - surface config errors in the UI.
        st.error(str(exc))
        st.stop()

with st.sidebar:
    st.header("Settings")
    api_base_url = st.text_input("API base URL", value=default_api_base_url)
    web_api_key = st.text_input(
        "Firebase Web API key",
        value=firebase_web_api_key or "",
        type="password",
        help="Set FIREBASE_WEB_API_KEY in .env to avoid pasting it each time.",
    )

st.subheader("Create ID token")
col_a, col_b = st.columns(2)
with col_a:
    uid = st.text_input("Firebase UID", value="local-test-user")
    email = st.text_input("Email", value="local-test-user@example.com")
with col_b:
    display_name = st.text_input("Display name", value="Local Test User")

if st.button("Generate Firebase ID token", type="primary"):
    if not uid.strip():
        st.error("Firebase UID is required.")
    elif not web_api_key.strip():
        st.error("Firebase Web API key is required.")
    else:
        try:
            _ensure_test_user(uid.strip(), email.strip() or None, display_name.strip() or None)
            token_response = _mint_id_token(uid.strip(), web_api_key.strip())
            st.session_state["id_token"] = token_response["idToken"]
            st.session_state["refresh_token"] = token_response.get("refreshToken")
            st.session_state["uid"] = uid.strip()
            st.success("Firebase ID token generated.")
        except Exception as exc:  # noqa: BLE001 - developer tool.
            st.error(str(exc))

id_token = st.session_state.get("id_token")
if id_token:
    st.text_area("Firebase ID token", value=id_token, height=180)
    st.code(f'Authorization: Bearer {id_token}', language="http")

    st.subheader("Quick API tests")
    test_col_a, test_col_b = st.columns(2)

    with test_col_a:
        if st.button("GET /auth/me"):
            try:
                st.json(_api_get(api_base_url, "/auth/me", id_token))
            except Exception as exc:  # noqa: BLE001 - developer tool.
                st.error(str(exc))

        if st.button("GET /me/usage"):
            try:
                st.json(_api_get(api_base_url, "/me/usage", id_token))
            except Exception as exc:  # noqa: BLE001 - developer tool.
                st.error(str(exc))

    with test_col_b:
        message = st.text_area("Message", value="Explain photosynthesis in simple words.")
        subject = st.selectbox(
            "Subject",
            ["science", "maths", "english", "hindi", "odia", "sanskrit", "social_science", ""],
        )
        uploaded_image = st.file_uploader(
            "Image (optional)",
            type=["jpg", "jpeg", "png", "webp"],
            help="Attach a photo of notes/assignment. Message becomes optional when set.",
        )
        debug = st.checkbox("Debug retrieval", value=False)
        if st.button("POST /learnassist/chat"):
            payload: dict[str, Any] = {
                "message": message or None,
                "board": "scert_odisha",
                "class_no": 8,
                "subject": subject or None,
                "language": "en",
                "debug": debug,
            }
            if uploaded_image is not None:
                image_bytes = uploaded_image.getvalue()
                media_type = uploaded_image.type or "image/jpeg"
                # Normalize the jpg shorthand Streamlit may report.
                if media_type == "image/jpg":
                    media_type = "image/jpeg"
                payload["image_base64"] = base64.b64encode(image_bytes).decode("ascii")
                payload["image_media_type"] = media_type
                st.image(image_bytes, caption=f"{media_type} ({len(image_bytes)} bytes)", width=200)
            try:
                st.json(_api_post(api_base_url, "/learnassist/chat", id_token, payload))
            except Exception as exc:  # noqa: BLE001 - developer tool.
                st.error(str(exc))
