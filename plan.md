# Vidyalaya AI — Launch Readiness Plan

Plan to take LearnAssist (Agent 1) from "working" to "launch-ready": move off MongoDB to
cheaper Postgres, add error handling, usage/token accounting, per-user overrides, an admin
API, persistent chat history, and checkpoint cleanup.

---

## 1. Current state (what exists and works today)

**Architecture**
- FastAPI on Railway. Firebase Auth (identity only; tokens verified, never stored).
- LearnAssist agent built with LangChain `create_agent` (LangGraph ReAct: model ⇄ tools).
- Tool `search_textbook` → Qdrant retrieval (Gemini embeddings). The model decides *whether*
  to search; the tool always searches with the student's raw text.
- LLM via a provider layer, switchable in `.env` (`google` or `openrouter`; model id configurable).
  Embeddings always Gemini.
- Memory: MongoDB checkpointer (`MongoDBSaver`), one thread per student
  (`thread_id = learnassist:{firebase_uid}`). Only `messages` are checkpointed.
- Per-turn inputs (board, class, subject, language) passed via `context=` each request — not stored.
- System prompt injected per request (`dynamic_prompt`) — not stored.
- Last 10 messages sent to the model (`trim_messages` in a `wrap_model_call` hook); full history
  kept in the checkpointer.
- Orphan-heal hook removes a dangling tool turn left by a crashed turn (loop-safe).
- Daily quota: `daily_usage` counter (3/day default), `quota_override` per user
  (`unlimited` | int). IST reset.

**Data stores**
- MongoDB Atlas: `users`, `student_profiles`, `daily_usage`, `checkpoints`, `checkpoint_writes`.
- Qdrant: textbook chunks + embeddings (unchanged by this plan).

**Endpoints**
- `GET /health`, `GET /auth/me`, `GET/PUT /me/profile`, `GET /me/usage`, `POST /learnassist/chat`.

**Known gaps (this plan addresses)**
- Mongo cost; LLM/provider failures surface as raw 500s; no usage/token tracking; no admin tools;
  no per-user LLM override; checkpoints grow unbounded; no permanent chat history for scroll-back.

---

## 2. Decisions (locked with product owner)

- **Database:** migrate Mongo → **Postgres**. Host: Supabase, but code stays **DB-agnostic**
  (any Postgres via `DATABASE_URL`).
- **Access layer:** **SQLAlchemy 2.x async + asyncpg**. **Alembic** added but used pragmatically —
  during dev, freely drop/recreate tables (no migration churn); adopt migration discipline only
  as we approach production.
- **Chat history:** student sees their **full past conversation** (single continuous chat). Stored
  in our own **`messages` table** (permanent, display-only), independent of the checkpointer — so
  checkpoints can be pruned for cost without losing what the user sees.
- **Checkpoint retention:** keep **last 50 rows per thread** + **expire threads idle > 90 days**.
  Safe because `messages` holds the real history and the model only needs the last 10.
- **Usage logging:** **full per-turn log** in `usage_events`, written **non-blocking after the
  response**. Safe because quota enforcement lives in `daily_usage` (blocking hot path); a rare
  lost analytics row never affects quota or correctness. (Revisit to blocking/outbox when real
  paid billing arrives.)
- **Per-user overrides:** quota (exists) + new `llm_provider_override` / `llm_model_override`
  (e.g. give a test user unlimited quota and a stronger model).
- **Admin:** JSON API only (no UI), gated by existing `users.role == "admin"`.
- **Error handling:** retries + timeout + typed errors so the app never receives a raw 500.

Why Postgres for the checkpointer is safe: `langgraph-checkpoint-postgres` provides
`AsyncPostgresSaver`, **interface-compatible with `MongoDBSaver`** — no graph code changes, only
`await saver.setup()` once to create its tables.

---

## 3. Target data model (Postgres)

| Table | Purpose | Hot path? | Notes |
|---|---|---|---|
| `users` | identity, role, status, overrides | yes (auth) | + `llm_provider_override`, `llm_model_override` |
| `student_profiles` | board, class, language | onboarding | as today |
| `daily_usage` | quota counter | **yes (blocking)** | unique (firebase_uid, date_ist, agent) |
| `messages` | permanent chat history (scroll-back) | no | id, firebase_uid, thread_id, agent, role, content, citations(jsonb), created_at |
| `usage_events` | analytics log | no (async) | tokens, llm_calls, tool_calls, model, agent, created_at |
| checkpoint tables | agent runtime memory | yes | managed by `AsyncPostgresSaver.setup()`; pruned |
| *(later)* `subscriptions`, `student_links` | payments, parent/teacher | — | not now |

Token counts come from LangChain response `usage_metadata` (Gemini + OpenRouter both return it),
summed across the turn's AI messages.

---

## 4. Phases

Phase 1 is the gate (everything writes to the final DB). Phases 2–7 are independent after it and
can ship in any order.

