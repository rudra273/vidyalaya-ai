"""Basic retrieval evaluation for textbook RAG."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from vidyalaya_ai.rag.config import RagConfig
from vidyalaya_ai.rag.context import build_context_blocks
from vidyalaya_ai.rag.logging_config import setup_rag_logging
from vidyalaya_ai.rag.retrieval import retrieve_chunks


logger = logging.getLogger("vidyalaya_ai.rag")


@dataclass(frozen=True)
class EvalCase:
    """One retrieval evaluation question."""

    id: str
    query: str
    board: str
    class_no: int
    subject: str
    expected_pages: tuple[int, ...]
    note: str = ""


DEFAULT_EVAL_CASES: tuple[EvalCase, ...] = (
    EvalCase(
        id="english_major_somnath",
        query="Who was Major Somnath Sharma and what happened at Badgam?",
        board="scert_odisha",
        class_no=8,
        subject="english",
        expected_pages=(61, 62, 69, 70),
    ),
    EvalCase(
        id="english_magic_brush",
        query="Which poem teaches creativity, kindness, and the power of art?",
        board="scert_odisha",
        class_no=8,
        subject="english",
        expected_pages=(6, 134, 135, 136, 137),
    ),
    EvalCase(
        id="english_cherry_tree",
        query="What lesson does The Cherry Tree teach?",
        board="scert_odisha",
        class_no=8,
        subject="english",
        expected_pages=(6, 167, 170, 171, 172, 173, 174),
    ),
    EvalCase(
        id="science_robert_hooke_cell",
        query="Who observed cells in cork and wrote Micrographia?",
        board="scert_odisha",
        class_no=8,
        subject="science",
        expected_pages=(21,),
    ),
    EvalCase(
        id="science_onion_cell",
        query="How do students observe an onion cell?",
        board="scert_odisha",
        class_no=8,
        subject="science",
        expected_pages=(22,),
    ),
    EvalCase(
        id="science_force_friction",
        query="What is friction and how does it affect moving objects?",
        board="scert_odisha",
        class_no=8,
        subject="science",
        expected_pages=(77, 79),
    ),
    EvalCase(
        id="maths_rectangle_square",
        query="What are the properties of rectangle and square?",
        board="scert_odisha",
        class_no=8,
        subject="maths",
        expected_pages=(95, 96, 101, 102, 105),
    ),
    EvalCase(
        id="maths_parallelogram_angles",
        query="What can we say about the angles of a parallelogram?",
        board="scert_odisha",
        class_no=8,
        subject="maths",
        expected_pages=(107, 109),
    ),
    EvalCase(
        id="maths_quadrilaterals",
        query="What are quadrilaterals?",
        board="scert_odisha",
        class_no=8,
        subject="maths",
        expected_pages=(94,),
    ),
    EvalCase(
        id="social_science_constitution",
        query="ଭାରତୀୟ ସମ୍ବିଧାନ ବିଷୟରେ କଣ କୁହାଯାଇଛି?",
        board="scert_odisha",
        class_no=8,
        subject="social_science",
        expected_pages=(10, 165),
    ),
    EvalCase(
        id="social_science_election",
        query="ଭାରତର ନିର୍ବାଚନ ବ୍ୟବସ୍ଥା ବିଷୟରେ କଣ ଲେଖାଯାଇଛି?",
        board="scert_odisha",
        class_no=8,
        subject="social_science",
        expected_pages=(139, 160),
    ),
    EvalCase(
        id="social_science_shivaji",
        query="ଶିବାଜୀ ଏବଂ ମରାଠା ସାମ୍ରାଜ୍ୟର ଉତ୍ଥାନ ବିଷୟରେ କୁହ।",
        board="scert_odisha",
        class_no=8,
        subject="social_science",
        expected_pages=(79, 80),
    ),
    EvalCase(
        id="sanskrit_digital_bharat",
        query="डिजिटल् भारतम् विषये किम् अस्ति?",
        board="scert_odisha",
        class_no=8,
        subject="sanskrit",
        expected_pages=(97, 108),
    ),
    EvalCase(
        id="odia_book_language",
        query="ଓଡ଼ିଆ ପୁସ୍ତକରେ ଭାଷାର ଭୂମିକା ବିଷୟରେ କଣ କୁହାଯାଇଛି?",
        board="scert_odisha",
        class_no=8,
        subject="odia",
        expected_pages=(5,),
    ),
)


def run_basic_evaluation(
    *,
    cases: tuple[EvalCase, ...] = DEFAULT_EVAL_CASES,
    config: RagConfig | None = None,
    report_path: Path | str = "reports/rag_eval_class8.jsonl",
) -> list[dict[str, Any]]:
    """Run retrieval and context evaluation and save a JSONL report."""
    if not logger.handlers:
        setup_rag_logging()

    config = config or RagConfig()
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    with report_path.open("w", encoding="utf-8") as report_file:
        for case in cases:
            result = evaluate_case(case, config=config)
            results.append(result)
            report_file.write(json.dumps(result, ensure_ascii=False) + "\n")

    summary = summarize_results(results)
    logger.info("Evaluation complete: %s", summary)
    logger.info("Evaluation report saved to %s", report_path)
    return results


def evaluate_case(case: EvalCase, *, config: RagConfig | None = None) -> dict[str, Any]:
    """Evaluate one retrieval case."""
    config = config or RagConfig()
    hits = retrieve_chunks(
        case.query,
        board=case.board,
        class_no=case.class_no,
        subject=case.subject,
        top_k=config.top_k,
        config=config,
    )
    context_blocks = build_context_blocks(hits, config=config)

    top_pages = [hit.get("page_no") for hit in hits]
    context_pages = [block.get("page_no") for block in context_blocks]
    top_k_has_expected_page = _pages_overlap(top_pages, case.expected_pages)
    context_has_expected_page = _pages_overlap(context_pages, case.expected_pages)
    wrong_subject = any(hit.get("subject") != case.subject for hit in hits)
    failure_reasons = _failure_reasons(
        hits=hits,
        context_blocks=context_blocks,
        wrong_subject=wrong_subject,
        top_k_has_expected_page=top_k_has_expected_page,
        context_has_expected_page=context_has_expected_page,
        config=config,
    )

    return {
        "case": asdict(case),
        "top_k_has_expected_page": top_k_has_expected_page,
        "context_has_expected_page": context_has_expected_page,
        "top_score": hits[0]["score"] if hits else None,
        "top_pages": top_pages,
        "context_pages": context_pages,
        "context_block_count": len(context_blocks),
        "failure_reasons": failure_reasons,
        "top_hits": [
            {
                "score": hit.get("score"),
                "subject": hit.get("subject"),
                "book_name": hit.get("book_name"),
                "page_no": hit.get("page_no"),
                "chunk_id": hit.get("chunk_id"),
            }
            for hit in hits
        ],
    }


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize evaluation results."""
    total = len(results)
    top_k_pass = sum(1 for result in results if result["top_k_has_expected_page"])
    context_pass = sum(1 for result in results if result["context_has_expected_page"])
    failed = [result["case"]["id"] for result in results if result["failure_reasons"]]

    return {
        "total": total,
        "top_k_expected_page_pass": top_k_pass,
        "context_expected_page_pass": context_pass,
        "failed_cases": failed,
    }


