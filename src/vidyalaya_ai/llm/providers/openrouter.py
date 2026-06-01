"""OpenRouter chat model provider through LangChain.

OpenRouter exposes an OpenAI-compatible API, so we use ``ChatOpenAI`` pointed at
the OpenRouter base URL. The model id (e.g. ``google/gemini-2.5-flash``,
``openai/gpt-4.1-mini``) is set via ``LLM_MODEL`` in .env.
"""

from __future__ import annotations

from langchain_openai import ChatOpenAI

from vidyalaya_ai.llm.config import LLMConfig, load_provider_api_key


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def create_openrouter_chat_model(config: LLMConfig) -> ChatOpenAI:
    """Create a chat model that routes through OpenRouter."""
    api_key = load_provider_api_key("openrouter")

    return ChatOpenAI(
        model=config.model,
        api_key=api_key,
        base_url=OPENROUTER_BASE_URL,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        timeout=config.request_timeout,
    )
