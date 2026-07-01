"""Google Gemini chat model provider through LangChain."""

from __future__ import annotations

import os

from langchain_google_genai import ChatGoogleGenerativeAI

from vidyalaya_ai.llm.config import LLMConfig, load_provider_api_key


def create_google_chat_model(config: LLMConfig) -> ChatGoogleGenerativeAI:
    """Create a Gemini chat model without using the direct Gemini SDK in agents."""
    api_key = load_provider_api_key("google")
    os.environ.setdefault("GOOGLE_API_KEY", api_key)

    return ChatGoogleGenerativeAI(
        api_key=api_key,
        model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        request_timeout=config.request_timeout,
        # Enable token streaming for astream (the /chat/stream endpoint). Harmless
        # for the non-streaming ainvoke path, which still returns the full message.
        # Gemini reports usage_metadata on the final streamed chunk, so per-turn
        # token accounting keeps working.
        streaming=True,
    )
