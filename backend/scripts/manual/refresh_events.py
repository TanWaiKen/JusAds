"""
refresh_events.py
─────────────────
Update cultural_events table with fresh event data.

Currently uses a manual list. Future: integrate PredictHQ API or
Google Calendar API for dynamic updates.

Usage:
  cd backend
  .venv/Scripts/python scripts/manual/refresh_events.py

Requires: SUPABASE_URL + SUPABASE_KEY in .env
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv(".env", override=True)

from shared.clients import supabase


def main():
    print("=" * 50)
    print("Manual Cultural Events Refresh")
    print("=" * 50)

    if not supabase:
        print("\n❌ ERROR: Supabase not connected")
        sys.exit(1)

    # Check current count
    resp = supabase.table("cultural_events").select("id", count="exact").execute()
    current_count = resp.count if hasattr(resp, 'count') else len(resp.data or [])
    print(f"\n📊 Current events in DB: {current_count}")

    # The events are seeded via migration 020.
    # To add more, either:
    # 1. Run the migration SQL INSERT again with new events
    # 2. Or add them here manually:

    # Example: add new event
    # supabase.table("cultural_events").insert({
    #     "name": "New Event",
    #     "market": "malaysia",
    #     "start_date": "2026-12-01",
    #     "end_date": "2026-12-03",
    #     "event_type": "global",
    #     "tags": ["shopping", "deals"],
    #     "impact_score": 75,
    # }).execute()

    # List upcoming events
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    resp = (
        supabase.table("cultural_events")
        .select("name, market, start_date, end_date, event_type, impact_score")
        .gte("end_date", today)
        .order("start_date", desc=False)
        .limit(20)
        .execute()
    )
    events = resp.data or []

    print(f"\n📅 Upcoming events ({len(events)}):\n")
    print(f"{'Name':<30} {'Market':<12} {'Dates':<25} {'Type':<12} {'Impact'}")
    print("-" * 95)
    for e in events:
        print(f"{e['name']:<30} {e['market']:<12} {e['start_date']} → {e['end_date']:<10} {e['event_type']:<12} {e['impact_score']}/100")

    print(f"\n✅ Done. To add events, edit this script or run migration SQL.")


if __name__ == "__main__":
    main()
