"""
ingest.py
─────────
Standalone script to ingest the nano-banana-pro-prompts CSV into Qdrant.

Run from backend/:
    python -m jusads_generation.prompt_search.ingest

Options:
    --recreate    Drop and recreate the collection before ingesting.
"""

import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

# Load dotenv before anything else.
from dotenv import load_dotenv
load_dotenv()

from jusads_generation.prompt_search.qdrant_store import ingest_prompts_csv

# Default CSV path (backend/data/).
CSV_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "nano-banana-pro-prompts-20260701.csv"


def main():
    recreate = "--recreate" in sys.argv

    csv_path = CSV_PATH
    if not csv_path.exists():
        print(f"ERROR: CSV not found at {csv_path}")
        print("Place nano-banana-pro-prompts-20260701.csv in the project root.")
        sys.exit(1)

    print(f"{'RECREATING' if recreate else 'UPSERTING INTO'} collection...")
    print(f"CSV: {csv_path}")
    print()

    total = ingest_prompts_csv(csv_path, recreate=recreate)
    print(f"\n✅ Done! {total} prompts ingested into Qdrant.")


if __name__ == "__main__":
    main()
