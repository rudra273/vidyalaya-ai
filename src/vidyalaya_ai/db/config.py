"""Postgres configuration.

The app is DB-agnostic: it talks to any Postgres via ``DATABASE_URL``. Providers
hand out URLs in a few shapes (``postgres://``, ``postgresql://``, sometimes with
a ``+driver``). We normalize that single URL into the two drivers we actually use:

- ``asyncpg`` for the SQLAlchemy async engine (app tables).
- ``psycopg`` (psycopg3) for the LangGraph ``AsyncPostgresSaver`` checkpointer.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import quote

from dotenv import load_dotenv


# Characters that are safe to leave unencoded inside the userinfo (user:password)
# part of a URL. Everything else in the password (@, :, /, spaces, etc.) must be
# percent-encoded or the URL parser mis-reads where the host begins.
_USERINFO_SAFE = "-._~"

# scheme://user:password@host... — capture the password between the first ':'
# after the user and the LAST '@' (the real credentials/host separator). Using
# the last '@' is what lets an un-encoded '@' inside the password work.
_USERINFO_RE = re.compile(r"^(?P<head>[^:/?#]+://[^:@/]+:)(?P<pw>.*)@(?P<tail>[^@/]+.*)$")


def _encode_password(url: str) -> str:
    """Percent-encode the password in a DATABASE_URL so special chars are safe.

    Lets a raw password like ``Tiger@123`` or ``p:a/ss`` work without the user
    hand-encoding it. If the URL has no ``user:password@`` userinfo, it is
    returned unchanged. Already-encoded passwords are left alone (``%`` is safe).
    """
    match = _USERINFO_RE.match(url)
    if match is None:
        return url
    password = match.group("pw")
    # If it already looks percent-encoded, don't double-encode.
    if "%" in password:
        return url
    encoded = quote(password, safe=_USERINFO_SAFE)
    return f"{match.group('head')}{encoded}@{match.group('tail')}"


@dataclass(frozen=True)
class PostgresConfig:
    """Runtime Postgres connection settings, in the forms each client wants."""

    # Raw value from the environment, as the provider gave it.
    raw_url: str
    # SQLAlchemy async engine URL (postgresql+asyncpg://...).
    sqlalchemy_url: str
    # Plain libpq/psycopg URL (postgresql://...) for the checkpointer.
    psycopg_url: str


def _strip_driver(url: str) -> str:
    """Return the URL with any SQLAlchemy ``+driver`` suffix removed.

    ``postgresql+asyncpg://`` / ``postgres+psycopg://`` -> ``postgresql://``.
    """
    scheme, sep, rest = url.partition("://")
    if not sep:
        return url
    base = scheme.split("+", 1)[0]
    # Normalize the legacy ``postgres`` scheme some providers still emit.
    if base == "postgres":
        base = "postgresql"
    return f"{base}://{rest}"


def _to_asyncpg(url: str) -> str:
    """Return a ``postgresql+asyncpg://`` URL for the SQLAlchemy async engine."""
    plain = _strip_driver(url)
    _, _, rest = plain.partition("://")
    return f"postgresql+asyncpg://{rest}"


@lru_cache(maxsize=1)
def load_postgres_config() -> PostgresConfig:
    """Load and normalize Postgres config from the environment."""
    load_dotenv()
    raw = os.getenv("DATABASE_URL", "").strip()
    if not raw:
        raise RuntimeError("DATABASE_URL is required for Postgres-backed routes.")

    # Guard against a value accidentally split across whitespace (a common
    # copy-paste mishap); keep only the first whitespace-delimited token.
    raw = raw.split()[0]
    normalized = _encode_password(raw)

    return PostgresConfig(
        raw_url=normalized,
        sqlalchemy_url=_to_asyncpg(normalized),
        psycopg_url=_strip_driver(normalized),
    )


def has_postgres_config() -> bool:
    """Return whether Postgres has enough config to connect."""
    load_dotenv()
    return bool(os.getenv("DATABASE_URL", "").strip())
