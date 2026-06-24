"""Vidyalaya AI — local API tester (entry page: auth + settings).

Developer-only multipage Streamlit app for exercising the Vidyalaya API end to
end against a local server. This page mints a Firebase ID token and stores it in
``st.session_state`` so the other pages (Chat, History, API Console) can reuse it.

Run from the repo root:

    .venv/bin/streamlit run devtools/streamlit/Home.py
"""

from __future__ import annotations

import firebase_admin
import streamlit as st

from _client import call_api, ensure_test_user, load_settings, mint_id_token

st.set_page_config(page_title="Vidyalaya API Tester", page_icon="🧪", layout="wide")
st.title("🧪 Vidyalaya AI — API Tester")
st.caption("Local developer tool. Mint a token here, then use the pages in the sidebar.")

default_web_key, default_base_url = load_settings()

# Initialize Firebase once so token minting works; surface config errors clearly.
if not firebase_admin._apps:
    try:
        from vidyalaya_ai.auth.firebase import initialize_firebase_app

        initialize_firebase_app()
    except Exception as exc:  # noqa: BLE001 - surface config errors in the UI.
        st.error(f"Firebase init failed: {exc}")
        st.stop()

with st.sidebar:
    st.header("Settings")
    base_url = st.text_input("API base URL", value=st.session_state.get("base_url", default_base_url))
    web_key = st.text_input(
        "Firebase Web API key",
        value=st.session_state.get("web_key", default_web_key or ""),
        type="password",
        help="Set FIREBASE_WEB_API_KEY in .env to avoid pasting it each time.",
    )
    st.session_state["base_url"] = base_url
    st.session_state["web_key"] = web_key

    if st.session_state.get("id_token"):
        st.success(f"Signed in as: {st.session_state.get('uid')}")
    else:
        st.warning("No token yet — generate one below.")

st.subheader("1. Create a Firebase ID token")
col_a, col_b = st.columns(2)
with col_a:
    uid = st.text_input("Firebase UID", value=st.session_state.get("uid", "local-test-user"))
    email = st.text_input("Email", value="local-test-user@example.com")
with col_b:
    display_name = st.text_input("Display name", value="Local Test User")

if st.button("Generate Firebase ID token", type="primary"):
    if not uid.strip():
        st.error("Firebase UID is required.")
    elif not web_key.strip():
        st.error("Firebase Web API key is required.")
    else:
        try:
            ensure_test_user(uid.strip(), email.strip() or None, display_name.strip() or None)
            token_response = mint_id_token(uid.strip(), web_key.strip())
            st.session_state["id_token"] = token_response["idToken"]
            st.session_state["refresh_token"] = token_response.get("refreshToken")
            st.session_state["uid"] = uid.strip()
            st.success("Firebase ID token generated. Open a page from the sidebar.")
        except Exception as exc:  # noqa: BLE001 - developer tool.
            st.error(str(exc))

id_token = st.session_state.get("id_token")
if id_token:
    with st.expander("Show ID token / Authorization header"):
        st.text_area("Firebase ID token", value=id_token, height=140)
        st.code(f"Authorization: Bearer {id_token}", language="http")

    st.subheader("2. Quick sanity checks")
    check_a, check_b = st.columns(2)
    with check_a:
        if st.button("GET /health"):
            st.json(call_api(base_url, "GET", "/health"))
    with check_b:
        if st.button("GET /auth/me"):
            st.json(call_api(base_url, "GET", "/auth/me", token=id_token))

    st.info("Next: open **Chat** (test LearnAssist + the get_chat_history tool), "
            "**History** (see persisted messages), or **API Console** (hit any endpoint).")
else:
    st.info("Generate a token above to unlock the test pages.")
