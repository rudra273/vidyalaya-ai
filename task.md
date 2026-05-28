# Vidyalaya AI Roadmap

Goal: scale the working Release 1 system into a reliable student learning app.

Current working path:

```text
Android app
-> Railway FastAPI backend
-> LearnAssist agent
-> retrieve_textbook tool
-> Qdrant Cloud
-> Gemini Embedding 2 retrieval
-> Gemini/LangChain answer
```

## Release 1 Complete

- [x] OCR pipeline selected: Surya OCR.
- [x] Class 8 textbooks OCR completed.
- [x] Class 8 OCR converted to clean JSONL/MD.
- [x] JSONL metadata standardized:
  - board
  - class
  - subject
  - book_name
  - book_id
  - language
  - source_pdf
  - page_no
  - text
- [x] Page-aware chunking implemented.
- [x] Gemini Embedding 2 selected.
- [x] Embedding dimension fixed at 1536.
- [x] Class 8 embeddings generated and saved locally.
- [x] Qdrant selected as vector DB.
- [x] Deterministic point IDs implemented.
- [x] Qdrant Cloud created and configured.
- [x] Class 8 embeddings uploaded to Qdrant Cloud.
- [x] Qdrant Cloud collection count validated:
  ```text
  1468
  ```
- [x] Qdrant payload indexes created:
  - board
  - class
  - subject
  - book_id
  - page_no
  - chunk_index
- [x] Retrieval supports:
  - board filter
  - class filter
  - optional subject filter
  - subject discovery when subject is missing
- [x] Context merge/expand implemented.
- [x] Basic RAG evaluation passed:
  ```text
  Report: reports/rag_eval_class8.jsonl
  Total cases: 14
  Top-10 expected page pass: 14/14
  Final context expected page pass: 14/14
  Failed cases: 0
  ```
- [x] `retrieve_textbook` tool implemented.
- [x] LLM provider layer implemented.
- [x] Gemini chat model wired through LangChain.
- [x] Direct Gemini SDK kept for embeddings only.
- [x] LearnAssist agent implemented.
- [x] FastAPI backend implemented.
- [x] API endpoints implemented:
  - `GET /health`
  - `POST /learnassist/chat`
- [x] Railway deployment config added.
- [x] Railway backend deployed.
- [x] Swagger UI validation completed.
- [x] Android app integration completed.
- [x] Android app can call backend and receive answers using Qdrant context.

## Fixed Decisions

- Vector DB: Qdrant Cloud.
- Embedding model: Gemini Embedding 2 (`gemini-embedding-2`).
- Embedding dimension: 1536.
- LLM calls: LangChain-compatible provider layer.
- Current deployed agent: LearnAssist.
- Current deployed app backend: FastAPI on Railway.
- Current indexed class: Class 8 only.
- Current board: `scert_odisha`.
- Retrieval tuning is server-side, not Android-controlled.
- Auth direction: Google SSO in Android through Firebase Auth; backend verifies Firebase ID token.
- Chat thread naming: use `thread_id`, not `conversation_id`.
- Android sends trusted filters:
  - query
  - board
  - class_no
  - subject optional
  - language optional

## Current Gaps

- [ ] No persistent chat history.
- [ ] Railway auth redeploy validation is pending.
- [ ] No user profiles.
- [ ] No rate limiting.
- [ ] No streaming response.
- [ ] No LangGraph orchestration yet.
- [ ] No Tutor Agent implementation yet.
- [ ] Only class 8 is indexed.
- [ ] No automated deployed API regression test.
- [ ] No production monitoring/alerting.
- [ ] No cost/usage dashboard for Gemini and Qdrant.
- [ ] No admin tool to reingest or validate new classes.

## Recommended Next Order

Do not jump to LangGraph or multi-agent first.

The next safest order is:

1. Stabilize the live Release 1 API.
2. Add Google SSO auth and trusted user identity.
3. Define `thread_id` and message ownership.
4. Add backend conversation storage.
5. Add classes 6, 7, 9, and 10 to RAG.
6. Add streaming responses.
7. Then introduce LangGraph if the agent flow needs memory/tools/state.
8. Then build Tutor Agent.

Reason: scaling the data and app reliability will teach us more than adding agent complexity now.

## Phase 24: Release 1 Stabilization

