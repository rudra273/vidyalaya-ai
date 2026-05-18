"""FastAPI app for Release 1 LearnAssist."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from vidyalaya_ai.agents import LearnAssistInput, answer_with_learnassist
from vidyalaya_ai.api.logging_config import setup_api_logging
from vidyalaya_ai.api.schemas import HealthResponse, LearnAssistChatRequest, LearnAssistChatResponse


logger = logging.getLogger("vidyalaya_ai.api")


def create_app() -> FastAPI:
    """Create the FastAPI application."""
    setup_api_logging()

    api = FastAPI(title="Vidyalaya AI", version="0.1.0")

    @api.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        """Return a simple validation error response."""
        logger.info("Bad request path=%s error=%s", request.url.path, exc)
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "bad_request", "message": str(exc)}},
        )

    @api.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
        """Return a simple validation error response."""
        logger.info("Validation error path=%s error=%s", request.url.path, exc)
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "bad_request", "message": str(exc)}},
        )

    @api.exception_handler(Exception)
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

    @api.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        """Return API health."""
        return HealthResponse()

    @api.post("/learnassist/chat", response_model=LearnAssistChatResponse)
    def learnassist_chat(payload: LearnAssistChatRequest) -> dict:
        """Answer a student query with LearnAssist."""
        logger.info(
            "LearnAssist request board=%s class=%s subject=%s debug=%s",
            payload.board,
            payload.class_no,
            payload.subject,
            payload.debug,
        )
        result = answer_with_learnassist(
            LearnAssistInput(
                query=payload.query,
                board=payload.board,
                class_no=payload.class_no,
                subject=payload.subject,
                language=payload.language,
            )
        )

        if not payload.debug:
            result.pop("context_blocks", None)

        return result

    return api


app = create_app()
