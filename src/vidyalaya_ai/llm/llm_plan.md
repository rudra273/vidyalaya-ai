# LLM Layer Plan

## Purpose

The `llm/` folder contains only core model/provider setup.

It should not contain agent personality, tutor behavior, routing logic, textbook-answer prompts, or system prompts. Those belong in the agent layer.

## Boundary

```text
rag/
  retrieval and context building

tools/
  callable tools such as retrieve_textbook

llm/
  provider config
  provider implementations
  chat model factory

agents/
  agent prompts
  agent behavior
  conversation flow
```

## Important Rules

- Gemini SDK is used only for embeddings.
- Final answer generation uses LangChain-compatible chat model objects.
- Agents import the model factory and own their own prompts.
- The LLM folder should not decide whether to retrieve, tutor, quiz, or answer.

## Current Structure

```text
src/vidyalaya_ai/llm/
  __init__.py
  config.py
  factory.py
  providers/
    __init__.py
    google.py
  llm_plan.md
```

## Current Provider

Google Gemini is configured through `langchain-google-genai`.

Default config:

```json
{
  "provider": "google",
  "model": "gemini-2.5-flash",
  "temperature": 0.2,
  "max_tokens": 1200,
  "request_timeout": 60.0
}
```

The Google provider reads `GOOGLE_API_KEY`.

For compatibility with the current project setup, it also accepts `GEMINI_API_KEY` as a fallback.

## Factory Contract

Agents should use:

```python
from vidyalaya_ai.llm import LLMConfig, create_chat_model

llm = create_chat_model(
    LLMConfig(
        provider="google",
        model="gemini-2.5-flash",
        temperature=0.2,
        max_tokens=1200,
    )
)
```

The returned object is a LangChain-compatible chat model.

## Provider Expansion Later

Future providers can be added without changing agent code:

```text
src/vidyalaya_ai/llm/providers/
  google.py
  openai.py
  anthropic.py
  local.py
```

Then `factory.py` should route by `LLMConfig.provider`.

## What Should Not Be Here

- Tutor Agent system prompt
- LearnAssist Agent prompt
- textbook answer prompt
- routing rules
- student progress logic
- subject-specific teaching behavior
- worksheet generation rules

Those will live in `agents/` and call tools or chat models as needed.
