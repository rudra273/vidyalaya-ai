from pathlib import Path

from split_pdf import extract_pdf_part
from surya_ocr import run_surya_on_batches


INPUT_PDF = Path("data/raw/textbooks/scert_odisha/class_8/Odia_Sahitya_Surabhi.pdf")
EXPERIMENT_DIR = Path("experiments/ocr/single_page_test")
OUTPUT_PDF = EXPERIMENT_DIR / "Odia_Sahitya_Surabhi_page_1.pdf"
SURYA_OUTPUT_DIR = EXPERIMENT_DIR / "surya"
RAW_OUTPUT_PATH = EXPERIMENT_DIR / "raw" / "odia_page_1.json"
START_PAGE = 1
END_PAGE = 1


def create_single_page_pdf():
    """Create exactly one single-page PDF for a quick OCR experiment."""
    part = extract_pdf_part(
        input_pdf=INPUT_PDF,
        output_pdf=OUTPUT_PDF,
        start_page=START_PAGE,
        end_page=END_PAGE,
    )
    print("Created:", part["pdf"])
    return part["pdf"]


def run_single_page_surya_ocr():
    """Run Surya OCR for the single extracted PDF page."""
    single_page_pdf = create_single_page_pdf()
    batches = [
        {
            "pdf": single_page_pdf,
            "start_page": START_PAGE,
            "end_page": END_PAGE,
        }
    ]
    return run_surya_on_batches(
        batches=batches,
        output_dir=SURYA_OUTPUT_DIR,
        raw_output_path=RAW_OUTPUT_PATH,
        source_pdf_stem=OUTPUT_PDF.stem,
    )



# if __name__ == "__main__":
#     run_single_page_surya_ocr()
