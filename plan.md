# Vidyalaya AI — Architecture Plan

> **Scope:** This document covers the runtime architecture for **LearnAssist (Agent 1) only**.
> Tutor Agent and other agents will be planned in follow-up docs.

---

## 1. What this app is

FastAPI backend serving a Flutter Android app. Indian school students ask textbook questions, get answers with citations.

- **Identity:** Firebase Auth (Google Sign-In) — token verified server-side
- **Knowledge store:** Qdrant Cloud with Gemini-embedded SCERT Odisha class-8 textbook chunks
- **LLM:** Gemini chat via `langchain-google-genai`
- **Persistence:** MongoDB Atlas (introduced in this plan)
- **Deploy:** Railway

---

## 2. Current state (already built)

- FastAPI app with `GET /health`, `GET /auth/me`, `POST /learnassist/chat`
- Firebase token verification in [src/vidyalaya_ai/auth/firebase.py](src/vidyalaya_ai/auth/firebase.py) and [src/vidyalaya_ai/api/dependencies.py](src/vidyalaya_ai/api/dependencies.py)
- Stateless LearnAssist agent in [src/vidyalaya_ai/agents/learnassist_agent.py](src/vidyalaya_ai/agents/learnassist_agent.py) — plain LangChain, no memory
- Retrieve-textbook tool in [src/vidyalaya_ai/tools/](src/vidyalaya_ai/tools/) backed by Qdrant
- Ingestion pipeline in [ingestion/](ingestion/) — OCR JSONL → chunks → embeddings → Qdrant
- No database, no chat history, no user profiles, no quotas

---

## 3. Target architecture (where we're going)

```
Flutter Android
   │  Firebase ID token + cached profile (board, class, language)
   ▼
FastAPI on Railway   (async, motor, langgraph)
   ├─ Auth middleware    → verify Firebase token (local JWT, ~1ms)
   ├─ Quota middleware   → atomic daily counter check
   ├─ /me/profile        → onboarding writes (Mongo)
   ├─ /me/usage          → "how many queries left today?"
   └─ /learnassist/chat  → LangGraph (retrieve → llm) with MongoDBSaver
            │
            ▼
   ┌─────────────────────┬───────────────────┬─────────────┐
   │ MongoDB Atlas       │ Qdrant Cloud      │ Gemini API  │
   │ users, profiles,    │ textbook chunks   │ chat + embed│
   │ checkpoints,        │ + embeddings      │             │
   │ daily_usage         │                   │             │
   └─────────────────────┴───────────────────┴─────────────┘
```

### Key design choices (locked)

| Decision | Choice | Why |
|---|---|---|
| Profile on hot path | **Client sends** board/class/language each request | Stateless server, no Mongo read on chat path, fastest |
| Server stores profile too | Yes — Mongo is the authoritative copy | Cross-device sync, recovery, admin edits later |
| Chat memory | **One thread per user**, last 10 messages to LLM | Matches a 6th-grader's mental model; cheap prompts |
| Memory storage | **LangGraph `MongoDBSaver`** checkpointer | Industry-standard, handles tool-call message format, free Tutor support later |
| `thread_id` format | `learnassist:{firebase_uid}` | One persistent chat per student; namespace ready for Tutor |
| Mongo driver | **motor** (async) | All hot paths become async, parallelizable with `asyncio.gather` |
| Daily quota | 3 queries / day for free; `quota_override` per user | Cost control; admin override for test/internal users |
| Quota timezone | IST (`Asia/Kolkata`) | Indian students; reset at midnight IST |
| Tampering risk on board/class | Validate ranges only; defer enforcement | No paywall yet; lying gets you bad answers, not data breach |

---

## 4. MongoDB schema

### 4.1 Collections (MVP)

| Collection | Purpose | Owner |
|---|---|---|
| `users` | Identity, role, status, quota override | App |
| `student_profiles` | Board, class, language, school | App |
| `daily_usage` | Per-user per-day query counter (TTL-cleaned) | App |
| `checkpoints` + `checkpoint_writes` | LangGraph state per `thread_id` | LangGraph MongoDBSaver |

