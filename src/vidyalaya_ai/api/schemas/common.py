"""Common API schemas."""

from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    service: str = "vidyalaya-ai"


class ErrorDetail(BaseModel):
    """API error body."""

    code: str
    message: str


class ErrorResponse(BaseModel):
    """API error response."""

    error: ErrorDetail
