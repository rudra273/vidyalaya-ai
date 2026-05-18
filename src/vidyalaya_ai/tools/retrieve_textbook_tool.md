# Retrieve Textbook Tool Plan

## Purpose

`retrieve_textbook` is the main RAG tool used by agents when textbook context is needed.

It wraps the existing retrieval pipeline:

```text
query
-> query embedding
-> Qdrant search
-> merge/expand context
-> return context blocks + metadata
```

## Architecture Rule

Client/API owns trusted filters.

Tool owns retrieval tuning.

LLM/agent decides whether the tool is needed, but should not invent trusted filters when the client already provided them.

## Inputs

The tool should receive:

```python
def retrieve_textbook(
    query: str,
    board: str,
    class_no: int,
    subject: str | None = None,
) -> dict:
    ...
```

Input source:

```text
query -> client/API user message
board -> client/API or student profile
class_no -> client/API or student profile
subject -> client/API/session state, optional
```

If `subject=None`, the tool searches across all subjects for that board/class.

## Internal Tool Config

These should stay server-side in the tool, not controlled by the student client.

```python
top_k = 10
context_blocks = 4
neighbor_chunk_window = 1
neighbor_page_window = 0
max_context_chars = 6000
```

`preview_chars` is not part of the real tool. It is only for local debug scripts like `test.py`.

## Output

Return shape:

```json
{
  "context_blocks": [
    {
      "score": 0.75,
      "board": "scert_odisha",
      "class": 8,
      "subject": "english",
      "book_name": "Jasmine",
      "book_id": "scert_odisha_class_8_english_jasmine",
      "source_pdf": "English_Jasmine.pdf",
      "page_no": 69,
      "chunk_ids": ["..."],
      "text": "..."
    }
  ],
  "raw_hits": [
    {
      "score": 0.75,
      "subject": "english",
      "book_name": "Jasmine",
      "page_no": 69,
      "chunk_id": "..."
    }
  ],
  "metadata": {
    "query": "Who was Major Somnath Sharma?",
    "board": "scert_odisha",
    "class_no": 8,
    "subject_filter": null,
    "subjects_found": ["english"],
    "pages_found": [69, 70, 62],
    "top_score": 0.75,
    "context_block_count": 4
  }
}
```

## Tool Behavior

1. Validate query is not empty.
2. Validate board and class are present.
3. Use subject filter only if provided.
4. Retrieve raw top-k hits.
5. Build merged context blocks.
6. Collect metadata.
7. Return structured result.

## Logging

Log:

```text
query
board
class_no
subject filter
top score
subjects found
pages found
context block count
```

Do not log API keys or full student profile data.

## When Agents Should Use This Tool

Use when:

- new textbook question
- subject/topic changes
- citation needed but missing
- current conversation context is weak

Skip when:

- answer can be given from existing context
- student asks to simplify the previous answer
- student asks a follow-up already covered by current context

## Implementation Location

Suggested file:

```text
src/vidyalaya_ai/tools/retrieve_textbook.py
```

The tool should call:

```python
retrieve_chunks()
build_context_blocks()
```

It should not duplicate retrieval logic.

## MVP Test Cases

- subject provided: English question retrieves English only
- subject missing: English question finds English
- subject missing: Odia science question finds science
- no result or weak result returns structured empty/weak metadata
- output contains citations and raw hit metadata

