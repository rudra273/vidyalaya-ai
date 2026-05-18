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
- answer normally if textbook context is missing or not useful
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
4. Build LearnAssist prompt/messages inside the agent.
5. Call the configured LangChain-compatible LLM.
6. Return answer, citations, and basic retrieval metadata.

## Prompt Behavior

The agent prompt should instruct:

- answer only from provided textbook context when context is used
- use general knowledge when context is missing or not useful
- cite context labels like `[1]`, `[2]` only when textbook context is used
- if context is weak, still answer normally without forcing textbook citations
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

- still let the LLM answer normally
- avoid citation labels unless context was actually used
- keep retrieval metadata so we can debug later

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