- [ ] Collect 20-50 real Android questions.
- [ ] Save failures manually with:
  - query
  - subject selected or missing
  - expected answer
  - actual answer
  - citations
  - latency
- [ ] Check Railway logs for errors.
- [ ] Check Qdrant Cloud usage.
- [ ] Check Gemini usage.
- [ ] Identify repeated failure types:
  - wrong subject
  - correct subject but weak context
  - answer too long
  - answer too short
  - citation missing
  - Odia language issue
  - Android rendering issue
- [ ] Tune prompt only if repeated failures show a pattern.
- [ ] Tune retrieval only if repeated failures show a pattern.

## Phase 25: Firebase Auth For Google SSO

Decision: use Google login from Android through Firebase Auth.

Implemented backend flow:

```text
Android Google Sign-In through Firebase
-> Android receives Firebase ID token
-> Android sends Authorization: Bearer <firebase_id_token>
-> FastAPI verifies token with Firebase Admin SDK
-> backend extracts stable Firebase uid
-> backend uses that as authenticated user identity
```

Do not trust `email`, `name`, or `user_id` sent directly from Android body. The backend should trust only the verified Firebase token.

Backend user identity shape:

```json
{
  "user_id": "firebase_uid",
  "email": "student@example.com",
  "name": "Student Name"
}
```

Temporary internal user ID:

```text
firebase_uid
```

Later, when MongoDB is added, map Firebase identity to an internal UUID.

### Backend Tasks

- [x] Add Firebase Admin SDK dependency.
- [x] Add Firebase auth config.
- [x] Add environment variable:
  ```text
  FIREBASE_SERVICE_ACCOUNT_JSON_BASE64=<base64-encoded-service-account-json>
  ```
- [x] Add auth helper under `src/vidyalaya_ai/auth`.
- [x] Verify Firebase ID token on backend.
- [x] Extract user identity from token.
- [x] Add FastAPI dependency for authenticated user.
- [x] Keep `/health` public.
- [x] Add protected `/auth/me`.
- [x] Protect `/learnassist/chat`.
- [x] Return `401` for missing/invalid token.
- [x] Do not accept user identity in chat request body.
- [x] Refactor FastAPI into routers/schemas/dependencies.
- [x] Move deployment entrypoint to `vidyalaya_ai.main:app`.
- [x] Update Railway start command.
- [x] Update Railway deployment docs.
- [ ] Add Firebase service account variable in Railway.
- [ ] Redeploy Railway backend.
- [ ] Validate `/auth/me` with a real Flutter Firebase token.
- [ ] Validate `/learnassist/chat` with a real Flutter Firebase token.

### Android Tasks

- [x] Add Google Sign-In.
- [x] Configure Firebase project for Android.
- [x] Add Firebase/Google sign-in Flutter packages.
- [x] Get Firebase ID token after login.
- [ ] Store token in memory or secure storage.
- [ ] Add header to protected API calls:
  ```http
  Authorization: Bearer <firebase_id_token>
  ```
- [ ] On `401`, ask user to sign in again.
- [ ] Keep `/health` call unauthenticated.
- [ ] Do not send fake user ID in request body.
- [ ] Continue sending:
  - query
  - board
  - class_no
  - subject optional
  - language optional

### Tradeoffs

Pros:

- low login friction
- no password storage
- Android-friendly
- stable user identity
- good foundation for chat history

Cons:

- depends on Google
- some students may use parent/school accounts
- backend token verification is required
- privacy/consent still matters for minors

## Phase 26: Thread And Chat History Decision

Decision needed: where to store chat history.

Recommended path:

- MVP now: Android keeps short local session history for UI only.
- Next backend version: store chat history in MongoDB.

Why MongoDB later:

- conversation data is document-shaped
- easy to store messages, citations, metadata, timestamps
- works well with user/session IDs
- easier than forcing chat data into SQL early

Do not use Qdrant for chat history. Qdrant is for retrieval vectors, not primary conversation storage.

Tasks:

- [ ] Decide chat history owner for next release:
  - Android-only temporary history
  - backend MongoDB persistent history
- [ ] Define `thread_id`.
- [ ] Define `user_id`.
- [ ] Define message schema:
  - role
  - text
  - citations
  - retrieval metadata
  - created_at
