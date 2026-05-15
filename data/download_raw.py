import json
import ssl
import time
import urllib.request
from pathlib import Path


BOOKS = [
    {
        "subject": "odia",
        "book_name": "ସାହିତ୍ୟସୁରଭି",
        "download_url": "https://drive.google.com/uc?export=download&id=1QKBOWJMg0yPJ3nIvuXS4NPiZMIprzaGg",
        "file_name": "odia_ସାହିତ୍ୟସୁରଭି.pdf",
    },
    {
        "subject": "english",
        "book_name": "Jasmine",
        "download_url": "https://drive.google.com/uc?export=download&id=1CRDfeSBGSNOkRdf_tNqoWJXP8U3bkc4t",
        "file_name": "english_jasmine.pdf",
    },
    {
        "subject": "maths",
        "book_name": "ଗଣିତ ପ୍ରକାଶ",
        "download_url": "https://drive.google.com/uc?export=download&id=1rPDcJkzfUmxM9U45P5dtt0o45byMpTGE",
        "file_name": "maths_ଗଣିତ_ପ୍ରକାଶ.pdf",
    },
    {
        "subject": "hindi",
        "book_name": "हिंदी कलिका",
        "download_url": "https://drive.google.com/uc?export=download&id=1Q8f90Bd1kevXlIm5jcc5VDKL6FFeY9KJ",
        "file_name": "hindi_हिंदी_कलिका.pdf",
    },
    {
        "subject": "sanskrit",
        "book_name": "संस्कृतकलिका",
        "download_url": "https://drive.google.com/uc?export=download&id=1pobhcsgK4rO3L-wH4caitIY4zDUOg9FE",
        "file_name": "sanskrit_संस्कृतकलिका.pdf",
    },
    {
        "subject": "science",
        "book_name": "ଜିଜ୍ଞାସା",
        "download_url": "https://drive.google.com/uc?export=download&id=1izSmwE6fVOX_He4JQv4TT6Cxt6IggaaI",
        "file_name": "science_ଜିଜ୍ଞାସା.pdf",
    },
    {
        "subject": "social_science",
        "book_name": "ସାମାଜିକ ବିଜ୍ଞାନ ଅଧ୍ୟୟନ : ଭାରତ ଓ ଆମ ପୃଥିବୀ",
        "download_url": "https://drive.google.com/uc?export=download&id=17dx5DY74ZxepKiox7oSqhq_Y6HPkC124",
        "file_name": "social_science_ସାମାଜିକ_ବିଜ୍ଞାନ_ଅଧ୍ୟୟନ_ଭାରତ_ଓ_ଆମ_ପୃଥିବୀ.pdf",
    },

]


OUTPUT_DIR = Path("data/raw/textbooks/scert_odisha/class_8")
BUFFER_SECONDS = 5
SSL_CONTEXT = ssl._create_unverified_context()


def load_books(input_data):
    if isinstance(input_data, (list, tuple)):
        return input_data

    if isinstance(input_data, dict):
        return input_data.get("books", [])

    input_path = Path(input_data)
    with input_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, list):
        return data

    return data.get("books", [])


def download_books(input_data=BOOKS, output_dir=OUTPUT_DIR, buffer_seconds=BUFFER_SECONDS):
    books = load_books(input_data)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for book in books:
        url = book["download_url"]
        file_path = output_dir / book["file_name"]

        if file_path.exists():
            print(f"Skipping existing file: {file_path}")
            continue

        print(f"Downloading: {book.get('book_name', file_path.name)}")
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


if __name__ == "__main__":
    download_books()
