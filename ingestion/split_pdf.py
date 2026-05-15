import argparse
from pathlib import Path

from pypdf import PdfReader, PdfWriter


def validate_pdf_path(input_pdf):
    """Return a Path for an existing PDF file or raise a clear error."""
    input_pdf = Path(input_pdf)
    if not input_pdf.exists():
        raise FileNotFoundError(f"Input PDF not found: {input_pdf}")
    if input_pdf.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a PDF file, got: {input_pdf}")
    return input_pdf


def validate_page_range(start_page, end_page, total_pages):
    """Validate a 1-based inclusive page range against a PDF page count."""
    if start_page < 1 or end_page < 1:
        raise ValueError("Page numbers must start from 1.")
    if start_page > end_page:
        raise ValueError("start_page cannot be greater than end_page.")
    if end_page > total_pages:
        raise ValueError(
            f"Page range ends at {end_page}, but PDF has only {total_pages} pages."
        )


def write_pdf_part(reader, output_pdf, start_page, end_page):
    """Write a 1-based inclusive page range from a PdfReader to one output PDF."""
    output_pdf = Path(output_pdf)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    writer = PdfWriter()
    for page_no in range(start_page, end_page + 1):
        writer.add_page(reader.pages[page_no - 1])

    with output_pdf.open("wb") as file:
        writer.write(file)

    return output_pdf


def extract_pdf_part(input_pdf, output_pdf, start_page, end_page):
    """Create one PDF containing only the requested 1-based inclusive page range."""
    input_pdf = validate_pdf_path(input_pdf)
    reader = PdfReader(input_pdf)
    total_pages = len(reader.pages)
    validate_page_range(start_page, end_page, total_pages)

    output_pdf = write_pdf_part(
        reader=reader,
        output_pdf=output_pdf,
        start_page=start_page,
        end_page=end_page,
    )

    return {
        "pdf": output_pdf,
        "start_page": start_page,
        "end_page": end_page,
    }


def split_pdf_into_batches(input_pdf, batch_dir, page_batch_size):
    """Split a PDF into multiple page-batch PDFs and return batch metadata."""
    input_pdf = validate_pdf_path(input_pdf)
    batch_dir = Path(batch_dir)

    if page_batch_size < 1:
        raise ValueError("page_batch_size must be at least 1.")

    reader = PdfReader(input_pdf)
    total_pages = len(reader.pages)
    batch_dir.mkdir(parents=True, exist_ok=True)
    batches = []

    for start_page in range(1, total_pages + 1, page_batch_size):
        end_page = min(start_page + page_batch_size - 1, total_pages)
        output_pdf = batch_dir / f"{input_pdf.stem}_p{start_page:04d}_{end_page:04d}.pdf"
        write_pdf_part(reader, output_pdf, start_page, end_page)

        batches.append(
            {
                "pdf": output_pdf,
                "start_page": start_page,
                "end_page": end_page,
            }
        )

    return batches


def build_parser():
    """Build the CLI parser for batch splitting."""
    parser = argparse.ArgumentParser(description="Split a PDF into page batches.")
    parser.add_argument("--input-pdf", required=True, type=Path)
    parser.add_argument("--batch-dir", required=True, type=Path)
    parser.add_argument("--page-batch-size", type=int, default=20)
    return parser


def main():
    """Run the batch splitting CLI."""
    parser = build_parser()
    args = parser.parse_args()
    batches = split_pdf_into_batches(
        input_pdf=args.input_pdf,
        batch_dir=args.batch_dir,
        page_batch_size=args.page_batch_size,
    )
    print(f"Created {len(batches)} batches")
    for batch in batches:
        print(f"{batch['start_page']}-{batch['end_page']}: {batch['pdf']}")


if __name__ == "__main__":
    main()
