"""SQLAlchemy declarative base shared by all ORM models.

Kept separate from the engine so Alembic and ``create_all`` can import the
metadata without pulling in engine/connection side effects.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all Vidyalaya AI tables."""
