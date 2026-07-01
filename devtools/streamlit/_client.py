"""Shared helpers for the Vidyalaya dev Streamlit app (token minting + API calls).

Underscore-prefixed so Streamlit's multipage loader does NOT treat it as a page.
Every page imports from here; the module also puts ``src/`` on ``sys.path`` and
resolves repo-relative paths (``.env``, ``logs/``) from its own location so the
app works no matter what directory ``streamlit run`` is launched from.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# devtools/streamlit/_client.py -> repo root is two parents up.
REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

AGENTS_LOG = REPO_ROOT / "logs" / "agents.log"
API_LOG = REPO_ROOT / "logs" / "api.log"

FIREBASE_EXCHANGE_URL = (
    "https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={api_key}"
)


def load_settings() -> tuple[str | None, str]:
    """Return (FIREBASE_WEB_API_KEY, API base URL) from the repo ``.env``."""
    import os

    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
    return os.getenv("FIREBASE_WEB_API_KEY"), os.getenv(
        "VIDYALAYA_API_BASE_URL",
        "http://localhost:8000",
    )


def ensure_test_user(uid: str, email: str | None, display_name: str | None) -> None:
    """Create or update the Firebase test user backing the minted token."""
    from firebase_admin import auth

    from vidyalaya_ai.auth.firebase import initialize_firebase_app

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


def mint_id_token(uid: str, api_key: str) -> dict[str, Any]:
    """Exchange a custom token for a Firebase ID token via the Auth REST API."""
    from firebase_admin import auth

    from vidyalaya_ai.auth.firebase import initialize_firebase_app

    app = initialize_firebase_app()
    custom_token = auth.create_custom_token(uid, app=app).decode("utf-8")
    payload = {"token": custom_token, "returnSecureToken": True}
    result = _raw_request(
        FIREBASE_EXCHANGE_URL.format(api_key=api_key),
        payload=payload,
        method="POST",
    )
    if not result["ok"]:
        raise RuntimeError(f"{result['status']}: {result['data']}")
    return result["data"]


def call_api(
    base_url: str,
    method: str,
    path: str,
    *,
    token: str | None = None,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call the Vidyalaya API and return a structured result (never raises on HTTP).

    Returns ``{ok, status, data}`` so pages can render the status code and body
    uniformly for both success and error responses — the whole point of a tester.
    """
    url = f"{base_url.rstrip('/')}{path}"
    if params:
        query = "&".join(
            f"{key}={value}" for key, value in params.items() if value not in (None, "")
        )
        if query:
            url = f"{url}?{query}"
    return _raw_request(url, payload=json_body, bearer_token=token, method=method)


def stream_sse(
    base_url: str,
    path: str,
    *,
    token: str | None = None,
    json_body: dict[str, Any] | None = None,
) -> Iterator[dict[str, Any]]:
    """POST to an SSE endpoint and yield parsed frames as they arrive.

    Each yielded item is ``{"event": <name>, "data": <parsed>}`` where ``data``
    is JSON-decoded when possible. A pre-stream HTTP failure (e.g. 401/429 from
    the pre-flight, returned as a normal JSON body) is surfaced as a single
    ``{"event": "_http_error", "data": {"status", "body"}}`` frame so the caller
    can render it like any other error. Comment/ping lines (starting with ``:``)
    are ignored. Dependency-free to match :func:`call_api`.
    """
    url = f"{base_url.rstrip('/')}{path}"
    body = None if json_body is None else json.dumps(json_body).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, data=body, headers=headers, method="POST")

    try:
        response = urlopen(request, timeout=120)
    except HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        yield {"event": "_http_error", "data": {"status": exc.code, "body": _parse(text)}}
        return
    except URLError as exc:
        yield {
            "event": "_http_error",
            "data": {"status": None, "body": f"Request failed: {exc.reason}"},
        }
        return

    event_name = "message"
    data_lines: list[str] = []
    with response:
        for raw in response:  # HTTPResponse yields lines as they stream in
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            if line == "":  # blank line dispatches the buffered event
                if data_lines:
                    yield {"event": event_name, "data": _parse("\n".join(data_lines))}
                event_name = "message"
                data_lines = []
            elif line.startswith(":"):
                continue  # SSE comment / keep-alive ping
            elif line.startswith("event:"):
                event_name = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:") :].lstrip())
    if data_lines:  # flush a trailing event with no terminating blank line
        yield {"event": event_name, "data": _parse("\n".join(data_lines))}


def _raw_request(
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    bearer_token: str | None = None,
    method: str | None = None,
) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"

    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=120) as response:
            text = response.read().decode("utf-8")
            return {"ok": True, "status": response.status, "data": _parse(text)}
    except HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        return {"ok": False, "status": exc.code, "data": _parse(text)}
    except URLError as exc:
        return {"ok": False, "status": None, "data": f"Request failed: {exc.reason}"}


def _parse(text: str) -> Any:
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def tail_log(path: Path, *, lines: int = 60, contains: str | None = None) -> str:
    """Return the last ``lines`` of a log file, optionally filtered to ``contains``."""
    if not path.exists():
        return f"(no log file at {path})"
    text = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if contains:
        text = [line for line in text if contains in line]
    tail = text[-lines:]
    return "\n".join(tail) if tail else "(no matching log lines yet)"
