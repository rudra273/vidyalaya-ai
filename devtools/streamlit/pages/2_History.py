"""Chat history viewer — GET /me/history.

Shows the permanent ``messages`` rows for a thread (oldest -> newest). This is
exactly the conversation ``get_chat_history`` reads from, so it's the ground
truth for what the agent can recover after a memory reset. Supports backward
pagination via the ``before`` cursor.
"""

from __future__ import annotations

import streamlit as st

from _client import call_api

st.set_page_config(page_title="History · Vidyalaya Tester", page_icon="📜", layout="wide")
st.title("📜 Chat History — GET /me/history")

token = st.session_state.get("id_token")
base_url = st.session_state.get("base_url", "http://localhost:8000")
if not token:
    st.warning("No token. Go to **Home** and generate a Firebase ID token first.")
    st.stop()

SUBJECTS = ["", "science", "maths", "english", "hindi", "odia", "sanskrit", "social_science"]


def _subject_label(value: str) -> str:
    return "(all subjects / general)" if value == "" else value


col1, col2, col3, col4 = st.columns(4)
board = col1.text_input("Board", value="scert_odisha")
class_no = col2.number_input("Class", min_value=1, max_value=12, value=8)
subject = col3.selectbox("Subject", SUBJECTS, index=1, format_func=_subject_label)
limit = col4.number_input("Limit", min_value=1, max_value=100, value=30)

channel = st.text_input("Channel", value="learn_assist")
before = st.text_input("before (message id cursor; blank = newest page)", value="")

if st.button("Load history", type="primary"):
    params = {
        "board": board,
        "class_no": int(class_no),
        "channel": channel,
        "subject": subject or None,
        "limit": int(limit),
    }
    if before.strip():
        params["before"] = before.strip()
    result = call_api(base_url, "GET", "/me/history", token=token, params=params)
    st.session_state["history_result"] = result

result = st.session_state.get("history_result")
if result:
    if not result["ok"]:
        st.error(result)
    else:
        data = result["data"]
        messages = data.get("messages", [])
        st.caption(f"{len(messages)} message(s). next_before cursor: {data.get('next_before')}")
        for msg in messages:
            role = "user" if msg.get("role") == "human" else "assistant"
            with st.chat_message(role):
                st.markdown(f"**[id {msg.get('id')}]** {msg.get('content')}")
                if msg.get("citations"):
                    st.caption(f"citations: {len(msg['citations'])}")
        with st.expander("Raw JSON"):
            st.json(data)
