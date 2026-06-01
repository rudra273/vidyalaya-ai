# Vidyalaya AI — Implementation Plan

---

## Feature 1: Multi-Step Retrieval (Suchipatra → Chapter Flow)

### The Problem

Student asks: "explain first chapter" or "pehla chapter kya hai"

Today the agent does one thing: call `search_textbook` once with the student's
raw message. That one call returns random pages that loosely match — not the
chapter content. The agent has no way to discover *what* the first chapter is
before retrieving it.

What we actually want:

```
Step 1: Student asks → agent retrieves the suchipatra (table of contents)
Step 2: Agent reads the TOC, knows Chapter 1 = "Kabir Das ke Dohe" (pages 13-18)
Step 3: Agent asks student: "Do you want to learn about Chapter 1: Kabir Das ke Dohe?"
Step 4: Student says yes → agent retrieves pages 13-18 with the actual chapter name
Step 5: Agent gives a proper answer with citations
```

This is 2 retrieval calls per turn when needed. The LangGraph ReAct loop
already supports this — the agent can call `search_textbook` multiple times
in one turn. The infrastructure is there.

---

### Key Bug to Fix First: tools.py line 52-53

The current `search_textbook` tool **ignores** the LLM's `query` argument
and always substitutes the raw student message:

```python
# tools.py line 52-53 (current — this is the bug)
student_query = _latest_student_message(runtime) or query
```

This was added with the intent that "Odia stays Odia" — but it breaks
multi-step retrieval entirely. If the LLM's second call is
`search_textbook(query="Kabir Das ke Dohe pages 13 to 18")`, the tool ignores
that and searches for "pehla chapter kya hai" again. Same result, infinite loop.

**Fix:** Remove the override. Trust the LLM's generated query.
This is also what unlocks the Feature 2 (language intelligence) — the LLM
generates the right native-script query and passes it; the tool must use it.

```python
# tools.py after fix
result = retrieve_textbook(query=query, board=ctx.board, ...)
```

---

### Suchipatra: Where Is It in the DB?

Every SCERT book has a table of contents (suchipatra / विषय-सूची / ସୂଚୀପତ୍ର)
in the first ~5-15 pages. It is already chunked and stored in Qdrant as
regular text chunks (page 1-15 range typically).

We do NOT need a separate tool or Postgres table. The agent can retrieve
the TOC by querying for it:

- Odia: `search_textbook(query="ସୂଚୀପତ୍ର", ...)`
- Hindi: `search_textbook(query="विषय-सूची", ...)`
- English: `search_textbook(query="table of contents", ...)`

The returned chunk will list chapters + page numbers. The LLM reads it
and uses those page numbers in the next retrieval call.

---

### Full Multi-Step Flow Design

```
Student: "pehla chapter samjhao" (Roman Hindi → "explain first chapter")

Turn starts → ReAct loop

LLM step 1 — reasoning:
  "Student wants chapter 1. I don't know what chapter 1 is in this book.
   I should check the table of contents first."

Tool call 1: search_textbook(query="विषय-सूची अध्याय")
  → returns chunk with: "अध्याय 1: कबीर दास के दोहे ... पृष्ठ 13"
                        "अध्याय 2: मेरी कुटिया ... पृष्ठ 19"
                        ...

LLM step 2 — reasoning:
  "Chapter 1 is 'Kabir Das ke Dohe', pages 13-18.
   I should confirm with the student before retrieving."

LLM responds to student (NO second tool call yet):
  "Chapter 1 is: Kabir Das ke Dohe (pages 13-18). Shall I explain it?"

--- next student turn ---

Student: "haan" / "yes" / "ha batao"

LLM step 3 — reasoning:
  "Student confirmed. Now retrieve the actual chapter content."

Tool call 2: search_textbook(query="कबीर दास के दोहे गुरु गोविंद")
  → returns pages 13-18 content

LLM step 4: synthesizes full answer with citations [1][2][3]
```

This gives the student a natural, guided experience — not a dump of random pages.

---

### When NOT to Do the Two-Step

The agent should NOT do suchipatra lookup if:
- The student asks about a specific concept (not a chapter): "what is a doha?"
- The student names the content directly: "explain kabir das ke dohe"
- The subject context already makes it obvious (page range known from prior turn)

This is controlled via the system prompt — the LLM decides when to look up TOC first.

---

### Implementation Steps for Feature 1

**Step 1: Fix tools.py** — remove the student_query override (line 52-53).
Use the LLM's `query` argument directly. This is the only code change needed.