Future (not built now): `subscriptions`, `student_links` (parent/teacher), `tutor_sessions`, `chapter_progress`.

### 4.2 Document shapes

#### `users`
```json
{
  "_id": ObjectId(),
  "firebase_uid": "abc123",
  "email": "student@example.com",
  "display_name": "Asha P.",
  "role": "student",                  // "student" | "admin"
  "status": "active",                 // "active" | "suspended" | "deleted"
  "quota_override": null,             // null | "unlimited" | int (custom daily limit)
  "created_at": ISODate(),
  "last_seen_at": ISODate(),
  "schema_version": 1
}
```
**Indexes:**
- `{firebase_uid: 1}` unique
- `{email: 1}` unique sparse

#### `student_profiles`
```json
{
  "_id": ObjectId(),
  "user_id": ObjectId("..."),         // → users._id
  "firebase_uid": "abc123",           // denormalized for fast lookup without users join
  "board": "scert_odisha",
  "class_no": 8,
  "preferred_language": "or",
  "school_name": null,
  "onboarding_completed": true,
  "created_at": ISODate(),
  "updated_at": ISODate(),
  "schema_version": 1
}
```
**Indexes:**
- `{user_id: 1}` unique
- `{firebase_uid: 1}` unique

#### `daily_usage`
```json
{
  "_id": ObjectId(),
  "firebase_uid": "abc123",
  "date_ist": "2026-05-28",           // YYYY-MM-DD in IST
  "agent": "learnassist",             // namespace per agent for future Tutor counter
  "count": 2,
  "first_at": ISODate(),
  "last_at": ISODate()
}
```
**Indexes:**
- `{firebase_uid: 1, date_ist: 1, agent: 1}` unique
- `{first_at: 1}` TTL: 35 days (auto-cleanup)

#### LangGraph collections (managed)
`checkpoints` and `checkpoint_writes` — schema owned by `langgraph-checkpoint-mongodb`. We only configure `db_name`. Query by `thread_id` for history endpoints later.

---

## 5. API surface (LearnAssist only)

### Existing endpoints (kept)
- `GET /health` — unchanged
- `GET /auth/me` — extended response shape (adds role, onboarding status)

### New endpoints

```
GET  /me/profile
  → 200: { board, class_no, preferred_language, school_name, onboarding_completed }
  → 404: profile not yet created
  Purpose: mobile hydrates local cache after fresh install / new device

PUT  /me/profile
  body: { board, class_no, preferred_language, school_name? }
  → 200: full profile doc
  Purpose: onboarding write + later edits

GET  /me/usage
  → 200: { date_ist, used, limit, remaining, unlimited: bool }
  Purpose: mobile shows "X queries left today"
```

### Changed endpoints

```
POST /learnassist/chat
  body: { message, board, class_no, subject?, language? }
  ── removed: query (renamed to message), debug (kept as ?debug=1 query param)
  ── client supplies board/class/language from its local cache
  → 200: { answer, citations, retrieval, usage: { used, limit, remaining } }
  → 429: { error: { code: "quota_exceeded", message, retry_at_ist } }
  → 400: { error: { code: "bad_request", message } }  // invalid board/class_no
```

**Why include `usage` in the chat response:** mobile updates its "queries left" counter without a separate round-trip.

### Validation rules (server-side, no DB read)
- `message`: non-empty, max 2000 chars
- `board` ∈ known set (start with `{"scert_odisha"}`)
- `class_no` ∈ 1..12
- `subject` optional, lowercased, max 64 chars
- `language` optional, ISO-639-1 code or null

Rejected requests do **not** increment the quota counter.

---

## 6. Hot path & performance

### Cold path (once per install / new device)
```
GET /me/profile  → 1 Mongo read → mobile caches locally
```