### Phase 1 — Postgres migration (foundation)
- Add `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `langgraph-checkpoint-postgres`; drop
  `motor`, `pymongo`, `langgraph-checkpoint-mongodb`.
- `DATABASE_URL` config (generic Postgres). New `db/` engine + async session.
- SQLAlchemy models for `users`, `student_profiles`, `daily_usage`. For dev: create tables on
  startup (Alembic baseline added but not enforced yet).
- Rewrite repository/service SQL, keeping the **same function signatures** so routers/dependencies
  are untouched: `users/repository.py`, `quota/service.py`. The quota atomic
  upsert+increment becomes an `INSERT ... ON CONFLICT DO UPDATE ... RETURNING count`.
- Swap checkpointer `MongoDBSaver` → `AsyncPostgresSaver`; `await setup()` in app lifespan startup;
  update `close` logic.
- Verify: onboard → chat → follow-up → quota all pass on Postgres; checkpoints land in PG;
  restart preserves memory; second device continues same thread.

### Phase 2 — Error handling (no raw 500s)
- Add `ModelRetryMiddleware` to the agent (retry transient model/provider errors with backoff).
- Wrap agent invocation in `asyncio.wait_for` timeout guard.
- Map failures to clean JSON in `api/exceptions.py`:
  - quota → 429 (exists)
  - model/provider unavailable or rate-limited → 503 "Assistant is busy, please try again."
  - timeout → 504 "That took too long, please try again."
  - unexpected → 500 generic safe text (exists). Full detail logged server-side only.
- Verify: forced model failure → friendly 503; slow call → 504; never a stack trace to the client.

### Phase 3 — Messages table (permanent chat history / scroll-back)
- `messages` table + model.
- In the runner, after a successful turn, persist the human message + AI answer (+ citations).
  Reuse the same post-response non-blocking path as usage (Phase 4).
- `GET /me/history?limit=&before=` — paged, returns the student's conversation oldest→newest for
  scroll-back. (Single thread per student, so no thread param needed.)
- Verify: after chats, history endpoint returns the full conversation in order; survives checkpoint
  cleanup.

### Phase 4 — Usage / token accounting
- `usage_events` table + model.
- Capture per turn in the runner: `llm_calls`, `tokens_input/output/total` (from `usage_metadata`),
  `tool_calls`, `model`, `agent`.
- Write `usage_events` non-blocking after the response (FastAPI BackgroundTask / asyncio task).
- Verify: after N chats, row counts and summed token/call columns match actual activity.

### Phase 5 — Per-user LLM + quota overrides
- Add `llm_provider_override`, `llm_model_override` columns.
- Replace the single cached agent with `get_agent_for(provider, model)` cached by (provider, model).
- Runner resolves effective provider/model: user override → else global env default → pick/build
  matching agent. Quota override already honored.
- Verify: a user with an override uses it (logged in `usage_events.model`); others use default.

### Phase 6 — Admin API
- `require_admin` dependency (403 if `role != "admin"`).
- Endpoints:
  - `GET /admin/users` — paged list (uid, email, role, status, overrides, last_seen).
  - `GET /admin/users/{uid}` — profile + overrides + usage summary.
  - `GET /admin/users/{uid}/usage` — rollup by agent/day (requests, llm_calls, tokens).
  - `PATCH /admin/users/{uid}` — set quota_override, llm overrides, status.
  - `GET /admin/stats` — active users, requests/tokens today, top users, per-agent split.
- Become admin by setting `role='admin'` in DB.
- Verify: admin sees correct data; non-admin gets 403.

### Phase 7 — Checkpoint cleanup
- Keep last 50 checkpoint rows per thread; delete threads idle > 90 days.
- Prefer the checkpointer's built-in prune/TTL API if available; else SQL.
- Run as a scheduled job (Railway cron / scheduled task hitting an internal endpoint, or a script).
- Verify: old/idle checkpoints removed; active threads and `messages` untouched.

---

## 5. What stays the same

- The LangGraph agent design (create_agent, tools, trim, heal, dynamic prompt) — unchanged.
- Qdrant retrieval + Gemini embeddings — unchanged.
- The `/learnassist/chat` request/response contract — unchanged (additive `usage` already present).
- "One continuous chat per student" UX — unchanged.

## 6. Out of scope (future)

- Tutor Agent (separate plan).
- Subscriptions / payments, parent/teacher roles (`subscriptions`, `student_links`).
- Prompt tuning passes (ongoing, as needed).
- `max_tokens=1200` truncation handling — revisit in Phase 2 if observed.

---

## 7. Verification summary

- **P1:** full flow on Postgres; memory survives restart.
- **P2:** failures → friendly 4xx/5xx, never raw 500/stack trace.
- **P3:** scroll-back shows full conversation; survives cleanup.
- **P4:** usage_events totals match real calls/tokens.
- **P5:** override users use overridden model/quota; others default.
- **P6:** admin data correct; non-admin blocked.
- **P7:** old checkpoints pruned; history + active threads intact.
