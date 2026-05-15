import argparse
import json
from pathlib import Path


def load_surya_pages(raw_path, source_pdf_stem):
    raw_path = Path(raw_path)
    data = json.loads(raw_path.read_text(encoding="utf-8"))

    pages = data.get(source_pdf_stem)
    if pages is None and len(data) == 1:
        pages = next(iter(data.values()))
    if not isinstance(pages, list):
        raise ValueError(f"Could not find page results for {source_pdf_stem}")

    return pages


def page_text(page):
    lines = []
    for line in page.get("text_lines", []):
        text = str(line.get("text", "")).strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


def convert_raw_to_jsonl_and_markdown(
    raw_path,
    source_pdf,
    jsonl_output_path,
    md_output_path,
    board,
    class_no,
    subject,
    ocr_engine="surya",
):
    source_pdf = Path(source_pdf)
    jsonl_output_path = Path(jsonl_output_path)
    md_output_path = Path(md_output_path)

    pages = load_surya_pages(raw_path, source_pdf.stem)

    jsonl_output_path.parent.mkdir(parents=True, exist_ok=True)
    md_output_path.parent.mkdir(parents=True, exist_ok=True)

    with jsonl_output_path.open("w", encoding="utf-8") as jsonl_file:
        for index, page in enumerate(pages, start=1):
            page_no = page.get("page", index)
            record = {
                "board": board,
                "class": class_no,
                "subject": subject,
                "source_pdf": str(source_pdf),
                "page_no": page_no,
                "text": page_text(page),
            }
            jsonl_file.write(json.dumps(record, ensure_ascii=False) + "\n")

    markdown_parts = [
        "---",
        f"board: {board}",
        f"class: {class_no}",
        f"subject: {subject}",
        f"source_pdf: {source_pdf}",
        f"ocr_engine: {ocr_engine}",
        "---",
        "",
    ]

    for index, page in enumerate(pages, start=1):
        page_no = page.get("page", index)
        markdown_parts.append(f"## Page {page_no}")
        markdown_parts.append("")
        markdown_parts.append(page_text(page))
        markdown_parts.append("")

    md_output_path.write_text("\n".join(markdown_parts), encoding="utf-8")

    print("Pages:", len(pages))
    print("Saved JSONL:", jsonl_output_path)
    print("Saved Markdown:", md_output_path)
    return pages


def build_parser():
    parser = argparse.ArgumentParser(description="Convert Surya raw JSON to JSONL and Markdown.")
    parser.add_argument("--raw-path", required=True, type=Path)
    parser.add_argument("--source-pdf", required=True, type=Path)
    parser.add_argument("--jsonl-output", required=True, type=Path)
    parser.add_argument("--md-output", required=True, type=Path)
    parser.add_argument("--board", required=True)
    parser.add_argument("--class-no", required=True, type=int)
    parser.add_argument("--subject", required=True)
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    convert_raw_to_jsonl_and_markdown(
        raw_path=args.raw_path,
        source_pdf=args.source_pdf,
        jsonl_output_path=args.jsonl_output,
        md_output_path=args.md_output,
        board=args.board,
        class_no=args.class_no,
        subject=args.subject,
    )


if __name__ == "__main__":
    main()