**Step 2: Update the system prompt** (prompt.py `SYSTEM_PROMPT`) with rules:

> MULTI-STEP RETRIEVAL:
> - When a student asks about a chapter by number ("first chapter", "chapter 2"),
>   first search for the table of contents using the word "सूचीपत्र" (Hindi),
>   "ସୂଚୀପତ୍ର" (Odia), or "table of contents" (English) for the subject.
> - Read the TOC result to find the chapter name and page range.
> - Then confirm with the student: "Chapter 1 is [name]. Shall I explain it?"
> - Only after confirmation, do a second search_textbook call with the chapter name
>   as the query to retrieve the actual content.
>
> QUERY GENERATION (for ALL tool calls):
> - Generate a focused retrieval query in the native script of the textbook.
> - If the student wrote in Roman script (e.g. "kabir das"), convert to the
>   textbook's script (Hindi → Devanagari: "कबीर दास", Odia → Odia script).
> - Never pass the student's raw Roman-script message as the query.

**Step 3: Update tool docstring** (tools.py `search_textbook`):

> `query`: A focused search query in the native script of the textbook language.
> For Odia books use Odia script, for Hindi use Devanagari, for English use English.
> The agent generates this query — do not pass the student's raw message.
> You may call this tool more than once per turn (e.g. first for TOC, then for content).

**Step 4: No changes to retrieval.py, query_embedding.py, or runner.py.**
The multi-call behavior is already supported by the ReAct loop.

---

### Runner Change: Handle Multiple Tool Calls Per Turn

Currently `_retrieval_from_current_turn` in runner.py only reads the
**last** ToolMessage. With two calls per turn, we want citations from
both retrievals. Update it to collect context_blocks from ALL
search_textbook ToolMessages in the current turn (merged, deduped by chunk_id).

---

## Feature 2: Query Language Intelligence (Multilingual Retrieval)

### Background — Research & Test Results (2026-06-01)

We tested `gemini-embedding-2` (1536-dim) against Class 8 SCERT Odisha books
with native-language queries vs. English translations of the same query.

**Results:**

| Subject | Native query top-1 score | English translation top-1 score | Delta  | Winner |
|---------|--------------------------|----------------------------------|--------|--------|
| Odia    | 0.7751                   | 0.7395                           | +0.036 | Native |
| Hindi   | 0.7398                   | 0.7074                           | +0.032 | Native |
| English | 0.7464                   | —                                | —      | Native |

**Key findings:**
- Native-script queries score 0.03–0.04 higher than English translations
- Native queries rank pages better (Hindi: actual poem page ranked #1 vs. exercise page #1 for English)
- Gemini Embedding 2 handles Odia and Hindi script natively
- Translating to English loses exact-match signal
- Research confirms: monolingual retrieval > cross-lingual retrieval for Indic languages

**Conclusion:** Always query Qdrant in the textbook's native script.

### The Real Problem — Students Write in Roman Script

Students write like:
- Hindi: `guru ka matlab kya hai`, `pehla chapter batao`
- Odia: `birakishore das ke bare me batao`

This is Romanized text — not English, not native script. Embedding it gives
worse results than either, because it sits in a no-man's-land.

### Plan: LLM Generates the Query (Both Features Share This Fix)

The tools.py fix in Feature 1 (trust the LLM's query argument) enables this too.
The system prompt update tells the LLM to always generate native-script queries.

Both features are unlocked by the same two changes: fix tools.py + update the prompt.

---

## Implementation Order

1. **Fix tools.py** — remove student_query override (1 line change, critical)
2. **Update SYSTEM_PROMPT** — add multi-step retrieval + query generation rules
3. **Update search_textbook docstring** — tell the LLM what to pass
4. **Update runner.py** — merge context_blocks from multiple tool calls per turn
5. **Test** — run scripts/multilang_retrieval_test.py + manual chat test with
   "pehla chapter samjhao" in Hindi Kalika

---

## Future Considerations

- `get_subjects(board, class)` tool — useful if student hasn't selected a subject
- `get_chapters(board, class, subject)` tool backed by Postgres/config — faster than
  searching TOC from Qdrant every time, but TOC retrieval works for now
- Sanskrit: same pattern — Devanagari script for retrieval
- Subject-language map: `{odia: "or", hindi: "hi", english: "en", sanskrit: "sa"}`
  injected into context so LLM knows target script without guessing


30 min inactive checkpointer. 

if the user is not active for 30 mins .. clearn the checkpointer 