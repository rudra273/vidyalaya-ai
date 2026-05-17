# Doubt Solver Agent Plan

## Purpose

The Doubt Solver Agent answers a student's direct question using textbook RAG.

This is the first agent to build because the current RAG pipeline already supports it:

```text
student query
-> query embedding
-> Qdrant retrieval
-> merge/expand context
-> LLM answer with citations
```

## Student Experience

The student can ask any textbook-related doubt:

```text
Who was Major Somnath Sharma?
କୋଷ କିଏ ଆବିଷ୍କାର କରିଥିଲେ?
What are quadrilaterals?
ଭାରତର ନିର୍ବାଚନ ବ୍ୟବସ୍ଥା କଣ?
```

The agent should:

- answer simply
- use textbook context only
- cite book/page
- explain step by step when useful
- say clearly when the answer is not found in the available context
- avoid pretending if retrieval is weak

## Inputs

Minimum input:

```json
{
  "query": "Who was Major Somnath Sharma?",
  "class_no": 8
}
```

Optional filters:

```json
{
  "board": "scert_odisha",
  "subject": "english",
  "language": "en"
}
```

Subject can be optional. If not provided, retrieval can search across all subjects for the selected class.

## Outputs

Response shape:

```json
{
  "answer": "...",
  "citations": [
    {
      "book_name": "Jasmine",
      "source_pdf": "English_Jasmine.pdf",
      "page_no": 69,
      "score": 0.75
    }
  ],
  "retrieval": {
    "subject_used": "english",
    "top_score": 0.75,
    "context_block_count": 4
  }
}
```

## MVP Flow

1. Receive student query and optional filters.
2. Retrieve top chunks from Qdrant.
3. Build 2-4 merged context blocks.
4. Pass query + context to the LLM answer function.
5. Return answer, citations, and basic retrieval metadata.

## Prompt Behavior

The agent prompt should instruct:

- answer only from provided textbook context
- do not use outside knowledge
- cite context labels like `[1]`, `[2]`
- if context is weak, say the answer was not found clearly
- use the student's language when possible
- keep the answer understandable for school students

## What It Should Not Do In MVP

- no long tutoring journey
- no progress tracking
- no worksheet generation
- no answer grading
- no parent/teacher analytics
- no multi-agent routing

## RAG Config Defaults

```python
top_k = 10
final_context_blocks = 4
neighbor_chunk_window = 1
neighbor_page_window = 0
max_context_chars = 6000
```

## Edge Cases

### Subject Missing

If subject is missing:

- search across all subjects for the class
- infer the most likely subject from retrieved results
- include the selected subject in metadata

### Weak Retrieval

If top score is weak or context is unrelated:

- do not hallucinate
- say the answer was not found clearly
- suggest selecting a subject or rephrasing the query

### Mixed Results

If top results come from multiple subjects:

- prefer the strongest cluster
- mention uncertainty only if needed

## Later Improvements

- reranking
- query rewriting
- subject inference helper
- follow-up suggestions
- short answer / detailed answer mode
- citation links to page images

