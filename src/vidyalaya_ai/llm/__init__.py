"""LLM provider setup for Vidyalaya AI."""

from vidyalaya_ai.llm.config import LLMConfig
from vidyalaya_ai.llm.factory import create_chat_model


__all__ = ["LLMConfig", "create_chat_model"]
