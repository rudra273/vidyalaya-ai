"""LearnAssist chat tester — multi-turn conversation, memory reset, tool trace.

This page is built to exercise the ``get_chat_history`` tool end to end:

  1. Have a few turns on a subject (memory lives in the server-side checkpoint,
     keyed by channel/board/class/subject — not in this UI).
  2. Click **Reset memory** to wipe the checkpoint (the permanent ``messages``
     table is untouched), simulating a student returning after the session
     timeout.
  3. Send "continue what we were discussing" — a correct answer that recalls the
     earlier topic proves the agent called ``get_chat_history`` to re-read the
     persisted conversation.

The **Agent log** expander tails ``logs/agents.log`` filtered to tool calls, so
you can confirm ``get_chat_history`` actually fired (not just inferred it).
"""

from __future__ import annotations

import base64

import streamlit as st

from _client import AGENTS_LOG, call_api, tail_log

st.set_page_config(page_title="Chat · Vidyalaya Tester", page_icon="💬", layout="wide")
st.title("💬 LearnAssist Chat")

token = st.session_state.get("id_token")
base_url = st.session_state.get("base_url", "http://localhost:8000")
if not token:
    st.warning("No token. Go to **Home** and generate a Firebase ID token first.")
    st.stop()

SUBJECTS = ["", "science", "maths", "english", "hindi", "odia", "sanskrit", "social_science"]


def _subject_label(value: str) -> str:
    """Render the empty subject as the explicit all-subjects / general mode."""
    return "(all subjects / general)" if value == "" else value


with st.sidebar:
    st.header("Thread selectors")
    st.caption("Memory is scoped per (channel, board, class, subject). Change any and it's a fresh thread.")
    board = st.text_input("Board", value="scert_odisha")
    class_no = st.number_input("Class", min_value=1, max_value=12, value=8)
    channel = st.text_input("Channel", value="learn_assist")
    subject = st.selectbox("Subject", SUBJECTS, index=1, format_func=_subject_label)
    language = st.text_input("Language", value="en")
    debug = st.checkbox("Debug retrieval (return context_blocks)", value=False)

# --- Test actions: wipe the server-side checkpoint (simulates the 30-min reset) ---
# This calls the same endpoint the inactivity timeout uses, so afterwards a
# "continue" message should make the agent call get_chat_history.
act1, act2 = st.columns(2)
if act1.button("🧹 Clear server memory (reset checkpoint)", use_container_width=True):
    result = call_api(
        base_url,
        "POST",
        "/learnassist/memory/reset",
        token=token,
        json_body={
            "board": board,
            "class_no": int(class_no),
            "channel": channel,
            "subject": subject or None,
        },
    )
    if result["ok"]:
        st.success("Checkpoint cleared — permanent history is untouched. "
                   "Send 'continue what we were discussing' to trigger get_chat_history.")
    else:
        st.error(result)
if act2.button("🗑️ Clear local transcript (display only)", use_container_width=True):
    st.session_state["chat_transcript"] = []
    st.rerun()

transcript = st.session_state.setdefault("chat_transcript", [])

for turn in transcript:
    with st.chat_message(turn["role"]):
        st.markdown(turn["content"])

uploaded_image = st.file_uploader(
    "Attach image (optional)", type=["jpg", "jpeg", "png", "webp"]
)
message = st.chat_input("Message LearnAssist…")

if message or (uploaded_image is not None and st.button("Send image only")):
    payload: dict = {
        "message": message or None,
        "board": board,
        "class_no": int(class_no),
        "channel": channel,
        "subject": subject or None,
        "language": language or None,
        "debug": debug,
    }
    if uploaded_image is not None:
        media_type = uploaded_image.type or "image/jpeg"
        if media_type == "image/jpg":
            media_type = "image/jpeg"
        payload["image_base64"] = base64.b64encode(uploaded_image.getvalue()).decode("ascii")
        payload["image_media_type"] = media_type

    display_msg = message or "[image]"
    transcript.append({"role": "user", "content": display_msg})
    with st.chat_message("user"):
        st.markdown(display_msg)

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            result = call_api(base_url, "POST", "/learnassist/chat", token=token, json_body=payload)
        if result["ok"]:
            data = result["data"]
            answer = data.get("answer", "(no answer)")
            st.markdown(answer)
            transcript.append({"role": "assistant", "content": answer})
            tools_used = data.get("tools_used") or []
            meta_cols = st.columns(3)
            meta_cols[0].metric("tools used", ", ".join(tools_used) if tools_used else "none")
            usage = data.get("usage") or {}
            meta_cols[1].metric("used / limit", f"{usage.get('used')}/{usage.get('limit')}")
            meta_cols[2].metric("citations", len(data.get("citations") or []))
            with st.expander("Full response JSON"):
                st.json(data)
        else:
            st.error(result)
            transcript.append({"role": "assistant", "content": f"⚠️ {result['status']}: {result['data']}"})

st.divider()
with st.expander("🔎 Agent log — tool calls (logs/agents.log)"):
    st.caption("Lines mentioning a tool call. Look for `get_chat_history thread=… limit=…` "
               "after a reset+continue, and `search_textbook` on normal questions.")
    only_tools = st.checkbox("Filter to tool-call lines only", value=True)
    log_text = tail_log(AGENTS_LOG, lines=80)
    if only_tools:
        lines = [
            ln for ln in log_text.splitlines()
            if "get_chat_history" in ln or "search_textbook" in ln or "Healing thread" in ln
        ]
        log_text = "\n".join(lines[-40:]) or "(no tool-call lines in the recent log tail)"
    st.code(log_text, language="text")
    if st.button("Refresh log"):
        st.rerun()