### Hot path (every chat) — under 1.5s p50 target
```
1. verify Firebase token             ~1ms    (local JWT, cached cert)
2. validate request body             <1ms    (pydantic + range checks)
3. atomic quota inc + check          ~5ms    (Mongo, indexed, single op)
4. LangGraph load checkpoint         ~5-10ms (Mongo, indexed by thread_id)
5. retrieve_textbook                 ~50-200ms (Qdrant + embedding)
6. LLM call (Gemini)                 ~500-2000ms ← dominant
7. LangGraph save checkpoint         ~5-10ms
8. return response
```

Profile is **never** read on hot path. Quota check is one atomic op. Concurrent users scale linearly — no shared cache, no warmup, no contention.

### Concurrency model
- All routes and repositories are `async def`
- Mongo via `motor`
- Independent I/O parallelized with `asyncio.gather` where applicable (e.g., checkpoint save + response build)
- Single FastAPI worker handles many concurrent chats; horizontal scaling is trivial because the server is stateless on profile

---

## 7. Daily quota & admin override

### Logic (per chat request, in middleware)

```
DEFAULT_DAILY_LIMIT = 3

user = users.find_one({firebase_uid})       ← cached via lru_cache(maxsize=10_000, TTL ~ 60s)
                                              keyed by firebase_uid; admin overrides apply on next TTL refresh

if user.quota_override == "unlimited":
    skip quota check, skip increment
else:
    limit = user.quota_override if isinstance(int) else DEFAULT_DAILY_LIMIT
    today_ist = (utcnow + 5h30m).date().isoformat()
    doc = daily_usage.find_one_and_update(
        {firebase_uid, date_ist: today_ist, agent: "learnassist"},
        {$inc: {count: 1, ...}, $setOnInsert: {first_at: now}, $set: {last_at: now}},
        upsert=True, return_document=AFTER
    )
    if doc.count > limit:
        raise QuotaExceeded(used=doc.count, limit=limit, retry_at_ist=tomorrow_midnight)
```

### Why atomic-inc-then-check (not check-then-inc)
- Race-condition safe under concurrent requests from the same user (multi-device, retries)
- Single Mongo round-trip
- Counter may show `count > limit` briefly when blocked requests still hit the counter — acceptable, accurate as "attempts" metric

### Admin override
- Set manually in Mongo for MVP: `db.users.updateOne({firebase_uid: "..."}, {$set: {quota_override: "unlimited"}})`
- Test accounts get `"unlimited"`
- A pilot user could get `quota_override: 50` (custom int)
- A future `/admin/users/:id/quota` endpoint slots in without schema change

### User cache invalidation
- TTL on the in-memory cache (~60s) is enough — admin changes propagate within a minute
- For instant invalidation later: a small `pubsub` or just restart workers

---

## 8. LangGraph migration of LearnAssist

### Current shape ([learnassist_agent.py](src/vidyalaya_ai/agents/learnassist_agent.py))
- Plain function `answer_with_learnassist(request) -> dict`
- Calls `retrieve_textbook` then `llm.invoke([SystemMessage, HumanMessage])`
- No state, no memory

### Target shape (new file: `src/vidyalaya_ai/agents/learnassist_graph.py`)

