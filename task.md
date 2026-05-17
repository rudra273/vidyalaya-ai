# RAG Ingestion Tasks

Goal: build the first production-ready ingestion and query flow for OCR textbook JSONL files using Qdrant and Gemini Embedding 2.

## Fixed Decisions

- Vector DB: Qdrant
- Embedding model: Gemini Embedding 2 (`gemini-embedding-2`)
- Embedding dimension: 1536
- Input source: OCR JSONL files
- Main filters: board, class, subject
- Retrieval V1: Qdrant top 10
- Reranker V1: skip
- Context strategy: merge and expand nearby chunks before sending to the LLM
- Ingestion style: staged by board, class, and subject as books become ready
- Point IDs: deterministic, never random, so repeated ingestion can safely update existing chunks

## Current Input Format

Each JSONL row should contain:

```json
{
  "board": "scert_odisha",
  "class": 8,
  "subject": "english",
  "book_name": "Jasmine",
  "book_id": "scert_odisha_class_8_english_jasmine",
  "language": "en",
  "source_pdf": "English_Jasmine.pdf",
  "page_no": 1,
  "text": "..."
}
```

## Phase 1: Local Qdrant Check

- [x] Start local Qdrant with Docker Compose.
- [x] Confirm Qdrant dashboard opens at `http://localhost:6333/dashboard`.
- [x] Confirm API is reachable at `http://localhost:6333`.
- [x] Create one small test collection.
- [x] Insert one test point with a fake 1536-dim vector and metadata.
- [x] Query that one test point.
- [x] Delete the test collection.

## Phase 2: Ingestion Folder Structure

- [x] Create ingestion code folder.
- [x] Add a config section for local paths, model name, embedding dimension, Qdrant URL, and collection name.
- [x] Add environment loading for `GEMINI_API_KEY`.
- [x] Keep the code simple and runnable from one main file.
- [x] Keep board, class, and subject configurable for staged ingestion.

Suggested files:

```text
ingestion/
  loader.py
  chunk.py
  embed.py
  qdrant_store.py
  main.py
  query.py
```

## Phase 3: JSONL Loader

- [x] Read one JSONL file from `data/processed/ocr/scert_odisha/class_8/jsonl`.
- [x] Validate required fields.
- [x] Skip empty pages.
- [x] Print count of pages loaded.
- [x] Do not modify OCR output files.

## Phase 4: Chunking

- [x] Implement page-aware chunking.
- [x] Split text by paragraph/newline first.
- [x] Fall back to line or character splitting only when a block is too large.
- [x] Keep chunks inside one page.
- [x] Target chunk size: 1500-2200 characters.
- [x] Hard max chunk size: 3000 characters.
- [x] Overlap: 250-400 characters.
- [x] Merge very small chunks below 300-500 characters when possible.
- [x] Store chunk metadata.

Each chunk should contain:

```json
{
  "chunk_id": "scert_odisha_class_8_english_jasmine_p0001_c0001",
  "board": "scert_odisha",
  "class": 8,
  "subject": "english",
  "book_name": "Jasmine",
  "book_id": "scert_odisha_class_8_english_jasmine",
  "language": "en",
  "source_pdf": "English_Jasmine.pdf",
  "page_no": 1,
  "chunk_index": 1,
  "text": "..."
}
```

## Phase 5: Gemini Embeddings

- [x] Install and configure Gemini SDK.
- [x] Implement document chunk embedding with Gemini Embedding 2.
- [x] Use 1536 output dimensions.
- [x] Add a document instruction before chunk text.
- [x] Batch requests where possible.
- [x] Save progress locally so ingestion can resume if interrupted.
- [x] Print progress logs while embedding.

Document embedding text format:

```text
Represent this textbook passage for retrieval.

Board: scert_odisha
Class: 8
Subject: english
Book: Jasmine
Page: 1

<chunk text>
```

## Phase 6: Qdrant Collection

- [x] Create Qdrant collection with vector size 1536 and cosine distance.
- [x] Add payload indexes for common filters:
  - board
  - class
  - subject
  - book_id
  - page_no
- [x] Use deterministic point IDs from chunk IDs, not random UUIDs.
- [x] Upsert chunks with vectors and payload.
- [x] Store text inside payload for V1.
- [x] Print inserted point count.

## Phase 7: First Real Ingestion

- [x] Ingest one subject JSONL first.
- [x] Check collection count.
- [x] Query using board, class, and subject filters.
- [x] Inspect top 10 results manually.
- [x] Confirm page numbers and text look correct.
- [ ] Then ingest all class 8 subjects.
- [ ] Later ingest class 9, class 10, and other classes into the same collection by changing config.
- [x] Re-running the same subject should update existing points, not duplicate them.

## Phase 8: Query Flow V1

- [ ] Accept student query.
- [ ] Accept filters: board, class, subject.
- [ ] Embed query with Gemini Embedding 2 at 1536 dimensions.
- [ ] Search Qdrant with top 10.
- [ ] Return score, subject, book, page, chunk id, and text preview.

Query embedding text format:

```text
Represent this student question for retrieving relevant textbook passages.

<student query>
```

## Phase 9: Merge And Expand Context

- [ ] Group top 10 hits by book_id and page_no.
- [ ] For strong hits, fetch nearby chunks from the same page:
  - previous chunk
  - matched chunk
  - next chunk
- [ ] Optionally fetch previous or next page only when needed.
- [ ] Merge expanded chunks in page order.
- [ ] Keep final context to 2-4 blocks.
- [ ] Include citation metadata for each block.

Final context block shape:

```json
{
  "book_name": "Jasmine",
  "source_pdf": "English_Jasmine.pdf",
  "page_no": 12,
  "score": 0.81,
  "text": "..."
}
```

## Phase 10: Answer Generation

- [ ] Send student query and 2-4 context blocks to the LLM.
- [ ] Tell the LLM to answer only from the provided context.
- [ ] Ask it to include book/page citation.
- [ ] If context is weak, say the answer was not found clearly.

## Phase 11: Basic Evaluation

- [ ] Create 20-30 test questions from class 8 books.
- [ ] Track whether top 10 contains the correct page.
- [ ] Track whether final 2-4 context blocks are useful.
- [ ] Track bad cases:
  - wrong subject
  - right subject but wrong chapter/page
  - OCR text issue
  - chunk too small
  - chunk too large
- [ ] Tune chunk size and overlap only after checking failures.

## Later Improvements

- [ ] Add reranking only if top 10 has good candidates but final answers are noisy.
- [ ] Add hybrid sparse+dense search if exact Odia terms or names are missed.
- [ ] Add chapter metadata later if chapter detection becomes available.
- [ ] Move from local Qdrant to Qdrant Cloud after local ingestion is stable.
- [ ] Add image/page references later for multimodal retrieval.
