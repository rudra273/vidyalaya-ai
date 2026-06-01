"""
Multilingual retrieval test: compare native-language vs English query retrieval.

Tests three subjects from Class 8 SCERT books:
  - Odia textbook (Odia query vs English translation)
  - Hindi textbook (Hindi query vs English translation)
  - English textbook (English query directly)

Prints similarity scores for top-k results and highlights which pages are retrieved.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dotenv import load_dotenv
load_dotenv()

from vidyalaya_ai.rag.retrieval import retrieve_chunks
from vidyalaya_ai.rag.config import RagConfig

# ── Config ──────────────────────────────────────────────────────────────────
BOARD = "scert_odisha"
CLASS_NO = 8
TOP_K = 8

config = RagConfig(top_k=TOP_K)

# ── Test cases ───────────────────────────────────────────────────────────────
# Each entry: (label, query, subject, expected_pages)
TEST_CASES = [
    # Odia subject — native Odia query
    (
        "ODIA  | Native (Odia query)",
        "ଓଡିଆ ସାହିତ୍ୟରେ କବି ବୀରକିଶୋର ଦାସ 'ଜାତୀୟ କବି' ଭାବରେ ପରିଚିତ",
        "odia",
        list(range(17, 24)),
    ),
    # Odia subject — English translation of the same query
    (
        "ODIA  | English translation",
        "Poet Birakishore Das is known as 'National Poet' in Odia literature",
        "odia",
        list(range(17, 24)),
    ),

    # Hindi subject — native Hindi query
    (
        "HINDI | Native (Hindi query)",
        "गुरु गोविंद दोऊ खड़े, काके लागौं पाँय।",
        "hindi",
        list(range(13, 17)),
    ),
    # Hindi subject — English translation
    (
        "HINDI | English translation",
        "If both the Guru and Govind stand before me, whose feet shall I touch first?",
        "hindi",
        list(range(13, 17)),
    ),

    # English subject — direct English query
    (
        "ENGLISH | Native (English query)",
        "Once Shiva and Parvati held a competition between their sons Ganesh and Kartikeya.",
        "english",
        list(range(13, 25)),
    ),
]


def page_hit(chunk: dict, expected_pages: list[int]) -> bool:
    return chunk.get("page_no") in expected_pages


def run_test(label: str, query: str, subject: str, expected_pages: list[int]) -> None:
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"  Subject filter : {subject}")
    print(f"  Expected pages : {expected_pages}")
    print(f"  Query          : {query[:80]}{'…' if len(query) > 80 else ''}")
    print(f"{'='*70}")

    chunks = retrieve_chunks(
        query,
        board=BOARD,
        class_no=CLASS_NO,
        subject=subject,
        top_k=TOP_K,
        config=config,
    )

    if not chunks:
        print("  !! No chunks returned !!")
        return

    hits = 0
    for i, c in enumerate(chunks, 1):
        is_hit = page_hit(c, expected_pages)
        marker = "✓" if is_hit else " "
        hits += int(is_hit)
        print(
            f"  [{marker}] #{i:02d}  score={c['score']:.4f}  "
            f"page={c['page_no']:>4}  subject={c['subject']}  "
            f"text={c['text'][:60].replace(chr(10),' ')}…"
        )

    top_score = chunks[0]["score"] if chunks else 0
    top_hit = page_hit(chunks[0], expected_pages) if chunks else False
    print(f"\n  Summary: top_score={top_score:.4f}  top_page_hit={'YES' if top_hit else 'NO'}  "
          f"hits_in_top{TOP_K}={hits}/{TOP_K}")


def main():
    print("\n" + "="*70)
    print("  MULTILINGUAL RETRIEVAL TEST — Class 8 SCERT")
    print("  Model  : gemini-embedding-2 (1536-dim)")
    print("  Qdrant : cloud")
    print("="*70)

    results = []
    for label, query, subject, expected_pages in TEST_CASES:
        run_test(label, query, subject, expected_pages)


if __name__ == "__main__":
    main()