```
State (TypedDict):
  messages: Annotated[list[BaseMessage], add_messages]    # LangGraph appends
  board: str
  class_no: int
  subject: str | None
  language: str | None
  context_blocks: list[dict]
  citations: list[dict]
  retrieval_meta: dict

Graph:
  START → retrieve_node → llm_node → END

Nodes:
  retrieve_node(state):
    → reuses retrieve_textbook() from src/vidyalaya_ai/tools/
    → writes context_blocks, retrieval_meta into state
    (does NOT append a message — context is structured, not chat)

  llm_node(state):
    → take last 10 messages from state["messages"] (trim_messages helper)
    → build system prompt (reused from current learnassist_agent.py _build_messages style)
    → inject context_blocks as part of the SystemMessage (current pattern)
    → llm.invoke(trimmed_messages_with_context)
    → return {"messages": [AIMessage(content=..., additional_kwargs={"citations": ...})]}

Compile:
  graph.compile(checkpointer=MongoDBSaver(client, db_name="vidyalaya_ai"))

Invoke:
  result = graph.invoke(
    {"messages": [HumanMessage(content=message)], "board": ..., "class_no": ..., "subject": ..., "language": ...},
    config={"configurable": {"thread_id": f"learnassist:{firebase_uid}"}}
  )
  # checkpointer auto-loads prior messages for that thread_id
  # appends the new HumanMessage + AIMessage to history
  # saves new checkpoint
```

### What's reused from current code
- `retrieve_textbook` tool — unchanged
- Prompt-building logic (`_build_messages`, `_format_context`, `_citation_heading`) — extract to a `prompts.py` module, import from `llm_node`
- Citation regex parser (`_build_citations`) — unchanged, used in `llm_node` post-processing
- Retrieval metadata builder (`_build_retrieval_metadata`) — unchanged
- LLM factory `create_chat_model` from [src/vidyalaya_ai/llm/](src/vidyalaya_ai/llm/) — unchanged

### What's removed
- `answer_with_learnassist` plain function → replaced by graph invocation
- `LearnAssistInput` dataclass → replaced by graph state TypedDict + invocation kwargs
- The old [learnassist_agent.py](src/vidyalaya_ai/agents/learnassist_agent.py) file becomes the new graph module (or split into `learnassist_graph.py` + `learnassist_prompts.py`)

### Trim strategy
- Use `langchain_core.messages.trim_messages` with `max_tokens` strategy OR a simple slice `messages[-10:]` keeping any leading SystemMessage
- Start with simple slice of last 10 messages (5 turns), tune later
- System prompt is always re-built per-turn (not stored in checkpoint state)

---

## 9. Phase-by-phase rollout

Each phase is independently mergeable, leaves the app working, and is testable end-to-end.

### Phase 0 — Foundation (deps, env, plan)
**Files:**
- [requirements.txt](requirements.txt) — add `motor`, `langgraph`, `langgraph-checkpoint-mongodb`
- [.env.example](.env.example) — add `MONGODB_URI`, `MONGODB_DB_NAME`, `LEARNASSIST_DAILY_LIMIT` (default 3)
- [plan.md](plan.md) — this document (done)

**Verify:** `pip install -r requirements.txt` succeeds; uvicorn still boots; existing `/learnassist/chat` still works.

---

### Phase 1 — MongoDB connection + users + profiles collections
**New files:**
- `src/vidyalaya_ai/db/__init__.py`
- `src/vidyalaya_ai/db/config.py` — `MongoConfig` (uri, db_name) from env
- `src/vidyalaya_ai/db/mongo.py` — async motor client singleton, `get_db()`, `ensure_indexes()` on startup
- `src/vidyalaya_ai/users/__init__.py`
- `src/vidyalaya_ai/users/models.py` — `UserDoc`, `StudentProfileDoc` pydantic models
- `src/vidyalaya_ai/users/repository.py`:
  - `async upsert_user_from_token(firebase_uid, email, name) -> UserDoc` (just-in-time provisioning)
  - `async get_profile(firebase_uid) -> StudentProfileDoc | None`
  - `async upsert_profile(firebase_uid, board, class_no, language, school?) -> StudentProfileDoc`

**Modified:**
- [src/vidyalaya_ai/api/app.py](src/vidyalaya_ai/api/app.py) — call `await ensure_indexes()` on FastAPI `startup` event; close client on `shutdown`

**Verify:** boot logs show "Mongo connected, indexes ensured"; manually insert a user via repl and read it back.

---

