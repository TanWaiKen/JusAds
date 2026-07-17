#!/usr/bin/env python3
"""
seed_supabase.py
────────────────
Seed regulatory rules (from CSV), personas (from JSON), and platform format
rules into Supabase.

Usage:
    cd backend
    python -m migrations.scripts.seed_supabase
    python -m migrations.scripts.seed_supabase --rules-only
    python -m migrations.scripts.seed_supabase --personas-only
    python -m migrations.scripts.seed_supabase --platform-rules
"""

import csv
import json
import logging
import sys
import argparse
from datetime import datetime
from pathlib import Path

# Add backend/ to path so config imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

# -- Paths ---------------------------------------------------------------------
CSV_PATH = Path(__file__).resolve().parent / "regulatory_rules_vector_db_dataset.csv"
PERSONAS_DIR = Path(__file__).resolve().parent.parent / "personas"
PERSONA_FILES = {
    "malaysia": PERSONAS_DIR / "malaysia_personas.json",
    "singapore": PERSONAS_DIR / "singapore_personas.json",
}

BATCH_SIZE = 50


def _parse_date(date_str: str) -> str:
    """Convert date string to ISO format (yyyy-mm-dd).

    Handles formats: d/m/yyyy, dd/mm/yyyy, yyyy-mm-dd.
    Falls back to 1970-01-01 on failure.
    """
    if not date_str or not date_str.strip():
        return "1970-01-01"
    date_str = date_str.strip()
    # Already ISO format
    if len(date_str) == 10 and date_str[4] == "-":
        return date_str
    # Try d/m/yyyy or dd/mm/yyyy
    for fmt in ("%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return "1970-01-01"

# -- Platform Rules Data -------------------------------------------------------
PLATFORM_RULES_DATA = [
    # -- TikTok ----------------------------------------------------------------
    {"platform": "TikTok", "media_type": "video", "aspect_ratio": "9:16", "max_duration_seconds": 600, "max_file_size_mb": 500},
    {"platform": "TikTok", "media_type": "video", "aspect_ratio": "1:1", "max_duration_seconds": 600, "max_file_size_mb": 500},
    {"platform": "TikTok", "media_type": "video", "aspect_ratio": "16:9", "max_duration_seconds": 600, "max_file_size_mb": 500},
    {"platform": "TikTok", "media_type": "image", "aspect_ratio": "9:16", "max_duration_seconds": None, "max_file_size_mb": 20},
    {"platform": "TikTok", "media_type": "image", "aspect_ratio": "1:1", "max_duration_seconds": None, "max_file_size_mb": 20},
    # -- Instagram -------------------------------------------------------------
    {"platform": "Instagram", "media_type": "video", "aspect_ratio": "9:16", "max_duration_seconds": 90, "max_file_size_mb": 4000},
    {"platform": "Instagram", "media_type": "video", "aspect_ratio": "1:1", "max_duration_seconds": 90, "max_file_size_mb": 4000},
    {"platform": "Instagram", "media_type": "video", "aspect_ratio": "4:5", "max_duration_seconds": 90, "max_file_size_mb": 4000},
    {"platform": "Instagram", "media_type": "video", "aspect_ratio": "16:9", "max_duration_seconds": 90, "max_file_size_mb": 4000},
    {"platform": "Instagram", "media_type": "image", "aspect_ratio": "1:1", "max_duration_seconds": None, "max_file_size_mb": 30},
    {"platform": "Instagram", "media_type": "image", "aspect_ratio": "9:16", "max_duration_seconds": None, "max_file_size_mb": 30},
    {"platform": "Instagram", "media_type": "image", "aspect_ratio": "4:5", "max_duration_seconds": None, "max_file_size_mb": 30},
    {"platform": "Instagram", "media_type": "image", "aspect_ratio": "1.91:1", "max_duration_seconds": None, "max_file_size_mb": 30},
    # -- Meta (Facebook) -------------------------------------------------------
    {"platform": "Meta", "media_type": "video", "aspect_ratio": "16:9", "max_duration_seconds": 240, "max_file_size_mb": 4000},
    {"platform": "Meta", "media_type": "video", "aspect_ratio": "1:1", "max_duration_seconds": 240, "max_file_size_mb": 4000},
    {"platform": "Meta", "media_type": "video", "aspect_ratio": "9:16", "max_duration_seconds": 120, "max_file_size_mb": 4000},
    {"platform": "Meta", "media_type": "video", "aspect_ratio": "4:5", "max_duration_seconds": 240, "max_file_size_mb": 4000},
    {"platform": "Meta", "media_type": "image", "aspect_ratio": "1:1", "max_duration_seconds": None, "max_file_size_mb": 30},
    {"platform": "Meta", "media_type": "image", "aspect_ratio": "1.91:1", "max_duration_seconds": None, "max_file_size_mb": 30},
    {"platform": "Meta", "media_type": "image", "aspect_ratio": "4:5", "max_duration_seconds": None, "max_file_size_mb": 30},
    # -- YouTube ---------------------------------------------------------------
    {"platform": "YouTube", "media_type": "video", "aspect_ratio": "16:9", "max_duration_seconds": 43200, "max_file_size_mb": 256000},
    {"platform": "YouTube", "media_type": "video", "aspect_ratio": "9:16", "max_duration_seconds": 60, "max_file_size_mb": 256000},
    {"platform": "YouTube", "media_type": "video", "aspect_ratio": "1:1", "max_duration_seconds": 43200, "max_file_size_mb": 256000},
    {"platform": "YouTube", "media_type": "image", "aspect_ratio": "16:9", "max_duration_seconds": None, "max_file_size_mb": 2},
    # -- X (Twitter) -----------------------------------------------------------
    {"platform": "X", "media_type": "video", "aspect_ratio": "16:9", "max_duration_seconds": 140, "max_file_size_mb": 512},
    {"platform": "X", "media_type": "video", "aspect_ratio": "1:1", "max_duration_seconds": 140, "max_file_size_mb": 512},
    {"platform": "X", "media_type": "video", "aspect_ratio": "9:16", "max_duration_seconds": 140, "max_file_size_mb": 512},
    {"platform": "X", "media_type": "image", "aspect_ratio": "16:9", "max_duration_seconds": None, "max_file_size_mb": 5},
    {"platform": "X", "media_type": "image", "aspect_ratio": "1:1", "max_duration_seconds": None, "max_file_size_mb": 5},
    {"platform": "X", "media_type": "image", "aspect_ratio": "4:5", "max_duration_seconds": None, "max_file_size_mb": 5},
    # -- Shopee ----------------------------------------------------------------
    {"platform": "Shopee", "media_type": "image", "aspect_ratio": "1:1", "max_duration_seconds": None, "max_file_size_mb": 2},
    {"platform": "Shopee", "media_type": "video", "aspect_ratio": "1:1", "max_duration_seconds": 60, "max_file_size_mb": 30},
    {"platform": "Shopee", "media_type": "video", "aspect_ratio": "9:16", "max_duration_seconds": 60, "max_file_size_mb": 30},
]


def get_supabase():
    """Initialize Supabase client; exits non-zero on connection failure."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ SUPABASE_URL and SUPABASE_KEY must be set in .env")
        sys.exit(1)
    try:
        return create_client(supabase_url=SUPABASE_URL, supabase_key=SUPABASE_KEY)
    except Exception as e:
        print(f"❌ Failed to connect to Supabase: {e}")
        sys.exit(1)


def seed_rules(client) -> tuple[int, int]:
    """Load rules from CSV and upsert into ad_policy_rules table.

    Returns:
        Tuple of (upserted_count, failed_batch_count).
    """
    if not CSV_PATH.exists():
        print(f"❌ CSV file not found: {CSV_PATH}")
        sys.exit(1)

    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"📄 Loaded {len(rows)} rules from {CSV_PATH.name}")

    total = 0
    failed_batches = 0
    for batch_start in range(0, len(rows), BATCH_SIZE):
        batch = rows[batch_start:batch_start + BATCH_SIZE]

        records = []
        for row in batch:
            records.append({
                "id": row["id"],
                "source": row["source"].strip().lower(),
                "regulator": row.get("regulator", ""),
                "framework": row.get("framework", ""),
                "category": row.get("category", ""),
                "rule_title": row.get("rule_title", ""),
                "rule_text": row.get("rule_text", ""),
                "applies_to": row.get("applies_to", ""),
                "enforcement": row.get("enforcement", ""),
                "effective_date": _parse_date(row.get("effective_date", "")),
                "last_updated": _parse_date(row.get("last_updated", "")),
                "tags": row.get("tags", ""),
            })

        try:
            client.table("ad_policy_rules").upsert(records, on_conflict="id").execute()
            total += len(records)
            print(f"  ↑ Upserted batch {batch_start // BATCH_SIZE + 1} ({len(records)} rules)")
        except Exception as e:
            failed_batches += 1
            logger.error(
                "[seed_rules] Batch %d failed: %s",
                batch_start // BATCH_SIZE + 1,
                e,
            )
            print(f"  ❌ Batch {batch_start // BATCH_SIZE + 1} failed: {e}")

    return total, failed_batches


def seed_personas(client) -> tuple[int, int]:
    """Load personas from JSON files and upsert into personas table.

    Returns:
        Tuple of (upserted_count, failed_batch_count).
    """
    total = 0
    failed_batches = 0

    for market, filepath in PERSONA_FILES.items():
        if not filepath.exists():
            print(f"❌ Persona file not found: {filepath}")
            sys.exit(1)

        data = json.loads(filepath.read_text(encoding="utf-8"))
        print(f"📄 Loading personas for {market} from {filepath.name}")

        # Skip _meta key, iterate over ethnicities
        for ethnicity, persona_data in data.items():
            if ethnicity.startswith("_"):
                continue

            records = []

            # Insert base persona (without age group specifics)
            base_data = {k: v for k, v in persona_data.items() if k != "age_groups"}
            records.append({
                "market": market.lower(),
                "ethnicity": ethnicity.lower(),
                "age_group": "base",
                "persona_data": base_data,
            })

            # Insert age-group-specific personas
            age_groups = persona_data.get("age_groups", {})
            for age_key, age_data in age_groups.items():
                # Merge base + age-specific for a complete persona at each age group
                merged = {**base_data, "age_group_details": age_data}
                records.append({
                    "market": market.lower(),
                    "ethnicity": ethnicity.lower(),
                    "age_group": age_key.lower(),
                    "persona_data": merged,
                })

            try:
                client.table("personas").upsert(
                    records, on_conflict="market,ethnicity,age_group"
                ).execute()
                total += len(records)
                print(f"  ↑ Upserted {len(records)} personas for {market}/{ethnicity}")
            except Exception as e:
                failed_batches += 1
                logger.error(
                    "[seed_personas] Failed for %s/%s: %s",
                    market,
                    ethnicity,
                    e,
                )
                print(f"  ❌ Failed for {market}/{ethnicity}: {e}")

    return total, failed_batches


def seed_platform_rules(client) -> tuple[int, int]:
    """Upsert platform format rules into the platform_rules table.

    Uses the unique constraint on (platform, media_type, aspect_ratio) to
    perform upsert (insert or update on conflict).

    Returns:
        Tuple of (upserted_count, failed_batch_count).
    """
    print(f"📄 Seeding {len(PLATFORM_RULES_DATA)} platform rules")

    total = 0
    failed_batches = 0

    for batch_start in range(0, len(PLATFORM_RULES_DATA), BATCH_SIZE):
        batch = PLATFORM_RULES_DATA[batch_start:batch_start + BATCH_SIZE]

        try:
            client.table("platform_rules").upsert(
                batch, on_conflict="platform,media_type,aspect_ratio"
            ).execute()
            total += len(batch)
            print(f"  ↑ Upserted batch {batch_start // BATCH_SIZE + 1} ({len(batch)} platform rules)")
        except Exception as e:
            failed_batches += 1
            logger.error(
                "[seed_platform_rules] Batch %d failed: %s",
                batch_start // BATCH_SIZE + 1,
                e,
            )
            print(f"  ❌ Batch {batch_start // BATCH_SIZE + 1} failed: {e}")

    return total, failed_batches


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Seed Supabase with rules, personas, and platform rules")
    parser.add_argument("--rules-only", action="store_true", help="Seed only regulatory rules")
    parser.add_argument("--personas-only", action="store_true", help="Seed only personas")
    parser.add_argument("--platform-rules", action="store_true", help="Seed only platform format rules")
    args = parser.parse_args()

    client = get_supabase()
    print("🔗 Connected to Supabase\n")

    rules_count = 0
    personas_count = 0
    platform_rules_count = 0
    total_failed_batches = 0

    # Determine what to seed based on flags
    seed_all = not args.rules_only and not args.personas_only and not args.platform_rules

    if args.rules_only or seed_all:
        print("━━━ Seeding Rules ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        rules_count, failed = seed_rules(client)
        total_failed_batches += failed
        print()

    if args.personas_only or seed_all:
        print("━━━ Seeding Personas ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        personas_count, failed = seed_personas(client)
        total_failed_batches += failed
        print()

    if args.platform_rules or seed_all:
        print("━━━ Seeding Platform Rules ━━━━━━━━━━━━━━━━━━━━━━━━━")
        platform_rules_count, failed = seed_platform_rules(client)
        total_failed_batches += failed
        print()

    # Print summary
    print(
        f"✅ Done! Rules: {rules_count}, Personas: {personas_count}, "
        f"Platform Rules: {platform_rules_count}"
    )
    if total_failed_batches > 0:
        print(f"⚠️  {total_failed_batches} batch(es) failed during seeding.")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
