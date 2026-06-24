# devtools

Interactive, developer-only tools for working against a **local** Vidyalaya AI
server. Distinct from `scripts/`, which holds one-shot CLI utilities (Qdrant
probes, checkpoint cleanup).

## Streamlit API tester

A multipage Streamlit app that exercises the API end to end: mint a Firebase ID
token, drive LearnAssist chat, inspect persisted history, and call any endpoint.

```
.venv/bin/streamlit run devtools/streamlit/Home.py
```

Run it from the repo root. It reads `FIREBASE_WEB_API_KEY` and
`VIDYALAYA_API_BASE_URL` from `.env` (both can be overridden in the sidebar) and
uses the Firebase service account configured for the app.

### Pages

- **Home** — settings + mint a Firebase ID token (shared across pages via
  `st.session_state`). Start here.
- **Chat** — multi-turn LearnAssist tester with image upload, a **Reset memory**
  button, and an agent-log trace. Use it to verify the `get_chat_history` tool:
  chat → reset memory → send "continue what we were discussing" → confirm the
  answer recalls the earlier topic and `get_chat_history` appears in the log.
- **History** — `GET /me/history` viewer; the permanent `messages` the chat tool
  reads back after a reset.
- **API Console** — quick-call buttons, profile/preferences forms, and a
  free-form request builder for any method/path/body.

`_client.py` is shared infrastructure (token minting, API calls, log tailing);
the leading underscore keeps Streamlit from loading it as a page.