def _failure_reasons(
    *,
    hits: list[dict[str, Any]],
    context_blocks: list[dict[str, Any]],
    wrong_subject: bool,
    top_k_has_expected_page: bool,
    context_has_expected_page: bool,
    config: RagConfig,
) -> list[str]:
    """Build simple failure reason labels for one case."""
    reasons: list[str] = []
    if not hits:
        reasons.append("no_results")
    if wrong_subject:
        reasons.append("wrong_subject")
    if not top_k_has_expected_page:
        reasons.append("wrong_page_in_top_k")
    if not context_has_expected_page:
        reasons.append("wrong_page_in_context")
    if any(0 < len(str(block.get("text", ""))) < 200 for block in context_blocks):
        reasons.append("context_too_small")
    if any(len(str(block.get("text", ""))) >= config.max_context_chars for block in context_blocks):
        reasons.append("context_truncated_or_large")

    return reasons


def _pages_overlap(found_pages: list[Any], expected_pages: tuple[int, ...]) -> bool:
    """Return whether found page values overlap expected page numbers."""
    found = set()
    for value in found_pages:
        if isinstance(value, list):
            found.update(int(item) for item in value)
        elif value is not None:
            found.add(int(value))

    return bool(found.intersection(expected_pages))


if __name__ == "__main__":
    run_basic_evaluation()
