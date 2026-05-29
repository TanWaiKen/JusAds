"""
ingest_personas.py
──────────────────
CLI script to ingest cultural persona narratives CSV into the dedicated
'cultural-personas' Qdrant collection.

Usage:
    # Ingest persona narratives (default CSV path)
    python -m culture_compliance.ingest_personas

    # Custom CSV path
    python -m culture_compliance.ingest_personas --csv path/to/personas.csv

    # Recreate collection before ingesting
    python -m culture_compliance.ingest_personas --recreate
"""

import argparse
import csv
import logging
import time
import uuid
from pathlib import Path
from typing import Optional

from pydantic import ValidationError
from qdrant_client.models import PointStruct

from config import PERSONA_COLLECTION_NAME, PERSONA_COLLECTION_CONFIG
from .models.cultural_schemas import PersonaEntry

logger = logging.getLogger(__name__)

# Default CSV path for persona narratives
DEFAULT_PERSONA_CSV = Path(__file__).parent / "data" / "cultural_personas.csv"

# Batch size for embedding and upsert operations
UPSERT_BATCH_SIZE = 10


def validate_persona_row(row: dict, row_number: int) -> tuple[bool, Optional[str]]:
    """Validate a single CSV row against PersonaEntry schema.

    Args:
        row: A dictionary representing a single CSV row.
        row_number: The 1-based row number in the CSV file.

    Returns:
        A tuple of (is_valid, error_message_or_none).
    """
    try:
        PersonaEntry(**row)
        return True, None
    except ValidationError as e:
        first_error = e.errors()[0]
        field = first_error["loc"][0] if first_error["loc"] else "unknown"
        value = row.get(str(field), "")
        reason = first_error["msg"]
        error_msg = f"Row {row_number}: Invalid {field} value '{value[:50]}'. {reason}"
        return False, error_msg


def _read_persona_csv(path: Path) -> list[dict]:
    """Read a persona narratives CSV and return list of cleaned row dicts.

    Args:
        path: Path to the CSV file.

    Returns:
        List of dictionaries, one per CSV row, with stripped keys and values.
    """
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            clean = {k.strip(): v.strip() for k, v in row.items() if k}
            if any(clean.values()):
                rows.append(clean)
    return rows


def ingest_personas(csv_path: Path, recreate: bool = False) -> int:
    """Ingest persona narratives CSV into the 'cultural-personas' Qdrant collection.

    Args:
        csv_path: Path to the persona narratives CSV file.
        recreate: If True, drop and recreate the collection before ingesting.

    Returns:
        The number of vectors upserted into the collection.
    """
    from .embeddings import embed_batch
    from .qdrant_store import _client, ensure_collection

    csv_path = Path(csv_path)
    collection_name = PERSONA_COLLECTION_NAME

    if not csv_path.exists():
        raise FileNotFoundError(f"Persona CSV file not found: {csv_path}")

    rows = _read_persona_csv(csv_path)
    if not rows:
        raise ValueError(f"Persona CSV file is empty: {csv_path}")

    # Ensure collection exists (or recreate)
    ensure_collection(name=collection_name, recreate=recreate)

    print(f"\n  {csv_path.name}: {len(rows)} rows -> collection '{collection_name}'")

    # Validate rows
    valid_rows: list[tuple[int, dict]] = []
    skipped = 0

    for i, row in enumerate(rows, start=1):
        is_valid, error_msg = validate_persona_row(row, i)
        if is_valid:
            valid_rows.append((i, row))
        else:
            skipped += 1
            logger.warning(error_msg)

    if not valid_rows:
        print("  No valid rows to ingest.")
        return 0

    # Embed and upsert valid rows
    total_upserted = 0

    for batch_start in range(0, len(valid_rows), UPSERT_BATCH_SIZE):
        batch = valid_rows[batch_start : batch_start + UPSERT_BATCH_SIZE]
        batch_texts = [row_data["persona_text"] for _, row_data in batch]

        # Embed persona_text using Cohere embed-v4 (1024 dimensions)
        embeddings = embed_batch(batch_texts)

        points = []
        for (row_num, row_data), embedding in zip(batch, embeddings):
            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding,
                    payload={
                        "market": row_data["market"],
                        "ethnicity": row_data["ethnicity"],
                        "age_group": row_data["age_group"],
                        "persona_text": row_data["persona_text"],
                        "source": csv_path.name,
                    },
                )
            )

        _client.upsert(collection_name=collection_name, points=points)
        total_upserted += len(points)
        print(
            f"  Upserted {total_upserted}/{len(valid_rows)} "
            f"(Batch {batch_start // UPSERT_BATCH_SIZE + 1})"
        )

        # Give Bedrock API a break between batches
        if batch_start + UPSERT_BATCH_SIZE < len(valid_rows):
            time.sleep(1.0)

    print(f"  Total {total_upserted} vectors upserted to '{collection_name}'")
    if skipped:
        print(f"  {skipped} rows skipped due to validation errors")

    return total_upserted


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest cultural persona narrative CSV rows into Qdrant"
    )
    parser.add_argument(
        "--csv",
        default=None,
        help="Path to persona narratives CSV file (default: data/cultural_personas.csv)",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Drop and recreate the Qdrant collection before ingesting",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv) if args.csv else DEFAULT_PERSONA_CSV

    total = ingest_personas(csv_path, recreate=args.recreate)
    print(f"\nDone -- {total} vectors in Qdrant.")


if __name__ == "__main__":
    main()
