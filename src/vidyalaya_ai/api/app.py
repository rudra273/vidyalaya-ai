"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from vidyalaya_ai.api.exceptions import (
    http_exception_handler,
    request_validation_error_handler,
    service_error_handler,
    validation_error_handler,
    value_error_handler,
)
from vidyalaya_ai.api.logging_config import setup_api_logging
from vidyalaya_ai.api.routers import auth, health, learnassist


def create_app() -> FastAPI:
    """Create the FastAPI application."""
    setup_api_logging()

    api = FastAPI(title="Vidyalaya AI", version="0.1.0")
    api.add_exception_handler(HTTPException, http_exception_handler)
    api.add_exception_handler(ValueError, value_error_handler)
    api.add_exception_handler(ValidationError, validation_error_handler)
    api.add_exception_handler(RequestValidationError, request_validation_error_handler)
    api.add_exception_handler(Exception, service_error_handler)
    api.include_router(health.router)
    api.include_router(auth.router)
    api.include_router(learnassist.router)

    return api


app = create_app()
