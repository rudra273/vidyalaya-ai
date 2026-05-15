import shutil
from pathlib import Path

from convert import convert_raw_to_jsonl_and_markdown
from split_pdf import split_pdf_into_batches
from surya_ocr import run_surya_on_batches


BOARD = "scert_odisha"
CLASS_NO = 8
SUBJECT = "maths"

PDF_PATH = Path("data/raw/textbooks/scert_odisha/class_8/maths_ଗଣିତ_ପ୍ରକାଶ.pdf")
OUTPUT_ROOT = Path("data/processed/ocr") / BOARD / f"class_{CLASS_NO}"
WORK_ROOT = Path("data/tmp/ocr_work") / SUBJECT

PAGE_BATCH_SIZE = 20
TORCH_DEVICE = "auto"
DETECTOR_BATCH_SIZE = 4
RECOGNITION_BATCH_SIZE = 32
LAYOUT_BATCH_SIZE = 4

RAW_OUTPUT_PATH = OUTPUT_ROOT / "raw" / f"{SUBJECT}.json"
JSONL_OUTPUT_PATH = OUTPUT_ROOT / "jsonl" / f"{SUBJECT}.jsonl"
MD_OUTPUT_PATH = OUTPUT_ROOT / "md" / f"{SUBJECT}.md"

LOCAL_PDF_PATH = WORK_ROOT / PDF_PATH.name
BATCH_DIR = WORK_ROOT / "pdf_batches"
SURYA_WORK_DIR = WORK_ROOT / "surya_batches"


def prepare_pdf_batches():
    if not PDF_PATH.exists():
        raise FileNotFoundError(f"PDF not found: {PDF_PATH}")

    if WORK_ROOT.exists():
        shutil.rmtree(WORK_ROOT)
    WORK_ROOT.mkdir(parents=True, exist_ok=True)

    print("Copying PDF to local work path:", LOCAL_PDF_PATH)
    shutil.copyfile(PDF_PATH, LOCAL_PDF_PATH)

    batches = split_pdf_into_batches(
        input_pdf=LOCAL_PDF_PATH,
        batch_dir=BATCH_DIR,
        page_batch_size=PAGE_BATCH_SIZE,
    )
    print(f"Created {len(batches)} batches of up to {PAGE_BATCH_SIZE} pages")
    return batches


def run_ocr(batches):
    return run_surya_on_batches(
        batches=batches,
        output_dir=SURYA_WORK_DIR,
        raw_output_path=RAW_OUTPUT_PATH,
        source_pdf_stem=PDF_PATH.stem,
        torch_device=TORCH_DEVICE,
        detector_batch_size=DETECTOR_BATCH_SIZE,
        recognition_batch_size=RECOGNITION_BATCH_SIZE,
        layout_batch_size=LAYOUT_BATCH_SIZE,
    )


def convert_outputs():
    return convert_raw_to_jsonl_and_markdown(
        raw_path=RAW_OUTPUT_PATH,
        source_pdf=PDF_PATH,
        jsonl_output_path=JSONL_OUTPUT_PATH,
        md_output_path=MD_OUTPUT_PATH,
        board=BOARD,
        class_no=CLASS_NO,
        subject=SUBJECT,
    )


# if __name__ == "__main__":
#     batches = prepare_pdf_batches()
#     run_ocr(batches)
#     convert_outputs()
