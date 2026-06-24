"""Generic API console — call any Vidyalaya endpoint end to end.

A free-form request builder (method + path + query + JSON body) plus quick
buttons and small forms for the common endpoints, so the whole API surface
(auth, me/profile, me/usage, me/preferences, admin, …) can be exercised without
leaving Streamlit.
"""

from __future__ import annotations

import json

import streamlit as st

from _client import call_api

st.set_page_config(page_title="API Console · Vidyalaya Tester", page_icon="🛠️", layout="wide")
st.title("🛠️ API Console")

token = st.session_state.get("id_token")
base_url = st.session_state.get("base_url", "http://localhost:8000")
if not token:
    st.warning("No token. Go to **Home** and generate a Firebase ID token first.")
    st.stop()


def show(result: dict) -> None:
    badge = "✅" if result["ok"] else "❌"
    st.write(f"{badge} HTTP {result['status']}")
    st.json(result["data"])


st.subheader("Quick calls")
quick = {
    "GET /auth/me": ("GET", "/auth/me"),
    "GET /me/profile": ("GET", "/me/profile"),
    "GET /me/usage": ("GET", "/me/usage"),
    "GET /me/preferences": ("GET", "/me/preferences"),
    "GET /health": ("GET", "/health"),
    "GET /admin/stats": ("GET", "/admin/stats"),
    "GET /admin/users": ("GET", "/admin/users"),
}
cols = st.columns(4)
for idx, (label, (method, path)) in enumerate(quick.items()):
    if cols[idx % 4].button(label):
        show(call_api(base_url, method, path, token=token))

st.divider()
st.subheader("Forms")

tab_profile, tab_prefs = st.tabs(["PUT /me/profile", "PUT /me/preferences"])

with tab_profile:
    p_board = st.text_input("board", value="scert_odisha", key="prof_board")
    p_class = st.number_input("class_no", min_value=1, max_value=12, value=8, key="prof_class")
    p_lang = st.text_input("preferred_language", value="en", key="prof_lang")
    p_school = st.text_input("school_name (optional)", value="", key="prof_school")
    p_name = st.text_input("name (optional)", value="", key="prof_name")
    if st.button("Submit profile"):
        body = {
            "board": p_board,
            "class_no": int(p_class),
            "preferred_language": p_lang,
            "school_name": p_school or None,
            "name": p_name or None,
        }
        show(call_api(base_url, "PUT", "/me/profile", token=token, json_body=body))

with tab_prefs:
    pr_enabled = st.checkbox("memory_reset_enabled", value=True)
    pr_minutes = st.number_input("memory_reset_minutes", min_value=1, max_value=1440, value=30)
    st.caption("Note: requires an existing profile (submit the profile form first).")
    if st.button("Submit preferences"):
        body = {"memory_reset_enabled": pr_enabled, "memory_reset_minutes": int(pr_minutes)}
        show(call_api(base_url, "PUT", "/me/preferences", token=token, json_body=body))

st.divider()
st.subheader("Free-form request")
fc1, fc2 = st.columns([1, 3])
method = fc1.selectbox("Method", ["GET", "POST", "PUT", "PATCH", "DELETE"])
path = fc2.text_input("Path", value="/me/profile")
params_raw = st.text_area("Query params (one key=value per line)", value="", height=80)
body_raw = st.text_area("JSON body (for POST/PUT/PATCH)", value="", height=140)

if st.button("Send request", type="primary"):
    params = {}
    for line in params_raw.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            params[key.strip()] = value.strip()
    json_body = None
    if body_raw.strip():
        try:
            json_body = json.loads(body_raw)
        except json.JSONDecodeError as exc:
            st.error(f"Invalid JSON body: {exc}")
            st.stop()
    show(call_api(base_url, method, path, token=token, json_body=json_body, params=params or None))
