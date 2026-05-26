# Railway Deployment

## Purpose

Deploy only the FastAPI backend from this repository.

The repository can contain OCR, ingestion, and data folders, but Railway should start only:

```text
vidyalaya_ai.api.app:app
```

## Railway Settings

Build:

```text
Nixpacks
```

Start command:

```bash
PYTHONPATH=src uvicorn vidyalaya_ai.api.app:app --host 0.0.0.0 --port $PORT
```

The same command is already configured in:

```text
railway.toml
```

## Required Environment Variables

Set these in Railway Variables:

```text
QDRANT_URL=<your-qdrant-cloud-url>
QDRANT_API_KEY=<your-qdrant-cloud-api-key>
GEMINI_API_KEY=<your-gemini-api-key>
```

Optional:

```text
GOOGLE_API_KEY=<your-google-api-key>
```

If both `GOOGLE_API_KEY` and `GEMINI_API_KEY` are present, LangChain Google may prefer `GOOGLE_API_KEY`.

## Deploy Steps

1. Create a new Railway project.
2. Deploy from GitHub repository.
3. Confirm Railway detects Python/Nixpacks.
4. Confirm root `requirements.txt` is used.
5. Add required environment variables.
6. Deploy.
7. Open:

```text
https://<railway-domain>/health
```

Expected response:

```json
{
  "status": "ok",
  "service": "vidyalaya-ai"
}
```

## Test Request

```bash
curl -X POST "https://<railway-domain>/learnassist/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Who was Major Somnath Sharma?",
    "board": "scert_odisha",
    "class_no": 8,
    "subject": "english",
    "language": "en",
    "debug": false
  }'
```

## Notes

- Do not upload `.env` to GitHub.
- OCR/data files are not needed at runtime because retrieval uses Qdrant Cloud.
- Existing embedding files are only for rebuilding Qdrant Cloud if needed.
- Qdrant Cloud must already contain the uploaded collection before deployment testing.
