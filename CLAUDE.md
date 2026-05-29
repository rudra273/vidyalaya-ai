# vidyalaya-ai — Codebase Map

FastAPI RAG service that answers student questions from OCR'd school textbooks. Uses Gemini for embeddings + chat completion, Qdrant for vector storage, Firebase for auth, and MongoDB for users/profiles/usage. Mobile app sends a query → server retrieves relevant textbook chunks → LLM synthesizes an answer with citations.

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
  ├── db/                Motor MongoDB client lifecycle and indexes
  ├── users/             User/profile MongoDB models and repository functions
  ├── quota/             LearnAssist daily usage quota service
  ├── agents/            LearnAssist agent (langchain create_agent + tools + MongoDB checkpointer)
  ├── rag/               Query embedding, Qdrant retrieval, context building, eval
  ├── llm/               LLM provider abstraction (currently Gemini via langchain-google-genai)
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

qdrant_storage/          Local Qdrant persisted collections (dev only)
logs/                    Runtime logs (api, agents, rag, ingestion)
reports/                 RAG eval outputs (RAGAS metrics)
secrets/                 Firebase service account JSON (gitignored)
docs/                    Deployment guides
tests/                   Empty
```

## Data flow

- **Offline:** PDFs → `ocr/` → JSONL → `ingestion/` → Qdrant.
- **Runtime:** mobile → FastAPI `/learnassist/chat` → Firebase auth/JIT user → quota check → LearnAssist agent (model decides whether to call `search_textbook`) → Gemini → JSON `{answer, citations, usage}`.
- **LearnAssist agent:** built with `langchain.agents.create_agent` (ReAct on LangGraph). Memory is per-student via MongoDB checkpointer (`checkpoints`/`checkpoint_writes`, `thread_id = learnassist:{firebase_uid}`) with `SummarizationMiddleware`. Per-turn board/class/subject/language ride in the agent `context` (not checkpointed); `dynamic_prompt` injects the language rule. Package: `agents/learnassist/` (`agent`, `tools`, `prompt`, `context`, `state`, `runner`, `checkpointer`).

## Read these first for deeper context

- [plan.md](plan.md) — overall architecture
- [src/vidyalaya_ai/api/api_plan.md](src/vidyalaya_ai/api/api_plan.md) — API spec
- [src/vidyalaya_ai/llm/llm_plan.md](src/vidyalaya_ai/llm/llm_plan.md) — LLM strategy

## Maintenance

Update this map when adding/removing a top-level folder, or a subfolder under `src/vidyalaya_ai/` or `ingestion/`. Do NOT list individual files or functions here — those belong in code.
