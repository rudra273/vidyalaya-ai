# Release 1 API Plan

## Purpose

Release 1 exposes only the LearnAssist agent through a small FastAPI API.

The goal is to test the full flow in Postman:

```text
client request
-> FastAPI endpoint
-> LearnAssist agent
-> retrieve_textbook tool
-> LLM
-> answer + citations + retrieval metadata
```

Tutor Agent is future work and should not be included in Release 1.

## Endpoints

### Health

```http
GET /health
```

Response:

```json
{
  "status": "ok",
  "service": "vidyalaya-ai"
}
```

### LearnAssist Chat

```http
POST /learnassist/chat
```

Request:

```json
{
  "query": "କୋଷ କିଏ ଆବିଷ୍କାର କରିଥିଲେ?",
  "board": "scert_odisha",
  "class_no": 8,
  "subject": null,
  "language": "or",
  "debug": true
}
```

Required fields:

```text
query
board
class_no
```

Optional fields:

```text
subject
language
debug
```

## Request Rules

- `query` must not be empty.
- `board` must not be empty.
- `class_no` must be a positive integer.
- `subject` is optional. If missing or null, retrieval searches across subjects for the class.
- `language` is optional and can guide the answer language.
- `debug` controls whether context blocks are returned.

Retrieval tuning stays server-side. The API should not accept `top_k`, `context_blocks`, chunk window, or max context chars in Release 1.

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

## Implementation Files

Suggested structure:

```text
src/vidyalaya_ai/api/
  __init__.py
  app.py
  schemas.py
  logging_config.py
```

## Postman Test Requests

Subject provided:

```json
{
  "query": "Who was Major Somnath Sharma?",
  "board": "scert_odisha",
  "class_no": 8,
  "subject": "english",
  "language": "en",
  "debug": true
}
```

Subject missing:

```json
{
  "query": "Who was Major Somnath Sharma?",
  "board": "scert_odisha",
  "class_no": 8,
  "debug": true
}
```

Odia query:

```json
{
  "query": "କୋଷ କିଏ ଆବିଷ୍କାର କରିଥିଲେ?",
  "board": "scert_odisha",
  "class_no": 8,
  "language": "or",
  "debug": true
}
```

Weak or general query:

```json
{
  "query": "How should I prepare for exams?",
  "board": "scert_odisha",
  "class_no": 8,
  "language": "en",
  "debug": true
}
```
