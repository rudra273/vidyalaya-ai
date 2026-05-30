"""API exception handlers."""

from __future__ import annotations

import logging

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from vidyalaya_ai.agents.exceptions import AgentTimeout, AgentUnavailable
from vidyalaya_ai.quota.exceptions import QuotaExceeded


logger = logging.getLogger("vidyalaya_ai.api")


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Return API-shaped HTTP errors."""
    code = "unauthorized" if exc.status_code == 401 else "http_error"
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": code, "message": str(exc.detail)}},
    )


async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Return a simple validation error response."""
    logger.info("Bad request path=%s error=%s", request.url.path, exc)
    return JSONResponse(
        status_code=400,
        content={"error": {"code": "bad_request", "message": str(exc)}},
    )


async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """Return a simple validation error response."""
    logger.info("Validation error path=%s error=%s", request.url.path, exc)
    return JSONResponse(
        status_code=400,
        content={"error": {"code": "bad_request", "message": str(exc)}},
    )


async def request_validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Return a simple request body validation error response."""
    logger.info("Request validation error path=%s error=%s", request.url.path, exc)
    return JSONResponse(
        status_code=400,
        content={"error": {"code": "bad_request", "message": str(exc)}},
    )


async def quota_exceeded_handler(request: Request, exc: QuotaExceeded) -> JSONResponse:
    """Return a quota exceeded response."""
    logger.info(
        "Quota exceeded path=%s used=%s limit=%s",
        request.url.path,
        exc.used,
        exc.limit,
    )
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "quota_exceeded",
                "message": "Daily LearnAssist quota exceeded.",
                "retry_at_ist": exc.retry_at_ist,
            }
        },
    )


async def agent_unavailable_handler(request: Request, exc: AgentUnavailable) -> JSONResponse:
    """Return a friendly 503 when the model/provider is unavailable.

    The underlying error was already logged with full detail in the runner; here
    we only emit a safe, retryable message for the client.
    """
    logger.info("Agent unavailable path=%s", request.url.path)
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "code": "assistant_unavailable",
                "message": "Assistant is busy, please try again.",
            }
        },
    )


async def agent_timeout_handler(request: Request, exc: AgentTimeout) -> JSONResponse:
    """Return a friendly 504 when a turn exceeds its time budget."""
    logger.info("Agent timeout path=%s", request.url.path)
    return JSONResponse(
        status_code=504,
        content={
            "error": {
                "code": "assistant_timeout",
                "message": "That took too long, please try again.",
            }
        },
    )


async def service_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return a safe service error response."""
    logger.exception("Service error path=%s", request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "service_error",
                "message": "Unable to process the request right now.",
            }
        },
    )
