"""Configuration for chat model providers."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv


def _env(name: str, default: str) -> str:
    load_dotenv()
    value = os.getenv(name, "").strip()
    return value or default


def _env_float(name: str, default: float) -> float:
    raw = _env(name, str(default))
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = _env(name, str(default))
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class LLMConfig:
    """Settings used to create a LangChain-compatible chat model.

    Defaults come from the environment so the provider/model can be switched via
    .env without code changes:

      LLM_PROVIDER   google | openrouter   (default: openrouter)
      LLM_MODEL      provider-specific id  (e.g. google/gemini-2.0-flash-001)
      LLM_TEMPERATURE, LLM_MAX_TOKENS, LLM_REQUEST_TIMEOUT
    """

    provider: str = field(default_factory=lambda: _env("LLM_PROVIDER", "openrouter"))
    model: str = field(default_factory=lambda: _env("LLM_MODEL", "google/gemini-2.0-flash-001"))
    temperature: float = field(default_factory=lambda: _env_float("LLM_TEMPERATURE", 0.2))
    max_tokens: int = field(default_factory=lambda: _env_int("LLM_MAX_TOKENS", 1200))
    request_timeout: float = field(default_factory=lambda: _env_float("LLM_REQUEST_TIMEOUT", 60.0))


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
        "openrouter": "OPENROUTER_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }
    if provider not in key_names:
        raise ValueError(f"Unsupported LLM provider: {provider}")

    return key_names[provider]
