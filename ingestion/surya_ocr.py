import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path


def detect_torch_device():
    try:
        import torch
    except ImportError:
        return "cpu"

    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def build_surya_env(
    torch_device="auto",
    detector_batch_size=4,
    recognition_batch_size=32,
    layout_batch_size=4,
):
    env = os.environ.copy()
    if torch_device == "auto":
        torch_device = detect_torch_device()

    env["TORCH_DEVICE"] = torch_device
    env["DETECTOR_BATCH_SIZE"] = str(detector_batch_size)
    env["RECOGNITION_BATCH_SIZE"] = str(recognition_batch_size)
    env["LAYOUT_BATCH_SIZE"] = str(layout_batch_size)
    return env


def find_results_json(output_dir):
    results = sorted(Path(output_dir).rglob("results.json"))
    if not results:
        raise FileNotFoundError(f"No Surya results.json found under {output_dir}")
    return results[0]


def load_batch_pages(results_dir, batch_pdf):
    batch_pdf = Path(batch_pdf)
    results_path = find_results_json(results_dir)
    data = json.loads(results_path.read_text(encoding="utf-8"))

    pages = data.get(batch_pdf.stem)
    if pages is None and len(data) == 1:
        pages = next(iter(data.values()))
    if not isinstance(pages, list):
        raise ValueError(f"Could not find page results for {batch_pdf.stem}")

    return pages


def run_surya_on_pdf_batch(batch_pdf, output_dir, env=None):
    batch_pdf = Path(batch_pdf)
    output_dir = Path(output_dir)

    if not batch_pdf.exists():
        raise FileNotFoundError(f"Batch PDF not found: {batch_pdf}")

    surya_command = shutil.which("surya_ocr")
    if not surya_command:
        raise RuntimeError(
            "surya_ocr command is not installed or not on PATH. "
            "Install it with: python -m pip install -r ingestion/requirements.txt"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        surya_command,
        str(batch_pdf),
        "--output_dir",
        str(output_dir),
    ]

    print("Running:", " ".join(command))
    subprocess.run(command, check=True, env=env)
    return load_batch_pages(output_dir, batch_pdf)


def run_surya_on_batches(
    batches,
    output_dir,
    raw_output_path,
    source_pdf_stem,
    torch_device="auto",
    detector_batch_size=4,
    recognition_batch_size=32,
    layout_batch_size=4,
):
    output_dir = Path(output_dir)
    raw_output_path = Path(raw_output_path)
    env = build_surya_env(
        torch_device=torch_device,
        detector_batch_size=detector_batch_size,
        recognition_batch_size=recognition_batch_size,
        layout_batch_size=layout_batch_size,
    )

    print("Surya device:", env["TORCH_DEVICE"])
    print("Detector batch size:", env["DETECTOR_BATCH_SIZE"])
    print("Recognition batch size:", env["RECOGNITION_BATCH_SIZE"])
    print("Layout batch size:", env["LAYOUT_BATCH_SIZE"])

    all_pages = []
    start = time.monotonic()

    for index, batch in enumerate(batches, start=1):
        batch_pdf = Path(batch["pdf"])
        batch_output_dir = output_dir / batch_pdf.stem

        print(
            f"[{index}/{len(batches)}] "
            f"Pages {batch['start_page']}-{batch['end_page']}"
        )
        batch_pages = run_surya_on_pdf_batch(
            batch_pdf=batch_pdf,
            output_dir=batch_output_dir,
            env=env,
        )

        for local_index, page in enumerate(batch_pages, start=0):
            page["page"] = batch["start_page"] + local_index
            all_pages.append(page)

    elapsed = time.monotonic() - start
    print(f"Surya finished {len(all_pages)} pages in {elapsed / 60:.1f} minutes")

    raw_output_path.parent.mkdir(parents=True, exist_ok=True)
    raw_output_path.write_text(
        json.dumps({source_pdf_stem: all_pages}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("Saved raw JSON:", raw_output_path)
    return all_pages


def build_parser():
    parser = argparse.ArgumentParser(description="Run Surya OCR on PDF batches.")
    parser.add_argument("--batch-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--raw-output", required=True, type=Path)
    parser.add_argument("--source-pdf-stem", required=True)
    parser.add_argument("--torch-device", default="auto")
    parser.add_argument("--detector-batch-size", type=int, default=4)
    parser.add_argument("--recognition-batch-size", type=int, default=32)
    parser.add_argument("--layout-batch-size", type=int, default=4)
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    pdfs = sorted(args.batch_dir.glob("*.pdf"))
    batches = [
        {
            "pdf": pdf,
            "start_page": index,
            "end_page": index,
        }
        for index, pdf in enumerate(pdfs, start=1)
    ]
    run_surya_on_batches(
        batches=batches,
        output_dir=args.output_dir,
        raw_output_path=args.raw_output,
        source_pdf_stem=args.source_pdf_stem,
        torch_device=args.torch_device,
        detector_batch_size=args.detector_batch_size,
        recognition_batch_size=args.recognition_batch_size,
        layout_batch_size=args.layout_batch_size,
    )


if __name__ == "__main__":
    main()
