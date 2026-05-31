# Vidyalaya AI — Launch Readiness Plan

Plan to take LearnAssist (Agent 1) from "working" to "launch-ready": move off MongoDB to
cheaper Postgres, add error handling, usage/token accounting, subscription-based model
selection, an admin API, persistent chat history, and checkpoint cleanup.

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
  no subscription-based model selection; checkpoints grow unbounded; no permanent chat history
  for scroll-back.

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
- **Subscription plans:** quota + LLM provider/model are selected from hardcoded plan definitions
  (`free`, `plus`, `pro`) via a user's current `subscriptions.plan_key`. Admins manually assign
  plans first; payment-provider automation comes later without redesigning the schema.
- **Admin:** JSON API only (no UI), gated by existing `users.role == "admin"`.
- **Error handling:** retries + timeout + typed errors so the app never receives a raw 500.

Why Postgres for the checkpointer is safe: `langgraph-checkpoint-postgres` provides
`AsyncPostgresSaver`, **interface-compatible with `MongoDBSaver`** — no graph code changes, only
`await saver.setup()` once to create its tables.

---

## 3. Target data model (Postgres)

| Table | Purpose | Hot path? | Notes |
|---|---|---|---|
| `users` | identity, role, status, emergency overrides | yes (auth) | keep `quota_override` for admin exceptions |
| `student_profiles` | board, class, language | onboarding | as today |
| `daily_usage` | quota counter | **yes (blocking)** | unique (firebase_uid, date_ist, agent) |
| `subscriptions` | current/historical plan assignment | yes (auth/chat) | active `plan_key` chooses quota + LLM model |
| `messages` | permanent chat history (scroll-back) | no | id, firebase_uid, thread_id, agent, role, content, citations(jsonb), created_at |
| `usage_events` | analytics log | no (async) | tokens, llm_calls, tool_calls, model, agent, created_at |
| checkpoint tables | agent runtime memory | yes | managed by `AsyncPostgresSaver.setup()`; pruned |
| *(later)* `student_links` | parent/teacher links | — | not now |

Initial `subscriptions` columns:

| Column | Purpose |
|---|---|
| `id` | primary key |
| `user_id` | FK to `users.id` |
| `firebase_uid` | denormalized lookup key |
| `plan_key` | hardcoded plan id (`free`, `plus`, `pro`) |
| `status` | `active`, `trialing`, `past_due`, `cancelled`, `expired` |
| `source` | `admin` now; later `manual`, `razorpay`, `stripe` |
| `current_period_start`, `current_period_end` | billing/entitlement window; nullable for admin/manual plans |
| `cancel_at_period_end` | payment-provider compatible cancellation flag |
| `started_at`, `ended_at` | assignment lifecycle; one current row has `ended_at IS NULL` |
| `created_at`, `updated_at` | audit timestamps |
| `metadata` | JSONB for provider-specific details later |

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

### Phase 5 — Subscription plans for quota + model selection
- Add a `subscriptions` table and service for resolving the user's effective plan. No active
  subscription row means `free`.
- Hardcode plan definitions in code first:
  - `free`: default daily quota + default low-cost model.
  - `plus`: higher daily quota + stronger/costlier model.
  - `pro`: highest daily quota + strongest configured model.
- Replace the single cached agent with `get_agent_for(provider, model)` cached by (provider, model).
- Chat resolves effective quota/provider/model from active subscription plan (`active` or
  `trialing`) → else `free`; keep existing `quota_override` only as an emergency admin exception.
- Log the actual model used, and optionally `plan_key`, in `usage_events`.
- Verify: no subscription uses `free`; admin-assigned `plus`/`pro` users use that plan's quota and
  model; cancelled/expired users fall back to `free`.

### Phase 6 — Admin API
- `require_admin` dependency (403 if `role != "admin"`).
- Endpoints:
  - `GET /admin/users` — paged list (uid, email, role, status, overrides, last_seen).
  - `GET /admin/users/{uid}` — profile + current subscription/plan + usage summary.
  - `GET /admin/users/{uid}/usage` — rollup by agent/day (requests, llm_calls, tokens).
  - `PATCH /admin/users/{uid}` — set quota_override and account status.
  - `PATCH /admin/users/{uid}/subscription` — manually assign `plan_key`/`status`; closes the
    previous current subscription row and creates a new one.
  - `GET /admin/stats` — active users, requests/tokens today, top users, per-agent split.
- Become admin by setting `role='admin'` in DB.
- Verify: admin sees correct data and can assign plans; non-admin gets 403.

### Phase 7 — Checkpoint cleanup
- Keep last 50 checkpoint rows per thread; delete threads idle > 90 days.
- Prefer the checkpointer's built-in prune/TTL API if available; else SQL.
- Run as a scheduled job (Railway cron / scheduled task hitting an internal endpoint, or a script).
- Verify: old/idle checkpoints removed; active threads and `messages` untouched.

---

## 4b. Channel memory architecture (post-launch correctness fix)

### Problem observed
A single lifelong thread per student (`thread_id = learnassist:{firebase_uid}`) makes
**every prior turn — including failed/timed-out ones and other subjects — leak into the
next answer**. Symptoms:
- "hi" answered a previous question about photosynthesis/chapters (a turn that had
  **timed out** but was still persisted by the checkpointer).