### Phase 2 — Async auth middleware with JIT user provisioning
**Modified:**
- [src/vidyalaya_ai/auth/models.py](src/vidyalaya_ai/auth/models.py) — extend `AuthenticatedUser` with `mongo_id`, `role`, `status`, `quota_override`
- [src/vidyalaya_ai/api/dependencies.py](src/vidyalaya_ai/api/dependencies.py) — convert `get_current_user` to `async def`, upsert the user on first sight, reject if `status != "active"`
- Add small TTL cache (60s, lru_cache + asyncio lock) keyed by `firebase_uid` to avoid Mongo read on every request

**Verify:** call `GET /auth/me` with valid token — first call creates `users` doc, subsequent calls within 60s skip Mongo (log shows cache hit).

---

### Phase 3 — /me/profile endpoints (onboarding)
**New files:**
- `src/vidyalaya_ai/api/routers/me.py`
- `src/vidyalaya_ai/api/schemas/me.py` — `ProfileRequest`, `ProfileResponse`, `UsageResponse` (usage shape now, endpoint comes in Phase 5)

**Modified:**
- [src/vidyalaya_ai/api/app.py](src/vidyalaya_ai/api/app.py) — mount `me` router

**Verify:**
1. `PUT /me/profile { board: "scert_odisha", class_no: 8, preferred_language: "or" }` → creates profile
2. `GET /me/profile` → returns same profile
3. `PUT` again with new values → updates `updated_at`

---

### Phase 4 — LangGraph migration of LearnAssist (no checkpointer yet)
**New files:**
- `src/vidyalaya_ai/agents/learnassist_prompts.py` — extract `_build_messages`, `_format_context`, `_citation_heading`, `_build_citations`, `_build_retrieval_metadata` from current agent
- `src/vidyalaya_ai/agents/learnassist_graph.py` — `build_graph()` returning a compiled `StateGraph` (no checkpointer yet — pass `None`)

**Modified:**
- [src/vidyalaya_ai/agents/__init__.py](src/vidyalaya_ai/agents/__init__.py) — export `build_learnassist_graph`
- [src/vidyalaya_ai/api/routers/learnassist.py](src/vidyalaya_ai/api/routers/learnassist.py) — call graph.ainvoke instead of `answer_with_learnassist`
- [src/vidyalaya_ai/agents/learnassist_agent.py](src/vidyalaya_ai/agents/learnassist_agent.py) — delete (functions moved to prompts.py)

**Behavior unchanged at this point**: still stateless per-request (no checkpointer), same response shape. This phase is a pure refactor to graph form so Phase 5 can drop in the checkpointer cleanly.

**Verify:** existing curl tests from [api_plan.md](src/vidyalaya_ai/api/api_plan.md) return same answers.

---

### Phase 5 — MongoDBSaver checkpointer + last-10 trim + new request shape
**New files:**
- `src/vidyalaya_ai/agents/checkpointer.py` — `get_checkpointer()` returning `AsyncMongoDBSaver` bound to the motor client + db

**Modified:**
- `src/vidyalaya_ai/agents/learnassist_graph.py` — compile with `checkpointer=get_checkpointer()`; add `trim_messages` step in `llm_node`
- [src/vidyalaya_ai/api/schemas/learnassist.py](src/vidyalaya_ai/api/schemas/learnassist.py) — new request: `{ message, board, class_no, subject?, language? }`; new response field `usage` (filled in Phase 6, defaulted to null for now)
- [src/vidyalaya_ai/api/routers/learnassist.py](src/vidyalaya_ai/api/routers/learnassist.py) — invoke with `config={"configurable": {"thread_id": f"learnassist:{user.firebase_uid}"}}`; pass per-turn board/class/subject/language as state kwargs (not in checkpoint)

**Verify:**
1. Send chat: "What is photosynthesis?" → answer
2. Send follow-up: "Explain again simply" → LLM should reference prior turn
3. Inspect Mongo `checkpoints` collection — one+ docs with `thread_id = learnassist:<uid>`

---

