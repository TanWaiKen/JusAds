"""
refresh_events.py
─────────────────
Update cultural_events table with fresh event data from PredictHQ API.

Fetches upcoming events for Malaysia and globally, then upserts them
into the cultural_events Supabase table. Falls back to mock events
if PREDICTHQ_API_KEY is not configured.

Usage:
  cd backend
  .venv/Scripts/python scripts/manual/refresh_events.py

Requires: SUPABASE_URL + SUPABASE_KEY in .env
Optional: PREDICTHQ_API_KEY in .env (uses mock data without it)
"""

import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv(".env", override=True)

from shared.clients import supabase
from shared.predicthq_client import fetch_predicthq_events
from shared.config import PREDICTHQ_API_KEY


def main() -> None:
    """Fetch events from PredictHQ and upsert into cultural_events table."""
    print("=" * 60)
    print("  Cultural Events Refresh (PredictHQ Integration)")
    print("=" * 60)

    if not supabase:
        print("\n❌ ERROR: Supabase not connected")
        sys.exit(1)

    # Show current state
    resp = supabase.table("cultural_events").select("id", count="exact").execute()
    current_count = resp.count if hasattr(resp, 'count') else len(resp.data or [])
    print(f"\n📊 Current events in DB: {current_count}")

    if PREDICTHQ_API_KEY:
        print("🔑 PredictHQ API key found — fetching real events...")
    else:
        print("⚠️  No PREDICTHQ_API_KEY — using mock/fallback events")

    # Fetch events from PredictHQ (or mock fallback)
    print("\n🌏 Fetching Malaysia (MY) events...")
    my_events = asyncio.run(fetch_predicthq_events(country_code="MY", days_ahead=60))
    print(f"   → Got {len(my_events)} Malaysia events")

    print("🌐 Fetching global events...")
    global_events = asyncio.run(fetch_predicthq_events(country_code=None, days_ahead=60))
    # Filter out duplicates that are already in MY events
    my_names = {e["name"] for e in my_events}
    global_events = [e for e in global_events if e["name"] not in my_names]
    print(f"   → Got {len(global_events)} global events")

    all_events = my_events + global_events
    print(f"\n📥 Total events to upsert: {len(all_events)}")

    if not all_events:
        print("⚠️  No events fetched. Skipping upsert.")
        _show_upcoming()
        return

    # Upsert into Supabase (use name + market + start_date as unique key)
    inserted = 0
    skipped = 0
    for event in all_events:
        try:
            # Check if event already exists
            existing = (
                supabase.table("cultural_events")
                .select("id")
                .eq("name", event["name"])
                .eq("market", event["market"])
                .eq("start_date", event["start_date"])
                .execute()
            )

            if existing.data:
                # Update existing
                supabase.table("cultural_events").update({
                    "end_date": event["end_date"],
                    "event_type": event["event_type"],
                    "tags": event["tags"],
                    "impact_score": event["impact_score"],
                }).eq("id", existing.data[0]["id"]).execute()
                skipped += 1
            else:
                # Insert new
                supabase.table("cultural_events").insert(event).execute()
                inserted += 1
        except Exception as e:
            print(f"   ⚠️  Failed to upsert '{event['name']}': {e}")

    print(f"\n✅ Upsert complete: {inserted} new, {skipped} updated")

    # Show upcoming events
    _show_upcoming()


def _show_upcoming() -> None:
    """Display upcoming events from the database."""
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    resp = (
        supabase.table("cultural_events")
        .select("name, market, start_date, end_date, event_type, impact_score")
        .gte("end_date", today)
        .order("start_date", desc=False)
        .limit(25)
        .execute()
    )
    events = resp.data or []

    print(f"\n📅 Upcoming events in DB ({len(events)}):\n")
    print(f"  {'Name':<35} {'Market':<10} {'Dates':<25} {'Type':<10} {'Impact'}")
    print("  " + "-" * 95)
    for e in events:
        dates = f"{e['start_date']} → {e['end_date']}"
        print(f"  {e['name']:<35} {e['market']:<10} {dates:<25} {e['event_type']:<10} {e['impact_score']}/100")

    print(f"\n🎯 Done. Run this script periodically to keep events fresh.")


if __name__ == "__main__":
    main()
