import ssl
import time
import urllib.request
from pathlib import Path


jsonlf = [
    {
        "file_name": "social_science.jsonl",
        "download_url": "https://drive.google.com/uc?export=download&id=1vXqB5C_Op7QXnHp1h96kYhbT-CIQbCgj",
    },
    {
        "file_name": "sanskrit.jsonl",
        "download_url": "https://drive.google.com/uc?export=download&id=1bRJ7OxzqDE66RQq622SDIrZCs6D3Kx4H",
    },
    {
        "file_name": "hindi.jsonl",
        "download_url": "https://drive.google.com/uc?export=download&id=1t_9v6MpwYwJFpFvq68BiR7JxVJ-b2Vi8",
    },
    {
        "file_name": "english.jsonl",
        "download_url": "https://drive.google.com/uc?export=download&id=10tuDh1OmmUNB4NVeZN38BwyucmHuulu1",
    },
    {
        "file_name": "odia.jsonl",
        "download_url": "https://drive.google.com/uc?export=download&id=1EdhYwXyMtdst5Tk7TW-5UMSY50WYJIyw",
    },
    {
        "file_name": "science.jsonl",
        "download_url": "https://drive.google.com/uc?export=download&id=1nXL_2GoheuAl0Flpgi3RGgrHJNU48FJY",
    },
    {
        "file_name": "maths.jsonl",
        "download_url": "https://drive.google.com/uc?export=download&id=1VCIaO8D_AAhHk3PfUfGIOVECUian3s3P",
    },
]


BUFFER_SECONDS = 2
SSL_CONTEXT = ssl._create_unverified_context()


def download_files(files, output_dir, buffer_seconds=BUFFER_SECONDS):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for file_details in files:
        file_name = file_details["file_name"]
        url = file_details["download_url"]
        file_path = output_dir / file_name

        print(f"Downloading: {file_name}")
        download_file(url, file_path)
        print(f"Saved: {file_path}")

        if buffer_seconds:
            time.sleep(buffer_seconds)


def download_file(url, file_path):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
    )

    with urllib.request.urlopen(request, context=SSL_CONTEXT) as response:
        with open(file_path, "wb") as file:
            file.write(response.read())


def main():
    output_dir = Path("data/processed/ocr/scert_odisha/class_8/jsonl")
    download_files(jsonlf, output_dir)


if __name__ == "__main__":
    main()