- [ ] Decide how much history to send back into the LLM.
- [ ] Decide retention policy.

## Phase 27: Add More Classes To RAG

This should happen before Tutor Agent.

Priority:

1. Class 10
2. Class 9
3. Class 7
4. Class 6

Reason: class 9/10 likely has higher immediate academic value.

Tasks per class:

- [ ] Run OCR.
- [ ] Convert raw OCR to JSONL with final metadata.
- [ ] Validate 10-20 pages manually.
- [ ] Chunk pages.
- [ ] Generate Gemini embeddings.
- [ ] Upload embeddings to Qdrant Cloud.
- [ ] Validate collection count.
- [ ] Run 10-20 retrieval test questions.
- [ ] Add evaluation report.
- [ ] Test Android query with that class.

Collection strategy:

- Keep the same Qdrant collection.
- Use metadata filters:
  - board
  - class
  - subject
  - book_id

## Phase 28: Streaming Response

Do this after Android API is stable.

Benefits:

- better perceived latency
- answer starts appearing while model is still generating

Risks:

- Android integration is more complex
- Railway/proxy behavior needs testing
- error handling is harder

Tasks:

- [ ] Decide streaming protocol:
  - Server-Sent Events first
  - WebSocket later only if needed
- [ ] Add `/learnassist/chat/stream`.
- [ ] Stream tokens from LangChain model.
- [ ] Keep non-streaming endpoint as fallback.
- [ ] Add Android streaming UI.
- [ ] Test disconnects and retries.

## Phase 29: LangGraph Decision

Do not add LangGraph just because it exists.

Add LangGraph when one of these becomes true:

- agent needs multi-step tool decisions
- agent needs durable conversation state
- agent needs memory summarization
- agent needs retries/fallback branches
- Tutor Agent needs topic progression
- multiple agents need routing

Possible first LangGraph graph:

```text
receive query
-> inspect state
-> decide retrieval needed
-> retrieve textbook if needed
-> answer
-> save conversation
```

Tasks:

- [ ] Install LangGraph.
- [ ] Define state schema.
- [ ] Convert LearnAssist flow to graph nodes.
- [ ] Add checkpointing only after storage decision.
- [ ] Keep existing FastAPI endpoint stable.
- [ ] Regression-test old API behavior.

## Phase 30: Tutor Agent

Build after:

- auth exists
- chat history exists
- more classes are indexed
- LearnAssist is stable

Tutor Agent should teach over time, not just answer one question.

Future capabilities:

- subject journey
- topic progression
- student level tracking
- short explanations
- check questions
- hints
- feedback
- revision mode
- voice interaction later

Tasks:

- [ ] Define Tutor Agent state.
- [ ] Define topic/session model.
- [ ] Define progress tracking.
- [ ] Define teaching prompt.
- [ ] Define check-question flow.
- [ ] Decide how it uses textbook retrieval.
- [ ] Add Android UI for tutor mode.

## Phase 31: Monitoring And Operations

This is easy to skip, but it matters once real users test.

Tasks:

- [ ] Add request IDs.
- [ ] Log latency per request.
- [ ] Log retrieval top score and subjects found.
- [ ] Log LLM errors separately from retrieval errors.
- [ ] Add simple `/version` endpoint.
- [ ] Add deployed API smoke test script.
- [ ] Add alerting for repeated 500 errors.
- [ ] Track Gemini usage.
- [ ] Track Qdrant usage.
- [ ] Backup embedding files and OCR JSONL.

## What We Might Be Skipping

- Privacy policy for student data.
- Terms/consent if storing chat history.
- Abuse prevention and rate limits.
- Cost controls for Gemini calls.
- Prompt injection protection.
- Admin dashboard for ingestion status.
- Automated tests for deployed API.
- Android offline/error states.
- OCR quality audit for future classes.
- Dataset/version tracking for each uploaded class.
- Migration plan from Railway to Oracle Free Tier.

## Later Improvements

- [ ] Add reranking only if top 10 has good candidates but final answers are noisy.
- [ ] Add hybrid sparse+dense search if exact Odia terms or names are missed.
- [ ] Add chapter metadata later if chapter detection becomes available.
- [ ] Add image/page references later for multimodal retrieval.
- [ ] Add voice interaction for Tutor Agent.