### Phase 6 — Daily quota middleware + /me/usage endpoint
**New files:**
- `src/vidyalaya_ai/quota/__init__.py`
- `src/vidyalaya_ai/quota/config.py` — `QuotaConfig` (default_daily_limit from env)
- `src/vidyalaya_ai/quota/service.py`:
  - `async check_and_increment(firebase_uid, agent, user) -> UsageView`
  - `async get_usage(firebase_uid, agent, user) -> UsageView`
  - Handles `quota_override` logic
  - Computes today_ist
- `src/vidyalaya_ai/quota/exceptions.py` — `QuotaExceeded`

**Modified:**
- [src/vidyalaya_ai/api/routers/learnassist.py](src/vidyalaya_ai/api/routers/learnassist.py) — `await check_and_increment(...)` before invoking the graph; on success include `usage` in response
- [src/vidyalaya_ai/api/exceptions.py](src/vidyalaya_ai/api/exceptions.py) — register `QuotaExceeded` handler → 429
- `src/vidyalaya_ai/api/routers/me.py` — add `GET /me/usage` endpoint

**Verify:**
1. New student account → send 3 chats, all succeed, each response shows `usage.remaining` decrementing
2. 4th chat → 429 with `retry_at_ist`
3. `db.users.updateOne({firebase_uid}, {$set: {quota_override: "unlimited"}})` → after 60s cache TTL, 5th chat succeeds; usage response shows `unlimited: true`
4. `GET /me/usage` returns the current count without spending one

---

### Phase 7 — Documentation refresh
**Modified:**
- [src/vidyalaya_ai/api/api_plan.md](src/vidyalaya_ai/api/api_plan.md) — update request/response examples to the new shape; document `/me/profile`, `/me/usage`, 429 quota response
- [CLAUDE.md](CLAUDE.md) — add `db/`, `users/`, `quota/` to component map; mention MongoDB + LangGraph

**Verify:** docs match running behavior.

---

## 10. End-to-end verification (after Phase 6)

```bash
# 1. Onboard
curl -X PUT $API/me/profile \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"board":"scert_odisha","class_no":8,"preferred_language":"or"}'

# 2. Hydrate (sanity)
curl $API/me/profile -H "Authorization: Bearer $TOKEN"

# 3. First chat
curl -X POST $API/learnassist/chat \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"message":"କୋଷ କିଏ ଆବିଷ୍କାର କରିଥିଲେ?","board":"scert_odisha","class_no":8,"language":"or"}'
# expect: answer, citations, usage: {used:1, limit:3, remaining:2}

# 4. Follow-up (memory check)
curl -X POST $API/learnassist/chat \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"message":"explain that in english","board":"scert_odisha","class_no":8,"language":"en"}'
# expect: AI references prior turn; usage: {used:2, limit:3, remaining:1}

# 5. Hit limit
# (send one more chat → usage:{used:3,remaining:0}; next one → 429)

# 6. Usage check
curl $API/me/usage -H "Authorization: Bearer $TOKEN"
```

---

## 11. What's deferred (do NOT build now)

- Tutor Agent (separate plan doc later)
- `tutor_sessions`, `chapter_progress`, `chapters_catalog` collections
- `subscriptions` collection (build when payments launch)
- `student_links` collection (build when parent/teacher roles launch)
- Admin UI / `/admin/*` endpoints (manual Mongo updates suffice for MVP)
- Streaming responses (SSE/WebSocket)
- Rolling chat summaries (revisit when threads regularly cross ~100 messages)
- Voice interaction (Tutor scope)
- Per-tenant rate limiting beyond per-user daily
- Topic-shift detection in last-N window (premature optimization)

---

## 12. What never gets stored

- Firebase ID tokens or Google OAuth tokens
- Profile images (use Firebase `photoURL` directly from client if ever needed)
- Card numbers, CVVs, UPI PINs (when payments arrive: provider tokens only)
- Full LLM prompts per request (logs may sample; not persisted per-message)
