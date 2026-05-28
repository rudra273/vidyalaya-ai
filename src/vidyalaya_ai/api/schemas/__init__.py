"""API schemas."""

from vidyalaya_ai.api.schemas.auth import AuthenticatedUserResponse
from vidyalaya_ai.api.schemas.common import ErrorDetail, ErrorResponse, HealthResponse
from vidyalaya_ai.api.schemas.learnassist import LearnAssistChatRequest, LearnAssistChatResponse


__all__ = [
    "AuthenticatedUserResponse",
    "ErrorDetail",
    "ErrorResponse",
    "HealthResponse",
    "LearnAssistChatRequest",
    "LearnAssistChatResponse",
]
