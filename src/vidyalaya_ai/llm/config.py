"""Configuration for chat model providers."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class LLMConfig:
    """Settings used to create a LangChain-compatible chat model."""

    provider: str = "google"
    model: str = "gemini-2.5-flash"
    temperature: float = 0.2
    max_tokens: int = 1200
    request_timeout: float = 60.0


def load_provider_api_key(provider: str, env_path: str = ".env") -> str:
    """Load the API key for a provider from environment variables."""
    load_dotenv(env_path)
    normalized_provider = provider.strip().lower()
    key_name = _provider_key_name(normalized_provider)

    api_key = os.getenv(key_name)
    if normalized_provider == "google" and not api_key:
        api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(f"Missing API key. Set {key_name} in .env.")

    return api_key


def _provider_key_name(provider: str) -> str:
    """Return the expected environment variable name for a provider."""
    key_names = {
        "google": "GOOGLE_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }
    if provider not in key_names:
        raise ValueError(f"Unsupported LLM provider: {provider}")

    return key_names[provider]
