# RAG PIPELINE ARCHITECTURE AND MODEL SELECTION

## Architecture Plan

### 1. OCR Pipeline (Run locally, one-time per book)

- Take image-based PDFs (Odia, Hindi, Sanskrit books, 300-400 MB each)
- Process through Docling with Tesseract OCR engine (languages: ori+hin+san)
- Docling handles layout detection, reading order, table extraction, page tracking
- Output: clean markdown text with metadata (book name, page number, chapter) — about 1-3 MB per book

---

### 2. Indexing / Storage (Run once after OCR)

- An abstract `RAGBackend` interface with two implementations, switchable via a single config variable

#### Option A — Gemini File Search
- Upload the text files to Google's managed store
- Google auto-chunks, auto-embeds, auto-indexes
- Zero infra

#### Option B — Qdrant
- Chunk the text (500 tokens, 50 overlap)
- Embed each chunk using `gemini-embedding-2`
- Upsert vectors + metadata into Qdrant Cloud Free (4 GB disk free)

- Switching between A and B = change one config value + re-run the upload script

---

### 3. Server (Always running, lightweight)

- FastAPI app hosted on a $5 VPS or Google Cloud Run
- Single endpoint `POST /ask` — receives a question, returns an answer + citations
- Auth: simple API key check per request
- Rate limiting to control free-tier usage
- The server holds no ML models, no GPU — it's just an API gateway that calls the chosen RAG backend

---

### 4. Query Flow (What happens on every user question)

- Android app sends the question string to `POST /ask`
- Server passes query to the active backend:

#### If Gemini File Search
- One API call to `generateContent` with the FileSearch tool
- Returns answer + page citations automatically

#### If Qdrant
- Embed the query
- Search Qdrant for top 5 chunks
- Send chunks + query to Gemini Flash LLM
- Get answer

- Server returns JSON:

```json
{
  "answer": "...",
  "citations": [
    {"book": "Bhagavad Gita Odia", "page": 42},
    {"book": "Dharmapad", "page": 7}
  ]
}
```

---

### 5. Android App (Thin client)

- No AI logic, no API keys baked in, no book data
- Text input for questions, display area for answers
- Shows citations (book name + page number) under each answer
- Optional: query history, favorites, offline caching of past answers

---

### 6. Tech Stack

- OCR: Docling v2 + Tesseract 5 (ori+hin+san)
- Embedding: gemini-embedding-2 (free, 100+ languages, 3072 dims)
- RAG Option A: Gemini File Search (free tier, 1 GB storage, auto everything)
- RAG Option B: Qdrant Cloud Free (4 GB disk, hybrid search, open source)
- LLM: Gemini 3 Flash Preview (free tier)
- Server: FastAPI (Python, async)
- Mobile: Android, Kotlin + Retrofit

---

## Tools & Tech Stack

| Layer | Tool | Version | Why |
|---|---|---|---|
| OCR | Docling | v2.93 | Best PDF pipeline, layout detection |
| OCR Engine | Tesseract | v5.x | Free, supports ori+hin+san |
| Embedding | gemini-embedding-2 | Latest (Apr 2026) | Free tier, 100+ langs, 8K tokens |
| RAG Option A | Gemini File Search | Latest | Zero infra, auto-chunk, free storage |
| RAG Option B | Qdrant Cloud Free | v1.18 | 4 GB free, hybrid search, open-source |
| LLM | Gemini 3 Flash Preview | Latest | Free tier, fast, multilingual |
| Server | FastAPI | v0.115+ | Async, fast, Python |
| Auth | API key / JWT | — | Simple token auth for mobile |
| Hosting | Google Cloud Run / $5 VPS | — | Pay-per-request or fixed |
| Mobile | Android (Kotlin/Retrofit) | — | Thin HTTP client |

---

## Backend Switching

ONLY CHANGE:

1. Set config to `"qdrant"`
2. Re-run `admin/upload.py`
3. Done. Same API, same app.

---

## Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| OCR before upload | Yes | Saves 150x storage, faster search |
| Tesseract over EasyOCR | Tesseract | EasyOCR has no Odia support |
| Abstract RAG interface | Yes | Switch backends with 1 config change |
| Server required | Yes | API key safety, shared book store, cost control |
| Gemini as LLM for both backends | Yes | Free tier, best multilingual, consistent behavior |
| Chunking (Qdrant path) | 500 tokens, 50 overlap | Good for book paragraphs |
| Metadata on every chunk | book_name + page_no + chapter | For citations |

---

This is the complete plan. Say “implement” when you want me to write the code.
