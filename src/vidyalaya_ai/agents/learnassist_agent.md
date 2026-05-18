# LearnAssist Agent Plan

## Purpose

The LearnAssist Agent answers a student's direct study question using textbook RAG.

This is the first agent to build because the current RAG pipeline already supports it:

```text
student query
-> retrieve_textbook tool when needed
-> context blocks
-> LLM answer with citations
```

## Student Experience

The student can ask any textbook-related question:

```text
Who was Major Somnath Sharma?
କୋଷ କିଏ ଆବିଷ୍କାର କରିଥିଲେ?
What are quadrilaterals?
ଭାରତର ନିର୍ବାଚନ ବ୍ୟବସ୍ଥା କଣ?
```

The agent should:

- answer simply
- use textbook context when the question needs textbook grounding
- cite book/page when textbook context is used
- explain step by step when useful
- say clearly when the answer is not found in the available context
- avoid pretending if retrieval is weak
- reuse existing conversation context when enough context is already available

## Inputs From Client/API

The app/client owns trusted filters.

Minimum input:

```json
{
  "query": "Who was Major Somnath Sharma?",
  "board": "scert_odisha",
  "class_no": 8
}
```

Optional filters:

```json
{
  "subject": "english",
  "language": "en"
}
```

Subject can be optional. If not provided, the `retrieve_textbook` tool can search across all subjects for the selected class.

## Tool Use Rule

The agent should decide whether textbook retrieval is needed.

Call `retrieve_textbook` when:

- the student asks a new factual/textbook question
- the current conversation does not already contain enough context
- the student switches topic or subject
- the student asks for citations/page references and current context is missing them

Do not call `retrieve_textbook` when:

- the student asks to re-explain the immediately previous answer
- the student asks "what page was that from?" and citations are already in memory
- the student asks a follow-up that can be answered from existing context

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
    "tool_used": true,
    "subject_filter": null,
    "subjects_found": ["english"],
    "top_score": 0.75,
    "context_block_count": 4
  }
}
```

## MVP Flow

1. Receive student query and client/API filters.
2. Decide whether current conversation context is enough.
3. If needed, call `retrieve_textbook`.
4. Pass query + context to the generic LLM answer function.
5. Return answer, citations, and basic retrieval metadata.

## Prompt Behavior

The agent prompt should instruct:

- answer only from provided textbook context when context is used
- do not use outside knowledge for textbook-grounded answers
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

## Tool Contract

The agent should not own retrieval tuning.

Client/API provides:

```text
query
board
class_no
subject optional
```

The tool owns:

```text
top_k
context block count
neighbor expansion
max context chars
```

## Edge Cases

### Subject Missing

If subject is missing:

- call `retrieve_textbook` with `subject=None`
- search across all subjects for the class
- include found subjects in metadata

### Weak Retrieval

If top score is weak or context is unrelated:

- do not hallucinate
- say the answer was not found clearly
- suggest selecting a subject or rephrasing the query

### Mixed Results

If top results come from multiple subjects:

- prefer the strongest context blocks
- mention uncertainty only if needed

## Later Improvements

- reranking
- query rewriting
- subject inference helper
- follow-up suggestions
- short answer / detailed answer mode
- citation links to page images

