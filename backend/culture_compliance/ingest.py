"""
ingest.py
─────────
CLI script to ingest regulatory guidelines CSV into Qdrant with multi-market support.

Usage:
    # Ingest Malaysia (MCMC) guidelines (default)
    uv run python -m culture_compliance.ingest --market malaysia

    # Ingest Singapore (IMDA/ASAS) guidelines
    uv run python -m culture_compliance.ingest --market singapore

    # Custom CSV path
    uv run python -m culture_compliance.ingest --market singapore --csv path/to/custom.csv

    # Recreate collection before ingesting
    uv run python -m culture_compliance.ingest --market malaysia --recreate
"""

import argparse
from pathlib import Path
from typing import Optional

from .models.schemas import Market
from .nodes.step1_routing import COLLECTION_CONFIG

# Default CSV paths per market
DEFAULT_CSV_PATHS: dict[str, Path] = {
    Market.MALAYSIA: Path(__file__).parent / "data" / "mcmc_guidelines.csv",
    Market.SINGAPORE: Path(__file__).parent / "data" / "singapore_imda_asas_guidelines.csv",
}

# Mapping from MCMC CSV columns to standard metadata fields
MCMC_COLUMN_MAP = {
    "category": "topic_category",
    "rule": "guideline_text",
    "description": "guideline_text_detail",
}


def _resolve_market(market_str: str) -> Market:
    """Resolve a market string to a Market enum value (case-insensitive).

    Args:
        market_str: The market string (e.g., "malaysia", "Singapore").

    Returns:
        The resolved Market enum value.

    Raises:
        ValueError: If the market value is not supported.
    """
    normalized = market_str.strip().lower()
    try:
        return Market(normalized)
    except ValueError:
        supported = [m.value for m in Market]
        raise ValueError(
            f"Unsupported market: '{market_str}'. "
            f"Supported markets are: {supported}"
        )


def _normalize_row_payload(row: dict, market: Market) -> dict:
    """Normalize a CSV row into standard payload metadata.

    Ensures every row has: source_authority, topic_category, guideline_text.

    For Malaysia (MCMC) CSVs that use different column names, maps them
    to the standard schema. For Singapore CSVs that already use the
    standard columns, passes them through.

    Args:
        row: The raw CSV row dict.
        market: The target market.

    Returns:
        A dict with standardized metadata fields.
    """
    config = COLLECTION_CONFIG[market]
    source_authority = config["source_authority"]

    # Check if the row already has the standard columns (Singapore format)
    if "source_authority" in row and "topic_category" in row and "guideline_text" in row:
        return {
            "source_authority": row.get("source_authority", source_authority),
            "topic_category": row.get("topic_category", ""),
            "guideline_text": row.get("guideline_text", ""),
        }

    # Map MCMC-style columns to standard format
    topic_category = row.get("category", "")
    # Combine rule + description for guideline_text
    rule = row.get("rule", "")
    description = row.get("description", "")
    guideline_text = f"{rule}: {description}" if rule and description else rule or description

    return {
        "source_authority": source_authority,
        "topic_category": topic_category,
        "guideline_text": guideline_text,
    }


def ingest_guidelines(csv_path: Path, market: str, recreate: bool = False) -> int:
    """Ingest guidelines CSV into the market-specific Qdrant collection.

    Reads the CSV file, embeds each row using Cohere embed-v4 (1024 dimensions),
    and upserts into the appropriate Qdrant collection based on the market.

    Args:
        csv_path: Path to the CSV file containing guidelines.
        market: Target market string (e.g., "malaysia", "singapore").
        recreate: If True, drop and recreate the collection before ingesting.

    Returns:
        The number of vectors upserted into the collection.

    Raises:
        FileNotFoundError: If the CSV file does not exist.
        ValueError: If the CSV file is empty or the market is unsupported.
    """
    from .qdrant_store import _read_csv, ensure_collection, row_to_text, UPSERT_BATCH_SIZE
    from .embeddings import embed_batch
    from qdrant_client.models import PointStruct

    import uuid
    import time

    # Resolve market
    resolved_market = _resolve_market(market)
    collection_name = COLLECTION_CONFIG[resolved_market]["collection_name"]

    # Validate CSV path
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Guidelines CSV file not found: {csv_path}. "
            f"Please ensure the file exists at the specified path."
        )

    # Read and validate CSV content
    rows = _read_csv(csv_path)
    if not rows:
        raise ValueError(
            f"Guidelines CSV file is empty or contains no valid data rows: {csv_path}. "
            f"The file must contain at least one data row with non-empty values."
        )

    # Ensure collection exists (or recreate)
    ensure_collection(name=collection_name, recreate=recreate)

    print(f"\n📄 {csv_path.name}: {len(rows)} rows → collection '{collection_name}'")

    # Prepare texts for embedding
    texts = [row_to_text(row) for row in rows]
    total_upserted = 0

    # Get Qdrant client
    from .qdrant_store import _client

    for batch_start in range(0, len(texts), UPSERT_BATCH_SIZE):
        batch_texts = texts[batch_start: batch_start + UPSERT_BATCH_SIZE]
        batch_rows = rows[batch_start: batch_start + UPSERT_BATCH_SIZE]
        embeddings = embed_batch(batch_texts)

        points = []
        for row, embedding, text in zip(batch_rows, embeddings, batch_texts):
            # Normalize payload metadata
            metadata = _normalize_row_payload(row, resolved_market)

            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding,
                    payload={
                        "source": csv_path.name,
                        "row_text": text,
                        **metadata,
                        # Also preserve original row data
                        **{k: v for k, v in row.items()
                           if k not in ("source_authority", "topic_category", "guideline_text")},
                    },
                )
            )

        _client.upsert(collection_name=collection_name, points=points)
        total_upserted += len(points)
        print(
            f"  ✅ Upserted {total_upserted}/{len(rows)} "
            f"(Batch {batch_start // UPSERT_BATCH_SIZE + 1})"
        )

        # Give Bedrock API a break between batches
        if batch_start + UPSERT_BATCH_SIZE < len(rows):
            time.sleep(1.0)

    print(f"  🎉 Total {total_upserted} vectors upserted to '{collection_name}'")
    return total_upserted


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest regulatory guideline CSV rows into Qdrant (multi-market)"
    )
    parser.add_argument(
        "--market",
        default="malaysia",
        help="Target market: 'malaysia' or 'singapore' (default: malaysia)",
    )
    parser.add_argument(
        "--csv",
        default=None,
        help="Path to CSV file (default: auto-selected based on market)",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Drop and recreate the Qdrant collection before ingesting",
    )
    args = parser.parse_args()

    # Resolve CSV path
    if args.csv:
        csv_path = Path(args.csv)
    else:
        resolved_market = _resolve_market(args.market)
        csv_path = DEFAULT_CSV_PATHS[resolved_market]

    total = ingest_guidelines(csv_path, market=args.market, recreate=args.recreate)
    print(f"\n✅ Done — {total} vectors in Qdrant.")


if __name__ == "__main__":
    main()
