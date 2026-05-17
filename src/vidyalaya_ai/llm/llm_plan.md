# LLM Layer Plan

## Purpose

The LLM folder should contain core model/provider setup only.

It should not contain agent personality, tutor behavior, routing logic, or long system prompts. Those belong in the agent layer.

## Current Boundary

```text
rag/
  retrieval and context

llm/
  model/provider setup
  common LLM invocation helpers
  generic answer helper

agents/
  agent prompts
  agent behavior
  conversation flow
```

## Important Rule

Gemini SDK is used only for embeddings.

Final answer models should be called through LangChain-compatible interfaces so the model can be changed later.

## MVP LLM Responsibilities

- load LLM provider config
- create LangChain chat model
- expose simple factory function
- keep temperature/max tokens/model name configurable
- support different providers later

## Suggested Files Later

```text
src/vidyalaya_ai/llm/
  config.py
  factory.py
  answer.py
```

## Config Shape

```json
{
  "provider": "google",
  "model": "gemini-2.5-flash",
  "temperature": 0.2,
  "max_tokens": 1200
}
```

Provider examples:

```text
google
openai
anthropic
local
```

## Factory Example

The future factory should expose:

```python
def create_chat_model(config: LLMConfig):
    ...
```

Agents should receive the model from this factory.

## What Should Not Be Here

- Tutor Agent system prompt
- Doubt Solver Agent prompt
- routing rules
- student progress logic
- subject-specific teaching behavior
- worksheet generation rules

## Current Status

`answer.py` currently contains a generic LangChain-compatible helper:

```python
generate_answer(query=..., context_blocks=..., llm=...)
```

This is acceptable for now because it is generic and model-agnostic. Later, agent-specific prompts can move into agent files while this folder keeps only common model invocation code.

