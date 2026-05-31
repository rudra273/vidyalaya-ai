# Release 1 API Plan

## Purpose

Release 1 exposes the LearnAssist agent through a small FastAPI API.

The goal is to test the full flow from Android, Swagger, or curl:

```text
client request
-> FastAPI endpoint
-> LearnAssist agent
-> retrieve_textbook tool
-> LLM
-> answer + citations + retrieval metadata
```

Tutor Agent is future work and should not be included in Release 1.

Authentication uses Firebase Auth on the client. The backend does not perform Google login. Android sends a Firebase ID token:

```http
Authorization: Bearer <firebase_id_token>
```

FastAPI verifies that token with Firebase Admin SDK.
Verified Firebase users are provisioned just-in-time in MongoDB. MongoDB also stores student profiles and daily LearnAssist usage counters.

## Endpoints

### Health

```http
GET /health
```

Public endpoint. No token is required.

Response:

```json
{
  "status": "ok",
  "service": "vidyalaya-ai"
}
```

### Auth Me

```http
GET /auth/me
```

Protected endpoint. Requires:

```http
Authorization: Bearer <firebase_id_token>
```

Response:

```json
{
  "user_id": "firebase_uid",
  "firebase_uid": "firebase_uid",
  "mongo_id": "665...",
  "email": "student@example.com",
  "name": "Student Name",
  "role": "student",
  "status": "active",
  "quota_override": null
}
```

### Profile

```http
GET /me/profile
PUT /me/profile
```

Protected endpoints. `GET` returns `404` until onboarding creates a profile.

PUT request:

```json
{
  "board": "scert_odisha",
  "class_no": 8,
  "preferred_language": "or",
  "school_name": null
}
```

Response:

```json
{
  "board": "scert_odisha",
  "class_no": 8,
  "preferred_language": "or",
  "school_name": null,
  "onboarding_completed": true,
  "created_at": "2026-05-28T10:00:00Z",
  "updated_at": "2026-05-28T10:00:00Z"
}
```

### Usage

```http
GET /me/usage
```

Protected endpoint. Returns current LearnAssist usage without spending quota.

```json
{
  "date_ist": "2026-05-28",
  "used": 1,
  "limit": 3,
  "remaining": 2,
  "unlimited": false
}
```

### LearnAssist Chat

```http
POST /learnassist/chat
```

Protected endpoint. Requires:

```http
Authorization: Bearer <firebase_id_token>
```

Request:

```json
{
  "message": "କୋଷ କିଏ ଆବିଷ୍କାର କରିଥିଲେ?",
  "board": "scert_odisha",
  "class_no": 8,
  "channel": "science",
  "language": "or",
  "debug": true
}
```

Required fields:

```text
message
board
class_no
```

Optional fields:

```text
channel
language
debug
```

## Request Rules

- `message` must not be empty and must be at most 2000 characters.
- `board` must be `scert_odisha`.
- `class_no` must be 1 through 12.
- `channel` selects the conversation and its subject scope (single source of truth):
  - `"general"` (default if missing/empty): cross-subject "ask anything"; no subject filter.
  - a known subject (`science`, `maths`, `english`, `hindi`, `odia`, `sanskrit`,
    `social_science`): that subject only; retrieval is filtered to it.
  - any other value is rejected (422). There is **no** separate `subject` field — the
    server derives the subject from `channel`, so the two can never disagree.
- Memory is scoped per `(board, class_no, channel)`: each is its own conversation
  thread (`thread_id = learnassist:{uid}:{board}:{class_no}:{channel}`), so subjects
  never leak into each other and a class/board change starts fresh memory.
- `language` is optional and can guide the answer language.
- `debug` controls whether context blocks are returned.

Retrieval tuning stays server-side. The API should not accept `top_k`, `context_blocks`, chunk window, or max context chars in Release 1.

The API should not accept `user_id`, `email`, or `name` in the chat body. User identity comes only from the verified Firebase token.

## Success Response

When `debug=false` or missing:

```json
{
  "answer": "...",
  "citations": [
    {
      "label": "[1]",
      "book_name": "jigyasa",
      "source_pdf": "Science_Jigyasa.pdf",
      "page_no": 21,
      "score": 0.77,
      "chunk_ids": ["scert_odisha_class_8_science_jigyasa_p0021_c0001"]
    }
  ],
  "retrieval": {
    "tool_used": true,
    "query": "କୋଷ କିଏ ଆବିଷ୍କାର କରିଥିଲେ?",
    "board": "scert_odisha",
    "class_no": 8,
    "subject_filter": null,
    "subjects_found": ["science"],
    "pages_found": [1, 20, 21, 22, 23, 35, 49, 66],
    "top_score": 0.77,
    "context_block_count": 4
  },
  "usage": {
    "date_ist": "2026-05-28",
    "used": 1,
    "limit": 3,
    "remaining": 2,
    "unlimited": false
  }
}
```

When `debug=true`, include context blocks:

```json
{
  "answer": "...",
  "citations": [],
  "retrieval": {},
  "context_blocks": [
    {
      "score": 0.77,
      "board": "scert_odisha",
      "class": 8,
      "subject": "science",
      "book_name": "jigyasa",
      "book_id": "scert_odisha_class_8_science_jigyasa",
      "language": "or",
      "source_pdf": "Science_Jigyasa.pdf",
      "page_no": 21,
      "chunk_ids": ["..."],
      "text": "..."
    }
  ]
}
```

## Error Responses

Validation error:

```json
{
  "error": {
    "code": "bad_request",
    "message": "query cannot be empty."
  }
}
```

Service error:

```json
{
  "error": {
    "code": "service_error",
    "message": "Unable to process the request right now."
  }
}
```

Unauthorized:

```json
{
  "error": {
    "code": "unauthorized",
    "message": "Missing bearer token."
  }
}
```

Quota exceeded:

```json
{
  "error": {
    "code": "quota_exceeded",
    "message": "Daily LearnAssist quota exceeded.",
    "retry_at_ist": "2026-05-29T00:00:00+05:30"
  }
}
```

## Implementation Files

Current structure:

```text
src/vidyalaya_ai/
  main.py
  api/
    __init__.py
    app.py
    dependencies.py
    exceptions.py
    logging_config.py
    routers/
      __init__.py
      health.py
      learnassist.py
      auth.py
      me.py
    schemas/
      __init__.py
      common.py
      learnassist.py
      auth.py
      me.py
  auth/
    __init__.py
    config.py
    firebase.py
    models.py
  db/
  users/
  quota/
```

## Test Requests

Auth me:

```bash
curl "https://<domain>/auth/me" \
  -H "Authorization: Bearer <firebase_id_token>"
```

Subject provided:

```bash
curl -X POST "https://<domain>/learnassist/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <firebase_id_token>" \
  -d '{
    "message": "Who was Major Somnath Sharma?",
    "board": "scert_odisha",
    "class_no": 8,
    "subject": "english",
    "language": "en",
    "debug": true
  }'
```

Subject missing:

```json
{
  "message": "Who was Major Somnath Sharma?",
  "board": "scert_odisha",
  "class_no": 8,
  "debug": true
}
```

Odia query:

```json
{
  "message": "କୋଷ କିଏ ଆବିଷ୍କାର କରିଥିଲେ?",
  "board": "scert_odisha",
  "class_no": 8,
  "language": "or",
  "debug": true
}
```

Weak or general query:

```json
{
  "message": "How should I prepare for exams?",
  "board": "scert_odisha",
  "class_no": 8,
  "language": "en",
  "debug": true
}
```
