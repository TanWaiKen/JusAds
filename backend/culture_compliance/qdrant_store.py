"""
qdrant_store.py
───────────────
Qdrant vector store: collection setup, upsert, and retrieval.
"""

import csv
import uuid
import time
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from .config import (
    EMBED_DIMENSIONS,
    QDRANT_API_KEY,
    QDRANT_COLLECTION_NAME,
    QDRANT_TOP_K,
    QDRANT_URL,
)
from .embeddings import embed_batch

# ── Client ────────────────────────────────────────────────────────────────────

_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=120)

UPSERT_BATCH_SIZE = 20


# ── Helpers ───────────────────────────────────────────────────────────────────


def row_to_text(row: dict) -> str:
    """Convert a CSV row dict into a single string for embedding."""
    return " | ".join(f"{k}: {v}" for k, v in row.items() if v and v.strip())


def _read_csv(path: Path) -> list[dict]:
    """Read a CSV and return list of cleaned row dicts."""
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            clean = {k.strip(): v.strip() for k, v in row.items() if k}
            if any(clean.values()):
                rows.append(clean)
    return rows


# ── Collection management ────────────────────────────────────────────────────


def ensure_collection(
    name: str = QDRANT_COLLECTION_NAME,
    recreate: bool = False,
) -> None:
    """Create the Qdrant collection if it doesn't exist (or recreate it)."""
    existing = [c.name for c in _client.get_collections().collections]

    if name in existing:
        if recreate:
            print(f"  [RECREATE] Recreating collection '{name}'...")
            _client.delete_collection(name)
        else:
            print(f"  [INFO] Collection '{name}' already exists — upserting into it.")
            return

    _client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(
            size=EMBED_DIMENSIONS,
            distance=Distance.COSINE,
        ),
    )
    print(f"  [OK] Collection '{name}' created ({EMBED_DIMENSIONS}-dim, cosine).")


# ── Ingest CSV rows ──────────────────────────────────────────────────────────


def ingest_csv(
    csv_path: str | Path,
    collection_name: str = QDRANT_COLLECTION_NAME,
    recreate: bool = False,
) -> int:
    """
    Read a CSV file, embed each row with Titan v2, and upsert into Qdrant.
    Returns the number of vectors upserted.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    ensure_collection(collection_name, recreate=recreate)

    rows = _read_csv(csv_path)
    print(f"\n📄 {csv_path.name}: {len(rows)} rows")

    texts = [row_to_text(row) for row in rows]
    total_upserted = 0

    for batch_start in range(0, len(texts), UPSERT_BATCH_SIZE):
        batch_texts = texts[batch_start : batch_start + UPSERT_BATCH_SIZE]
        batch_rows = rows[batch_start : batch_start + UPSERT_BATCH_SIZE]
        embeddings = embed_batch(batch_texts)

        points = []
        for row, embedding, text in zip(batch_rows, embeddings, batch_texts):
            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding,
                    payload={
                        "source": csv_path.name,
                        "row_text": text,
                        **row,
                    },
                )
            )

        _client.upsert(collection_name=collection_name, points=points)
        total_upserted += len(points)
        print(f"  ✅ Upserted {total_upserted}/{len(rows)} (Batch {batch_start//UPSERT_BATCH_SIZE + 1})")
        
        # Give Bedrock API a break between batches
        if batch_start + UPSERT_BATCH_SIZE < len(rows):
            time.sleep(1.0)

    print(f"  🎉 Total {total_upserted} vectors upserted to '{collection_name}'")
    return total_upserted


# ── Retrieval ─────────────────────────────────────────────────────────────────


def retrieve_guidelines(
    query_text: str,
    top_k: int = QDRANT_TOP_K,
    collection_name: str = QDRANT_COLLECTION_NAME,
) -> str:
    """
    Embed the query, search Qdrant, and return a formatted string of
    matching guideline rows ready for prompt injection.
    """
    from .embeddings import embed_text

    vector = embed_text(query_text, input_type="search_query")

    results = _client.query_points(
        collection_name=collection_name,
        query=vector,
        limit=top_k,
        with_payload=True,
    )

    if not results.points:
        return "No relevant regulatory guidelines found."

    lines = []
    for i, point in enumerate(results.points, start=1):
        payload = point.payload
        if not payload:
            continue
        score = round(point.score, 3)
        row_text = " | ".join(
            f"{k}: {v}"
            for k, v in payload.items()
            if k not in ("source", "row_text") and v
        )
        source = payload.get("source", "MCMC Guidelines")
        lines.append(f"[{i}] (source: {source}, relevance: {score})\n{row_text}")

    return "\n\n".join(lines)
