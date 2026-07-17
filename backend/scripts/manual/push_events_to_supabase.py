"""
push_events_to_supabase.py
──────────────────────────
Push all events from cultural_events_sea_full_2026.csv into the
Supabase cultural_events table, deduplicating by name + start_date.

Usage:
  cd backend
  .venv/Scripts/python scripts/manual/push_events_to_supabase.py
"""

import sys
import os
import csv


if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv(".env", override=True)

from shared.clients import supabase


def main() -> None:
    """Push CSV events to Supabase, deduplicating against existing rows."""
    print("=" * 60)
    print("  Push Cultural Events CSV → Supabase")
    print("=" * 60)

    if not supabase:
        print("\n❌ ERROR: Supabase not connected")
        sys.exit(1)

    # Read CSV
    csv_path = "data/cultural_events_sea_full_2026.csv"
    if not os.path.exists(csv_path):
        print(f"\n❌ CSV not found: {csv_path}")
        sys.exit(1)

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        csv_events = list(reader)

    print(f"\n📄 CSV contains {len(csv_events)} events")

    # Fetch existing events from Supabase
    print("📡 Fetching existing events from Supabase...")
    response = supabase.table("cultural_events").select("name, start_date, market").execute()
    existing = {
        (r["name"].lower().strip(), str(r["start_date"]), r["market"].lower().strip())
        for r in (response.data or [])
    }
    print(f"   → {len(existing)} events already in DB")

    # Prepare events to insert
    to_insert = []
    skipped = 0

    for row in csv_events:
        key = (
            row["name"].lower().strip(),
            row["start_date"].strip(),
            row["market"].lower().strip(),
        )
        if key in existing:
            skipped += 1
            continue

        # Convert tags from pipe-separated string to array
        tags_str = row.get("tags", "")
        tags = [t.strip() for t in tags_str.split("|") if t.strip()] if tags_str else []

        to_insert.append({
            "name": row["name"].strip(),
            "market": row["market"].strip().lower(),
            "start_date": row["start_date"].strip(),
            "end_date": row["end_date"].strip(),
            "event_type": row["event_type"].strip(),
            "tags": tags,
            "impact_score": int(row.get("impact_score", 50)),
        })

    print(f"\n📊 To insert: {len(to_insert)} new events (skipping {skipped} duplicates)")

    if not to_insert:
        print("✅ Database already up to date. Nothing to insert.")
        return

    # Batch insert (Supabase handles up to ~1000 at a time)
    batch_size = 50
    inserted_total = 0

    for i in range(0, len(to_insert), batch_size):
        batch = to_insert[i:i + batch_size]
        try:
            supabase.table("cultural_events").insert(batch).execute()
            inserted_total += len(batch)
            print(f"   ✅ Inserted batch {i // batch_size + 1}: {len(batch)} events")
        except Exception as e:
            print(f"   ⚠️  Batch {i // batch_size + 1} failed: {e}")
            # Try one-by-one for failed batch
            for event in batch:
                try:
                    supabase.table("cultural_events").insert(event).execute()
                    inserted_total += 1
                except Exception as e2:
                    print(f"      ❌ Failed: {event['name']} — {e2}")

    print(f"\n✅ Done! Inserted {inserted_total} events into Supabase.")

    # Show final count
    resp = supabase.table("cultural_events").select("id", count="exact").execute()
    total = resp.count if hasattr(resp, 'count') else len(resp.data or [])
    print(f"📊 Total events now in DB: {total}")


if __name__ == "__main__":
    main()
