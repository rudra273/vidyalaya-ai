# Tutor Agent Plan

## Purpose

The Tutor Agent teaches a subject like an offline tutor.

This is not a generic Q&A agent. It should guide the student through a subject/book step by step, check understanding, and track progress.

## Student Experience

The student starts a learning session:

```text
I want to learn class 8 science.
Start maths from the beginning.
ଆଜି social science ପଢ଼ିବା।
```

The agent should behave like a patient tutor:

- start from the selected subject
- teach one small topic at a time
- explain with examples
- ask simple check questions
- give hints if the student is wrong
- revise before moving forward
- remember where the student stopped

## Inputs

Minimum input:

```json
{
  "student_id": "optional-later",
  "board": "scert_odisha",
  "class_no": 8,
  "subject": "science"
}
```

During chat:

```json
{
  "message": "I understood this. Continue."
}
```

## Outputs

Session response shape:

```json
{
  "message": "...",
  "current_subject": "science",
  "current_topic": "Cells",
  "current_page_refs": [21, 22],
  "student_state": "learning",
  "next_action": "ask_check_question"
}
```

## MVP Teaching Flow

1. Student selects board, class, and subject.
2. Agent starts with the first available textbook section or selected topic.
3. Agent retrieves relevant context.
4. Agent explains a small part.
5. Agent asks one check question.
6. Student replies.
7. Agent gives feedback.
8. Agent either revises or continues.

## Teaching Style

The agent should:

- use simple language
- adapt to the student's language
- prefer examples from the textbook
- keep explanations short
- ask interactive questions
- encourage but not overpraise
- avoid dumping full chapter text

## Progress Tracking

Eventually store:

```json
{
  "student_id": "...",
  "board": "scert_odisha",
  "class_no": 8,
  "subject": "science",
  "current_book_id": "...",
  "current_page_no": 21,
  "current_topic": "Cells",
  "completed_topics": [],
  "weak_topics": [],
  "last_session_at": "..."
}
```

For MVP, this can be in memory or a simple database table later.

## Required Capabilities

### Teach Topic

Explain the current topic using textbook context.

### Ask Check Question

Ask a small question after teaching.

### Evaluate Student Reply

Check whether the student understood.

### Hint Mode

If the student is wrong, give a hint before giving the answer.

### Continue Mode

Move to the next part only after the student is ready.

## Difference From LearnAssist Agent

| Agent | Main Job |
|---|---|
| LearnAssist Agent | Answer one study question |
| Tutor Agent | Teach a subject over time |

## What It Should Not Do In MVP

- no full syllabus planner yet
- no exam prediction
- no parent dashboard
- no complicated chapter parser
- no one-agent-per-subject split

## Later Improvements

- chapter/topic map generation
- long-term student memory
- adaptive revision
- mastery score
- spaced repetition
- homework mode
- teacher dashboard
- voice tutoring

## Future Voice Interaction

Voice interaction should be available later for the Tutor Agent.

Future flow:

```text
student speaks
-> speech-to-text
-> Tutor Agent understands the message
-> agent responds
-> text-to-speech reads the explanation aloud
```

Voice mode should support:

- student asking doubts by speaking
- tutor explaining aloud
- follow-up questions
- pronunciation-friendly pacing
- Odia/Hindi/English support when possible
- fallback to text when voice fails

This is not part of MVP implementation, but the Tutor Agent should be designed so voice can be added without changing the core teaching flow.
