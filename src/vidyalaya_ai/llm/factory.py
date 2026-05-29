"""Factory for LangChain-compatible chat models."""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from vidyalaya_ai.llm.config import LLMConfig
from vidyalaya_ai.llm.providers.google import create_google_chat_model
from vidyalaya_ai.llm.providers.openrouter import create_openrouter_chat_model


def create_chat_model(config: LLMConfig | None = None) -> BaseChatModel:
    """Create a chat model for the configured provider."""
    config = config or LLMConfig()
    provider = config.provider.strip().lower()

    if provider == "google":
        return create_google_chat_model(config)
    if provider == "openrouter":
        return create_openrouter_chat_model(config)

    raise ValueError(f"Unsupported LLM provider: {config.provider}")
