"""
ingest_cultural.py
──────────────────
CLI script to ingest cultural guidelines CSV into the dedicated
'cultural-guidelines' Qdrant collection.

Usage:
    # Ingest cultural guidelines (default CSV path)
    uv run python -m culture_compliance.ingest_cultural

    # Custom CSV path
    uv run python -m culture_compliance.ingest_cultural --csv path/to/cultural.csv

    # Recreate collection before ingesting
    uv run python -m culture_compliance.ingest_cultural --recreate
"""

import argparse
import csv
import logging
import time
import uuid
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, ValidationError
from qdrant_client.models import PointStruct

from config import CULTURAL_COLLECTION_NAME, CULTURAL_COLLECTION_CONFIG
from .models.cultural_schemas import GuidelineEntry

logger = logging.getLogger(__name__)

# Default CSV path for cultural guidelines
DEFAULT_CULTURAL_CSV = Path(__file__).parent / "data" / "cultural_guidelines.csv"

# Batch size for embedding and upsert operations
UPSERT_BATCH_SIZE = 20


# ── Result Model ──────────────────────────────────────────────────────────────


class IngestionResult(BaseModel):
    """Result of cultural guideline ingestion."""

    total_ingested: int
    rows_skipped: int
    collection_name: str
    errors: list[dict] = Field(default_factory=list)


# ── Validation ────────────────────────────────────────────────────────────────


def validate_guideline_row(row: dict, row_number: int) -> tuple[bool, Optional[str]]:
    """Validate a single CSV row against GuidelineEntry schema.

    Args:
        row: A dictionary representing a single CSV row with keys matching
             GuidelineEntry fields.
        row_number: The 1-based row number in the CSV file (for error reporting).

    Returns:
        A tuple of (is_valid, error_message_or_none).
        If valid, returns (True, None).
        If invalid, returns (False, descriptive_error_message).
    """
    try:
        GuidelineEntry(**row)
        return True, None
    except ValidationError as e:
        # Extract the first error for a concise message
        first_error = e.errors()[0]
        field = first_error["loc"][0] if first_error["loc"] else "unknown"
        value = row.get(str(field), "")
        reason = first_error["msg"]
        error_msg = f"Row {row_number}: Invalid {field} value '{value}'. {reason}"
        return False, error_msg


# ── Ingestion ─────────────────────────────────────────────────────────────────


