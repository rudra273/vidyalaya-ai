# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# vidyalaya-ai — Codebase Map

FastAPI RAG service that answers student questions from OCR'd school textbooks. Uses Gemini for embeddings, a pluggable provider (OpenRouter or Google) for chat completion, Qdrant for vector storage, Firebase for auth, and Postgres for users/profiles/usage. Mobile app sends a query → server retrieves relevant textbook chunks → LLM synthesizes an answer with citations.

## Commands

`src/` is not installed as a package — **every Python entrypoint needs `PYTHONPATH=src`**, and the venv lives at `.venv/`. Python 3.12.

```
# Local dev server (auto-reload)
docker compose up -d                                          # start local Qdrant first
PYTHONPATH=src .venv/bin/uvicorn vidyalaya_ai.main:app --reload

# DB migrations (prod runs these on deploy; dev also auto-creates tables on startup)
PYTHONPATH=src .venv/bin/alembic upgrade head
PYTHONPATH=src .venv/bin/alembic revision --autogenerate -m "msg"

# Tests — standalone scripts with their own __main__, NOT pytest-configured.
# Run a single test file directly:
.venv/bin/python tests/test_session_reset.py
.venv/bin/python tests/test_heal_history.py

# Offline pipelines (run from repo root)
PYTHONPATH=src .venv/bin/python ingestion/main.py            # chunk → embed → upsert to Qdrant
.venv/bin/python ocr/main.py                                 # PDFs → JSONL (uncomment __main__ block)

# Dev helper scripts (scripts/)
.venv/bin/streamlit run scripts/firebase_token_app.py        # mint Firebase ID tokens to hit local APIs
PYTHONPATH=src .venv/bin/python scripts/probe_qdrant.py      # inspect Qdrant collections
.venv/bin/python scripts/cleanup_checkpoints.py              # clear LearnAssist agent memory
```

## Stack & entrypoints

- App entry: [src/vidyalaya_ai/main.py](src/vidyalaya_ai/main.py)
- API factory: [src/vidyalaya_ai/api/app.py](src/vidyalaya_ai/api/app.py)
- Deploy: Railway via [railway.toml](railway.toml); local Qdrant via [docker-compose.yml](docker-compose.yml)
- Env vars: see [.env.example](.env.example)
- Python deps: [requirements.txt](requirements.txt)

## Component map

```
src/vidyalaya_ai/        FastAPI app — request handling, agents, RAG, LLM, auth
  ├── api/               FastAPI factory, routers (health/auth/learnassist), Pydantic schemas
  ├── auth/              Firebase Admin SDK token verification, AuthenticatedUser model
  ├── db/                Async SQLAlchemy (asyncpg) engine/session, declarative Base, ORM models; DATABASE_URL config
  ├── users/             User/profile SQLAlchemy repository functions + return DTOs
  ├── quota/             LearnAssist daily usage quota service
  ├── chatlog/           Permanent chat history (messages) + per-turn usage_events; non-blocking post-response writes; history pagination
  ├── agents/            LearnAssist agent (langchain create_agent + tools + Postgres checkpointer)
  ├── rag/               Query embedding, Qdrant retrieval, context building, eval
  ├── llm/               Chat-model provider factory (LLM_PROVIDER: openrouter [default] | google); embeddings always Gemini
  ├── tools/             Underlying retrieve_textbook function (wrapped as a tool in agents/)
  └── common/            Shared utilities (placeholder)

ingestion/               Offline ETL: OCR JSONL → chunk → embed → Qdrant upsert
  ├── main.py            Pipeline entrypoint
  ├── loader.py          Reads OCR output from data/processed/ocr
  ├── chunk.py           Semantic chunking (500 tokens, 50 overlap)
  ├── embed.py           Gemini embeddings + caching
  └── qdrant_store.py    Qdrant client, collection management, upsert

ocr/                     Offline OCR: PDFs → JSONL pages (Surya / Tesseract)

data/                    Textbook data
  ├── raw/               Source PDFs
  └── processed/         ocr/ (JSONL), embeddings/ (cached)

alembic/                 DB migrations scaffold (baseline only; not auto-run — dev uses create_all on startup)
qdrant_storage/          Local Qdrant persisted collections (dev only)
logs/                    Runtime logs (api, agents, rag, ingestion)
reports/                 RAG eval outputs (RAGAS metrics)
secrets/                 Firebase service account JSON (gitignored)
docs/                    Deployment guides
scripts/                 Dev-only tools: Firebase token minting, Qdrant probes, checkpoint cleanup
tests/                   Standalone test scripts (run directly via python, not pytest)
```

## Data flow

- **Offline:** PDFs → `ocr/` → JSONL → `ingestion/` → Qdrant.
- **Runtime:** mobile → FastAPI `/learnassist/chat` → Firebase auth/JIT user → quota check → LearnAssist agent (model decides whether to call `search_textbook`) → Gemini → JSON `{answer, citations, usage}`.
- **LearnAssist agent:** built with `langchain.agents.create_agent` (ReAct on LangGraph). Memory is per-student via Postgres checkpointer (`AsyncPostgresSaver` over an async psycopg pool; tables created by `saver.setup()` at startup; `thread_id = learnassist:{firebase_uid}`). Per-turn board/class/subject/language ride in the agent `context` (not checkpointed); `dynamic_prompt` injects the language rule. Package: `agents/learnassist/` (`agent`, `tools`, `prompt`, `context`, `runner`, `checkpointer`).

## Read these first for deeper context

- [architecture.drawio](architecture.drawio) — system architecture diagram. Read this to understand the architecture before architecture-level work, and update it **only** when making an architecture-level change (new component, service, or data-flow path). Do not touch it for routine code changes.
- [data/data.md](data/data.md) — data layer: textbook data directory, OCR → chunk → embed → Qdrant hand-off
- [src/vidyalaya_ai/llm/llm_plan.md](src/vidyalaya_ai/llm/llm_plan.md) — LLM strategy

## Maintenance

Update this map when adding/removing a top-level folder, or a subfolder under `src/vidyalaya_ai/` or `ingestion/`. Do NOT list individual files or functions here — those belong in code.