- Switching the requested book from science to maths still returned science answers,
  because the recent conversation window was full of science.

Root cause is **not** model power or the trim window size. Trimming bounds *how much*
stale context is sent, not *whether* it's stale. The window contained (a) a poisoned
failed turn and (b) another subject's turns. The model used them exactly as instructed.

### Design: channel = memory boundary; thread is invisible plumbing
A **channel** is a place the student returns to (General, or a subject). The student
never manages threads/sessions ("new chat"/"clear") — they just pick a channel. The
server derives the thread deterministically:

```
thread_id = {agent}:{firebase_uid}:{board}:{class_no}:{channel}
```

`board`/`class_no` are in the key (not just the uid) because `student_profiles` is
**updateable** — a class promotion, re-onboard, or board switch must NOT inherit old
memory. Longer keys are cheap; wrong memory is expensive.

Examples (one student):
```
learnassist:uid123:scert_odisha:8:general    # ask anything, cross-subject
learnassist:uid123:scert_odisha:8:science    # science only
learnassist:uid123:scert_odisha:8:maths      # maths only
tutor:uid123:scert_odisha:8:science          # future Tutor agent, science only
```

Rules:
- **General** is its own channel and does **not** share memory with subject channels.
- Each **subject channel** is isolated → switching subject can't leak (structural fix).
- **Tutor** (future) is a separate `agent` prefix reusing the same scheme, so its
  pedagogical state never pollutes Q&A memory.
- Frontend surfaces channels as tabs (`[General] [Science] [Maths] …`); **screen =
  memory** (what's visible always matches what the model remembers).

### Request contract: `channel` is the single source of truth
`channel` is authoritative; the server derives `subject` from it. We do **not** accept
both a `channel` and an independent free-form `subject` — two fields that can disagree
are how this bug class returns.

```jsonc
{ "channel": "science", "message": "explain chapter 1" }
// -> subject = "science"; thread = ...:8:science; retrieval filtered to science

{ "channel": "general", "message": "hi" }
// -> subject = null; thread = ...:8:general; retrieval unfiltered
```
Inside a subject channel the subject filter is **enforced** — never silently
"search all subjects".

### Reliability: prevent/clean incomplete turns (not write-side rollback)
`AsyncPostgresSaver` exposes `adelete_thread` (whole thread) and `aprune`, but **no
per-checkpoint delete by id** — so a failed turn cannot be surgically rolled back on
the write side without nuking the whole conversation. Instead we **clean incomplete
turns on read**, in the `before_model` healing middleware, which already runs each turn
and is the mechanism we trust. This also covers process crashes, not just timeouts.

Healing is **lazy/on-read**: it cleans what the *model* sees. The poisoned checkpoint
may briefly remain in Postgres until the next turn heals it — acceptable because the
clean history source of truth is the `messages` table (chatlog), read separately.

### Phases
**Phase A — reliability (ship first, no API/app change):**
- Harden `_heal_history` to also drop a dangling **HumanMessage with no completed
  answer** (currently it only strips orphaned tool calls), so a timed-out/crashed turn
  can't leak into the next, new question.
- Stop greetings/small-talk from triggering retrieval.
- Make the latest user message authoritative over stale context.
- Tests: `timeout → next "hi"` must not answer the prior question.

**Phase B — channels (structural fix + product vision):**
- Add `channel` to the request (default `general`); subject channels require a known
  subject value, derived from `channel` (single source of truth, no free-form subject).
- Thread key `{agent}:{uid}:{board}:{class_no}:{channel}`, built by one shared
  `build_thread_id` helper used by both the chat and history endpoints (no drift).
- Enforce subject filter inside subject channels; never silently search all subjects.
- `GET /me/history?channel=…` scopes display history to that channel's thread
  (board/class taken from the profile), so each tab shows only its own messages
  (screen = the model's per-channel memory).

**Phase C — future:** Tutor agent reuses the key scheme with a `tutor:` prefix. No rework.

---

## 5. What stays the same

- The LangGraph agent design (create_agent, tools, trim, heal, dynamic prompt) — unchanged.
- Qdrant retrieval + Gemini embeddings — unchanged.
- "One continuous chat per student" UX — superseded by §4b channels (General stays the
  default channel, so the single-chat experience is preserved until tabs ship).

## 6. Out of scope (future)

- Tutor Agent (separate plan).
- Payment-provider automation/webhooks (Razorpay/Stripe), parent/teacher roles (`student_links`).
- Prompt tuning passes (ongoing, as needed).
- `max_tokens=1200` truncation handling — revisit in Phase 2 if observed.

---

## 7. Verification summary

- **P1:** full flow on Postgres; memory survives restart.
- **P2:** failures → friendly 4xx/5xx, never raw 500/stack trace.
- **P3:** scroll-back shows full conversation; survives cleanup.
- **P4:** usage_events totals match real calls/tokens.
- **P5:** subscribed users use plan model/quota; no/inactive subscription falls back to `free`.
- **P6:** admin data correct, plan assignment works, non-admin blocked.
- **P7:** old checkpoints pruned; history + active threads intact.
