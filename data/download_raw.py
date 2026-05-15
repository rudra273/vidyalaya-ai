import json
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path


BOOKS = [
    # {
    #     "subject": "odia",
    #     "book_name": "ସାହିତ୍ୟସୁରଭି",
    #     "download_url": "https://drive.google.com/uc?export=download&id=1QKBOWJMg0yPJ3nIvuXS4NPiZMIprzaGg",
    # },
    # {
    #     "subject": "english",
    #     "book_name": "Jasmine",
    #     "download_url": "https://drive.google.com/uc?export=download&id=1CRDfeSBGSNOkRdf_tNqoWJXP8U3bkc4t",
    # },
    # {
    #     "subject": "maths",
    #     "book_name": "ଗଣିତ ପ୍ରକାଶ",
    #     "download_url": "https://drive.google.com/uc?export=download&id=1rPDcJkzfUmxM9U45P5dtt0o45byMpTGE",
    # },
    # {
    #     "subject": "hindi",
    #     "book_name": "हिंदी कलिका",
    #     "download_url": "https://drive.google.com/uc?export=download&id=1Q8f90Bd1kevXlIm5jcc5VDKL6FFeY9KJ",
    # },
    # {
    #     "subject": "sanskrit",
    #     "book_name": "संस्कृतकलिका",
    #     "download_url": "https://drive.google.com/uc?export=download&id=1pobhcsgK4rO3L-wH4caitIY4zDUOg9FE",
    # },
    # {
    #     "subject": "science",
    #     "book_name": "ଜିଜ୍ଞାସା",
    #     "download_url": "https://drive.google.com/uc?export=download&id=1izSmwE6fVOX_He4JQv4TT6Cxt6IggaaI",
    # },
    # {
    #     "subject": "social_science",
    #     "book_name": "ସାମାଜିକ ବିଜ୍ଞାନ ଅଧ୍ୟୟନ : ଭାରତ ଓ ଆମ ପୃଥିବୀ",
    #     "download_url": "https://drive.google.com/uc?export=download&id=17dx5DY74ZxepKiox7oSqhq_Y6HPkC124",
    # },

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
        print(f"Downloading: {book.get('book_name', url)}")
        file_path = download_file(url, output_dir)
        print(f"Saved: {file_path}")

        if buffer_seconds:
            time.sleep(buffer_seconds)


def download_file(url, output_dir):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
    )

    with urllib.request.urlopen(request, context=SSL_CONTEXT) as response:
        file_name = get_response_file_name(response)
        file_path = output_dir / file_name
        with open(file_path, "wb") as file:
            file.write(response.read())

    return file_path


def get_response_file_name(response):
    content_disposition = response.headers.get("Content-Disposition", "")
    file_name = parse_content_disposition_file_name(content_disposition)

    if file_name:
        return Path(file_name).name

    url_path = urllib.parse.urlparse(response.url).path
    return Path(urllib.parse.unquote(url_path)).name or "download"


def parse_content_disposition_file_name(content_disposition):
    parts = [part.strip() for part in content_disposition.split(";")]
    params = {}
    for part in parts[1:]:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        params[key.lower()] = value.strip().strip('"')

    if "filename*" in params:
        value = params["filename*"]
        if "''" in value:
            value = value.split("''", 1)[1]
        return urllib.parse.unquote(value)

    if "filename" in params:
        return urllib.parse.unquote(params["filename"])

    return ""


if __name__ == "__main__":
    download_books()
