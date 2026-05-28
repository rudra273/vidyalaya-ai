"""Health routes."""

from __future__ import annotations

from fastapi import APIRouter

from vidyalaya_ai.api.schemas.common import HealthResponse


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return API health."""
    return HealthResponse()