def ingest_cultural_guidelines(
    csv_path: Path, recreate: bool = False
) -> IngestionResult:
    """Ingest cultural guidelines CSV into the 'cultural-guidelines' Qdrant collection.

    Reads the CSV file, validates each row against the GuidelineEntry schema,
    embeds valid guideline_text using Cohere embed-v4 (1024 dimensions) via
    AWS Bedrock, and upserts into the cultural-guidelines Qdrant collection.

    Args:
        csv_path: Path to the cultural guidelines CSV file.
        recreate: If True, drop and recreate the collection before ingesting.

    Returns:
        IngestionResult with total_ingested, rows_skipped, collection_name,
        and errors list.
    """
    from .embeddings import embed_batch
    from .qdrant_store import _client, ensure_collection

    csv_path = Path(csv_path)
    collection_name = CULTURAL_COLLECTION_NAME

    # Handle file-not-found error case
    if not csv_path.exists():
        logger.error(f"Cultural guidelines CSV file not found: {csv_path}")
        return IngestionResult(
            total_ingested=0,
            rows_skipped=0,
            collection_name=collection_name,
            errors=[
                {
                    "row": 0,
                    "field": "file",
                    "value": str(csv_path),
                    "reason": "File not found",
                }
            ],
        )

    # Read CSV rows
    rows = _read_cultural_csv(csv_path)

    # Handle empty-file error case
    if not rows:
        logger.error(f"Cultural guidelines CSV file is empty: {csv_path}")
        return IngestionResult(
            total_ingested=0,
            rows_skipped=0,
            collection_name=collection_name,
            errors=[
                {
                    "row": 0,
                    "field": "file",
                    "value": str(csv_path),
                    "reason": "File is empty or contains no data rows",
                }
            ],
        )

    # Ensure collection exists (or recreate)
    ensure_collection(name=collection_name, recreate=recreate)

    print(f"\n📄 {csv_path.name}: {len(rows)} rows → collection '{collection_name}'")

    # Validate rows and separate valid from invalid
    valid_rows: list[tuple[int, dict]] = []  # (row_number, row_data)
    errors: list[dict] = []
    rows_skipped = 0

    for i, row in enumerate(rows, start=1):
        is_valid, error_msg = validate_guideline_row(row, i)
        if is_valid:
            valid_rows.append((i, row))
        else:
            rows_skipped += 1
            logger.warning(error_msg)
            # Parse error details for the errors list
            try:
                entry = GuidelineEntry(**row)
            except ValidationError as e:
                first_error = e.errors()[0]
                field = str(first_error["loc"][0]) if first_error["loc"] else "unknown"
                value = row.get(field, "")
                reason = first_error["msg"]
                errors.append(
                    {
                        "row": i,
                        "field": field,
                        "value": str(value),
                        "reason": reason,
                    }
                )

    if not valid_rows:
        print("  ⚠️  No valid rows to ingest.")
        return IngestionResult(
            total_ingested=0,
            rows_skipped=rows_skipped,
            collection_name=collection_name,
            errors=errors,
        )

    # Embed and upsert valid rows in batches
    total_upserted = 0

    for batch_start in range(0, len(valid_rows), UPSERT_BATCH_SIZE):
        batch = valid_rows[batch_start : batch_start + UPSERT_BATCH_SIZE]
        batch_texts = [row_data["guideline_text"] for _, row_data in batch]

        # Embed guideline_text using Cohere embed-v4 (1024 dimensions)
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
                        "category": row_data["category"],
                        "severity": row_data["severity"],
                        "guideline_text": row_data["guideline_text"],
                        "source": csv_path.name,
                    },
                )
            )

        _client.upsert(collection_name=collection_name, points=points)
        total_upserted += len(points)
        print(
            f"  ✅ Upserted {total_upserted}/{len(valid_rows)} "
            f"(Batch {batch_start // UPSERT_BATCH_SIZE + 1})"
        )

        # Give Bedrock API a break between batches
        if batch_start + UPSERT_BATCH_SIZE < len(valid_rows):
            time.sleep(1.0)

    print(f"  🎉 Total {total_upserted} vectors upserted to '{collection_name}'")
    if rows_skipped:
        print(f"  ⚠️  {rows_skipped} rows skipped due to validation errors")

    return IngestionResult(
        total_ingested=total_upserted,
        rows_skipped=rows_skipped,
        collection_name=collection_name,
        errors=errors,
    )


# ── CSV Reading ───────────────────────────────────────────────────────────────


def _read_cultural_csv(path: Path) -> list[dict]:
    """Read a cultural guidelines CSV and return list of cleaned row dicts.

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


# ── CLI Entry Point ───────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest cultural guideline CSV rows into Qdrant"
    )
    parser.add_argument(
        "--csv",
        default=None,
        help="Path to cultural guidelines CSV file (default: data/cultural_guidelines.csv)",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Drop and recreate the Qdrant collection before ingesting",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv) if args.csv else DEFAULT_CULTURAL_CSV

    result = ingest_cultural_guidelines(csv_path, recreate=args.recreate)

    print(f"\n✅ Done — {result.total_ingested} vectors in Qdrant.")
    if result.rows_skipped:
        print(f"⚠️  {result.rows_skipped} rows skipped.")
    if result.errors:
        print(f"❌ {len(result.errors)} errors encountered:")
        for err in result.errors:
            print(f"   Row {err['row']}: {err['field']} = '{err['value']}' — {err['reason']}")


if __name__ == "__main__":
    main()
