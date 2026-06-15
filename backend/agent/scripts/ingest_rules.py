#!/usr/bin/env python3
"""
ingest_rules.py
───────────────
Ingest regulatory rules from CSV into a single Qdrant collection.
Uses Gemini embedding-001 via Vertex AI for embeddings.

Usage:
    cd backend
    python -m agent.scripts.ingest_rules
    python -m agent.scripts.ingest_rules --recreate   # Drop and recreate collection
"""

import csv
import sys
import argparse
from pathlib import Path

# Add backend/ to path so config imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from google import genai
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Distance, VectorParams, PayloadSchemaType

from config import (
    VERTEX_PROJECT_ID,
    VERTEX_LOCATION,
    QDRANT_URL,
    QDRANT_API_KEY,
    QDRANT_COLLECTION_NAME,
)

# ── Constants ─────────────────────────────────────────────────────────────────
CSV_PATH = Path(__file__).resolve().parent.parent / "regulatory_rules_vector_db_dataset.csv"
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 3072  # gemini-embedding-001 outputs 3072 dimensions
BATCH_SIZE = 20


def get_client():
    """Initialize Gemini client for embeddings."""
    return genai.Client(vertexai=True, project=VERTEX_PROJECT_ID, location=VERTEX_LOCATION)


def embed_batch(client, texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts using Gemini embedding model."""
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=texts,
    )
    return [e.values for e in result.embeddings]


def derive_source(row: dict) -> str:
    """Derive the source metadata value from the CSV row (lowercase)."""
    return row["source"].strip().lower()


def derive_severity(row: dict) -> str:
    """Derive severity from category and tags."""
    tags = row.get("tags", "").lower()
    category = row.get("category", "").lower()

    if any(word in tags for word in ["prohibited", "csam", "terrorism", "harmful"]):
        return "severe"
    if any(word in category for word in ["prohibited", "harmful"]):
        return "severe"
    if any(word in tags for word in ["children", "minors", "misleading"]):
        return "moderate"
    return "minor"


def load_csv() -> list[dict]:
    """Load and parse the CSV file."""
    if not CSV_PATH.exists():
        print(f"❌ CSV file not found: {CSV_PATH}")
        sys.exit(1)

    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"📄 Loaded {len(rows)} rules from {CSV_PATH.name}")
    return rows


def main():
    parser = argparse.ArgumentParser(description="Ingest regulatory rules into Qdrant")
    parser.add_argument("--recreate", action="store_true", help="Drop and recreate the collection")
    args = parser.parse_args()

    # Load data
    rows = load_csv()

    # Initialize clients
    gemini_client = get_client()
    qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

    # Handle collection creation
    collection_name = QDRANT_COLLECTION_NAME

    if args.recreate:
        print(f"🗑️  Recreating collection '{collection_name}'...")
        if qdrant.collection_exists(collection_name):
            qdrant.delete_collection(collection_name)
        qdrant.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )
        # Create payload index for source filtering
        qdrant.create_payload_index(
            collection_name=collection_name,
            field_name="source",
            field_schema=PayloadSchemaType.KEYWORD,
        )
    else:
        # Create only if it doesn't exist
        collections = [c.name for c in qdrant.get_collections().collections]
        if collection_name not in collections:
            print(f"✨ Creating collection '{collection_name}'...")
            qdrant.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
            )
            qdrant.create_payload_index(
                collection_name=collection_name,
                field_name="source",
                field_schema=PayloadSchemaType.KEYWORD,
            )
        else:
            print(f"📦 Collection '{collection_name}' already exists")

    # Embed and upsert in batches
    total_upserted = 0

    for batch_start in range(0, len(rows), BATCH_SIZE):
        batch = rows[batch_start:batch_start + BATCH_SIZE]

        # Prepare texts for embedding (rule_title + rule_text for richer semantics)
        texts = [f"{row['rule_title']}: {row['rule_text']}" for row in batch]

        # Get embeddings
        embeddings = embed_batch(gemini_client, texts)

        # Build points
        points = []
        for i, (row, embedding) in enumerate(zip(batch, embeddings)):
            point_id = batch_start + i
            points.append(PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "doc_id": row["id"],
                    "source": derive_source(row),
                    "regulator": row.get("regulator", ""),
                    "framework": row.get("framework", ""),
                    "category": row.get("category", ""),
                    "rule_title": row.get("rule_title", ""),
                    "guideline_text": row.get("rule_text", ""),  # matches query code field name
                    "applies_to": row.get("applies_to", ""),
                    "enforcement": row.get("enforcement", ""),
                    "tags": row.get("tags", ""),
                    "severity": derive_severity(row),
                    "effective_date": row.get("effective_date", ""),
                    "last_updated": row.get("last_updated", ""),
                }
            ))

        # Upsert batch
        qdrant.upsert(collection_name=collection_name, points=points)
        total_upserted += len(points)
        print(f"  ↑ Upserted batch {batch_start // BATCH_SIZE + 1} ({len(points)} points)")

    # Summary
    print(f"\n✅ Done! Upserted {total_upserted} points to collection '{collection_name}'")

    # Show source distribution
    sources = {}
    for row in rows:
        s = derive_source(row)
        sources[s] = sources.get(s, 0) + 1
    print(f"   Sources: {sources}")


if __name__ == "__main__":
    main()
