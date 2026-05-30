"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from vidyalaya_ai.api.exceptions import (
    http_exception_handler,
    request_validation_error_handler,
    quota_exceeded_handler,
    service_error_handler,
    validation_error_handler,
    value_error_handler,
)
from vidyalaya_ai.agents import close_checkpointer, initialize_checkpointer
from vidyalaya_ai.api.logging_config import setup_api_logging
from vidyalaya_ai.api.routers import auth, health, learnassist, me
from vidyalaya_ai.auth.firebase import initialize_firebase_app
from vidyalaya_ai.db import close_engine, ensure_schema
from vidyalaya_ai.quota.exceptions import QuotaExceeded


@asynccontextmanager
async def lifespan(api: FastAPI):
    """Application startup/shutdown lifecycle."""
    await ensure_schema()
    await initialize_checkpointer()
    yield
    await close_checkpointer()
    await close_engine()


def create_app() -> FastAPI:
    """Create the FastAPI application."""
    setup_api_logging()
    initialize_firebase_app()

    api = FastAPI(title="Vidyalaya AI", version="0.1.0", lifespan=lifespan)
    api.add_exception_handler(HTTPException, http_exception_handler)
    api.add_exception_handler(ValueError, value_error_handler)
    api.add_exception_handler(ValidationError, validation_error_handler)
    api.add_exception_handler(RequestValidationError, request_validation_error_handler)
    api.add_exception_handler(QuotaExceeded, quota_exceeded_handler)
    api.add_exception_handler(Exception, service_error_handler)
    api.include_router(health.router)
    api.include_router(auth.router)
    api.include_router(me.router)
    api.include_router(learnassist.router)

    return api


app = create_app()
