"""
qdrant_store.py
───────────────
Qdrant vector store for prompt templates: collection setup, ingest, and search.
Follows the same pattern as the regulatory rules store.
"""

import csv
import logging
import time
import uuid
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from .embeddings import EMBED_DIMENSIONS, embed_batch, embed_text

logger = logging.getLogger(__name__)

# -- Config (from env) ---------------------------------------------------------

import os

QDRANT_URL = os.environ.get("QDRANT_URL", "")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", "")
QDRANT_PROMPT_COLLECTION = os.environ.get("QDRANT_PROMPT_COLLECTION", "prompt_templates")
QDRANT_TOP_K = int(os.environ.get("QDRANT_PROMPT_TOP_K", "8"))
UPSERT_BATCH_SIZE = 20

# -- Client --------------------------------------------------------------------

_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=120) if QDRANT_URL else None


# -- Helpers -------------------------------------------------------------------


def _row_to_text(row: dict) -> str:
    """Combine title + description + content into one searchable string."""
    parts = []
    if row.get("title"):
        parts.append(row["title"])
    if row.get("description"):
        parts.append(row["description"])
    if row.get("content"):
        # Truncate very long prompts for embedding (Titan max ~8000 chars).
        parts.append(row["content"][:2000])
    return " | ".join(parts)


# -- Collection management -----------------------------------------------------


def ensure_collection(recreate: bool = False) -> None:
    """Create the prompt_templates collection if it doesn't exist."""
    if not _client:
        raise RuntimeError("Qdrant client not configured (QDRANT_URL missing)")

    name = QDRANT_PROMPT_COLLECTION
    existing = [c.name for c in _client.get_collections().collections]

    if name in existing:
        if recreate:
            logger.info("[PromptSearch] Recreating collection '%s'...", name)
            _client.delete_collection(name)
        else:
            logger.info("[PromptSearch] Collection '%s' already exists.", name)
            return

    _client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=EMBED_DIMENSIONS, distance=Distance.COSINE),
    )
    logger.info("[PromptSearch] Collection '%s' created (%d-dim, cosine).", name, EMBED_DIMENSIONS)


# -- Ingest CSV ----------------------------------------------------------------


def ingest_prompts_csv(csv_path: str | Path, recreate: bool = False) -> int:
    """Read the nano-banana-pro-prompts CSV, embed each row, and upsert to Qdrant.

    Args:
        csv_path: Path to the CSV file.
        recreate: If True, drop and recreate the collection first.

    Returns:
        Number of vectors upserted.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    ensure_collection(recreate=recreate)

    rows: list[dict] = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            clean = {k.strip(): (v.strip() if v else "") for k, v in row.items() if k}
            if clean.get("title") or clean.get("content"):
                rows.append(clean)

    logger.info("[PromptSearch] CSV loaded: %d prompts from %s", len(rows), csv_path.name)
    texts = [_row_to_text(row) for row in rows]

    total = 0
    for batch_start in range(0, len(texts), UPSERT_BATCH_SIZE):
        batch_texts = texts[batch_start: batch_start + UPSERT_BATCH_SIZE]
        batch_rows = rows[batch_start: batch_start + UPSERT_BATCH_SIZE]

        embeddings = embed_batch(batch_texts)

        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=emb,
                payload={
                    "prompt_id": row.get("id", ""),
                    "title": row.get("title", ""),
                    "description": row.get("description", ""),
                    "content": row.get("content", ""),
                    "source_link": row.get("sourceLink", ""),
                    "source_media": row.get("sourceMedia", ""),
                    "author": row.get("author", ""),
                },
            )
            for row, emb in zip(batch_rows, embeddings)
        ]

        _client.upsert(collection_name=QDRANT_PROMPT_COLLECTION, points=points)
        total += len(points)
        logger.info("[PromptSearch] Upserted %d/%d", total, len(rows))

        # Throttle to avoid rate limits on Bedrock embedding calls.
        if batch_start + UPSERT_BATCH_SIZE < len(rows):
            time.sleep(0.5)

    logger.info("[PromptSearch] Ingestion complete: %d vectors in '%s'", total, QDRANT_PROMPT_COLLECTION)
    return total


# -- Search --------------------------------------------------------------------


def search_prompts(query: str, top_k: int = QDRANT_TOP_K) -> list[dict]:
    """Embed the query and return the top-K most similar prompt templates.

    Args:
        query: The user's search text (what they want to generate).
        top_k: Number of results to return.

    Returns:
        A list of dicts with keys: title, description, content, score, source_media.
    """
    if not _client:
        logger.warning("[PromptSearch] Qdrant not configured; returning empty results.")
        return []

    vector = embed_text(query, input_type="search_query")

    results = _client.query_points(
        collection_name=QDRANT_PROMPT_COLLECTION,
        query=vector,
        limit=top_k,
        with_payload=True,
    )

    suggestions: list[dict] = []
    for point in results.points:
        payload = point.payload or {}
        suggestions.append({
            "title": payload.get("title", ""),
            "description": payload.get("description", ""),
            "content": payload.get("content", ""),
            "score": round(point.score, 3),
            "source_media": payload.get("source_media", ""),
            "source_link": payload.get("source_link", ""),
        })

    return suggestions
