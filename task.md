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
- Gemini SDK usage: embeddings only, never LLM answering or agent orchestration
- LLM/agent layer: use LangChain-compatible LLM calls and LangGraph later for orchestration so the answer model can change
- Client/API owns trusted filters: query, board, class_no, subject optional
- Tools own internal retrieval tuning: top_k, context blocks, neighbor expansion, max context chars
- Agents decide when tools are needed; agents should not blindly retrieve every turn

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
- [x] Then ingest all class 8 subjects.
- [ ] Later ingest class 9, class 10, and other classes into the same collection by changing config.
- [x] Re-running the same subject should update existing points, not duplicate them.

## Phase 8: Query Flow V1

- [x] Accept student query.
- [x] Accept filters: board, class, subject.
- [x] Embed query with Gemini Embedding 2 at 1536 dimensions.
- [x] Search Qdrant with top 10.
- [x] Return score, subject, book, page, chunk id, and text preview.
- [x] Keep Gemini SDK isolated to query embeddings only.

Query embedding text format:

```text
Represent this student question for retrieving relevant textbook passages.

<student query>
```

## Phase 9: Merge And Expand Context

- [x] Group top 10 hits by book_id and page_no.
- [x] For strong hits, fetch nearby chunks from the same page:
  - previous chunk
  - matched chunk
  - next chunk
- [x] Optionally fetch previous or next page only when needed.
- [x] Merge expanded chunks in page order.
- [x] Keep final context to 2-4 blocks.
- [x] Include citation metadata for each block.
- [x] Keep merge/expand behavior configurable.

Config knobs:

```python
final_context_blocks = 4
neighbor_chunk_window = 1
neighbor_page_window = 0
max_context_chars = 6000
dedupe_context_chunks = True
```

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

## Phase 10: Answer Generation Direction

- [x] Use LangChain-compatible LLM calls, not direct Gemini SDK.
- [x] Keep the final answer model configurable through the LLM provider layer.
- [x] Do not keep answer prompts or system prompts in the `llm/` folder.
- [x] Let agents own final answer behavior, citation rules, and fallback wording.
- [x] Keep Gemini SDK usage limited to embeddings only.

## Phase 11: Basic Evaluation

- [x] Create 10-20 test questions from class 8 books.
- [x] Track whether top 10 contains the correct page.
- [x] Track whether final 2-4 context blocks are useful.
- [x] Track bad cases:
  - wrong subject
  - right subject but wrong chapter/page
  - OCR text issue
  - chunk too small
  - chunk too large
- [x] Tune chunk size and overlap only after checking failures.

Latest basic evaluation:

```text
Report: reports/rag_eval_class8.jsonl
Total cases: 14
Top-10 expected page pass: 14/14
Final context expected page pass: 14/14
Failed cases: 0
```

## Phase 12: Retrieve Textbook Tool

- [x] Create `src/vidyalaya_ai/tools/retrieve_textbook.py`.
- [x] Create a small config object for server-side tool tuning:
  - top_k
  - context_blocks
  - neighbor_chunk_window
  - neighbor_page_window
  - max_context_chars
- [x] Implement `retrieve_textbook(query, board, class_no, subject=None)`.
- [x] Use client/API-provided board, class, and optional subject.
- [x] Do not let student/client control internal retrieval tuning in MVP.
- [x] Call existing `retrieve_chunks()` and `build_context_blocks()`.
- [x] Return context blocks, raw hits, and metadata.
- [x] Include subjects found, pages found, top score, and context block count.
- [x] Add logging.
- [x] Add a simple local test for:
  - subject provided
  - subject missing
  - cross-subject retrieval

## Phase 13: LLM Provider Setup

- [x] Remove generic answer/prompt code from the LLM folder.
- [x] Create `src/vidyalaya_ai/llm/config.py`.
- [x] Create `src/vidyalaya_ai/llm/factory.py`.
- [x] Create provider module `src/vidyalaya_ai/llm/providers/google.py`.
- [x] Keep provider/model/temperature/max tokens configurable.
- [x] Return LangChain-compatible chat model objects.
- [x] Do not place agent prompts in the LLM folder.
- [x] Keep Gemini SDK out of answer generation.
- [x] Support at least one provider first, then add more later.

## Phase 14: LearnAssist Agent

- [x] Rename backend concept from Doubt Solver to LearnAssist.
- [x] Create LearnAssist agent implementation.
- [x] Agent receives query and client/API filters from state.
- [x] Agent decides whether `retrieve_textbook` is needed.
- [x] Agent reuses existing conversation context when enough.
- [x] Agent calls `retrieve_textbook` for new textbook questions.
- [x] Agent builds its own prompt/messages and calls the configured LLM.
- [x] Agent returns answer, citations, and retrieval metadata.
- [x] Keep implementation simple before adding LangGraph complexity.

## Phase 15: Release 1 API Design

- [x] Design one LearnAssist chat endpoint for Postman testing.
- [x] Keep the API request close to the agent input:
  - query
  - board
  - class_no
  - subject optional
  - language optional
- [x] Keep retrieval tuning server-side.
- [x] Define response shape with:
  - answer
  - citations
  - retrieval metadata
  - optional context blocks for debugging
- [x] Decide error response shape for bad input and service failures.

## Phase 16: Release 1 API Implementation

- [x] Add FastAPI app under `src/vidyalaya_ai/api`.
- [x] Add request/response schemas.
- [x] Add `/health` endpoint.
- [x] Add `/learnassist/chat` endpoint.
- [x] Wire endpoint to `answer_with_learnassist()`.
- [x] Add API logging.
- [x] Add local run command for development:
  ```bash
  PYTHONPATH=src .venv/bin/uvicorn vidyalaya_ai.api.app:app --reload --port 8000
  ```

## Phase 17: Postman Validation

- [ ] Start local API server.
- [ ] Test `/health`.
- [ ] Test LearnAssist with subject provided.
- [ ] Test LearnAssist with subject missing.
- [ ] Test Odia query.
- [ ] Test weak/unknown query.
- [ ] Save working Postman examples or curl commands.

## Later Improvements

- [ ] Add reranking only if top 10 has good candidates but final answers are noisy.
- [ ] Add hybrid sparse+dense search if exact Odia terms or names are missed.
- [ ] Add chapter metadata later if chapter detection becomes available.
- [ ] Move from local Qdrant to Qdrant Cloud after local ingestion is stable.
- [ ] Add image/page references later for multimodal retrieval.
- [ ] Build Tutor Agent after LearnAssist release 1 is stable.
- [ ] Add voice interaction for Tutor Agent.
