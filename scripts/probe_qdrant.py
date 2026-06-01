"""Quick probe: show what metadata values actually exist in Qdrant collection."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from dotenv import load_dotenv
load_dotenv()

from qdrant_client import QdrantClient
from vidyalaya_ai.rag.config import RagConfig

config = RagConfig()
client = QdrantClient(url=config.qdrant_url, api_key=config.qdrant_api_key)

info = client.get_collection(config.collection_name)
print(f"Collection: {config.collection_name}")
print(f"Points count: {info.points_count}")

# Fetch a sample of 20 points to see payload structure
result = client.scroll(
    collection_name=config.collection_name,
    limit=20,
    with_payload=True,
    with_vectors=False,
)
points = result[0]
print(f"\nSample payloads ({len(points)} points):")
seen_keys = set()
for p in points:
    payload = p.payload or {}
    board = payload.get("board", "?")
    class_ = payload.get("class", "?")
    subject = payload.get("subject", "?")
    language = payload.get("language", "?")
    page = payload.get("page_no", "?")
    book = payload.get("book_name", "?")[:40]
    key = (board, class_, subject, language)
    if key not in seen_keys:
        seen_keys.add(key)
        print(f"  board={board!r:12} class={class_!r:4} subject={subject!r:15} language={language!r:8} book={book!r}")

print(f"\nUnique (board, class, subject, language) combos: {len(seen_keys)}")

# Scroll more to find all unique combinations
all_combos = set()
offset = None
while True:
    result = client.scroll(
        collection_name=config.collection_name,
        limit=250,
        offset=offset,
        with_payload=True,
        with_vectors=False,
    )
    batch, next_offset = result
    for p in batch:
        payload = p.payload or {}
        key = (payload.get("board"), payload.get("class"), payload.get("subject"), payload.get("language"))
        all_combos.add(key)
    if next_offset is None:
        break
    offset = next_offset

print(f"\nAll unique (board, class, subject, language) combinations in DB:")
for combo in sorted(all_combos, key=lambda x: str(x)):
    print(f"  board={combo[0]!r:12} class={combo[1]!r:4} subject={combo[2]!r:20} language={combo[3]!r}")
