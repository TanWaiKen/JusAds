"""
fetch_sea_events.py
───────────────────
Fetch cultural events from PredictHQ API for Malaysia (primary),
Southeast Asia, and globally popular festivals/events.

Saves results to backend/data/cultural_events_sea.csv

Usage:
  cd backend
  .venv/Scripts/python scripts/manual/fetch_sea_events.py
"""

import sys
import os
import csv
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv(".env", override=True)

import httpx
from shared.config import PREDICTHQ_API_KEY

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Countries to fetch
SEA_COUNTRIES = {
    "MY": "malaysia",
    "TH": "thailand",
    "SG": "singapore",
    "ID": "indonesia",
    "VN": "vietnam",
    "PH": "philippines",
}

# PredictHQ categories mapping
CATEGORY_MAPPING = {
    "sports": "sports",
    "festivals": "festive",
    "concerts": "festive",
    "expos": "global",
    "conferences": "global",
    "public-holidays": "national",
    "school-holidays": "national",
    "observances": "religious",
    "community": "global",
    "performing-arts": "festive",
    "daylight-savings": "national",
}

CATEGORIES = [
    "festivals", "sports", "public-holidays", "concerts",
    "expos", "conferences", "observances", "performing-arts",
]


def map_category(category: str) -> str:
    """Map PredictHQ category to local event_type."""
    return CATEGORY_MAPPING.get(category.lower(), "global")


async def fetch_events_for_country(
    country_code: str,
    days_ahead: int = 180,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Fetch events for a specific country from PredictHQ."""
    now = datetime.now(timezone.utc)
    start_date = now.strftime("%Y-%m-%d")
    end_date = (now + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    url = "https://api.predicthq.com/v1/events/"
    headers = {
        "Authorization": f"Bearer {PREDICTHQ_API_KEY}",
        "Accept": "application/json",
    }
    params = {
        "active.gte": start_date,
        "active.lte": end_date,
        "category": ",".join(CATEGORIES),
        "country": country_code.upper(),
        "limit": limit,
        "sort": "rank",  # Most impactful first
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, params=params, timeout=20.0)
        if resp.status_code != 200:
            logger.error(f"  ❌ {country_code}: API returned {resp.status_code}")
            return []

        data = resp.json()
        results = data.get("results", [])

        events = []
        for r in results:
            # Get end date, fallback to start + 1 day
            event_end = r.get("end")
            event_start = r.get("start", start_date)[:10]
            if event_end:
                event_end = event_end[:10]
            else:
                event_end = event_start

            events.append({
                "name": r.get("title", "Unknown"),
                "market": SEA_COUNTRIES.get(country_code.upper(), country_code.lower()),
                "country_code": country_code.upper(),
                "start_date": event_start,
                "end_date": event_end,
                "event_type": map_category(r.get("category", "community")),
                "category_raw": r.get("category", ""),
                "tags": "|".join(r.get("labels", [])),
                "impact_score": min(r.get("rank", 50), 100),
                "description": r.get("description", "")[:200],
            })

        return events


async def fetch_global_popular(days_ahead: int = 180) -> List[Dict[str, Any]]:
    """Fetch globally popular events (high rank, no country filter)."""
    now = datetime.now(timezone.utc)
    start_date = now.strftime("%Y-%m-%d")
    end_date = (now + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    url = "https://api.predicthq.com/v1/events/"
    headers = {
        "Authorization": f"Bearer {PREDICTHQ_API_KEY}",
        "Accept": "application/json",
    }
    params = {
        "active.gte": start_date,
        "active.lte": end_date,
        "category": ",".join(CATEGORIES),
        "rank.gte": 70,  # Only high-impact global events
        "limit": 50,
        "sort": "rank",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, params=params, timeout=20.0)
        if resp.status_code != 200:
            logger.error(f"  ❌ Global: API returned {resp.status_code}")
            return []

        data = resp.json()
        results = data.get("results", [])

        events = []
        for r in results:
            event_end = r.get("end")
            event_start = r.get("start", start_date)[:10]
            if event_end:
                event_end = event_end[:10]
            else:
                event_end = event_start

            country = r.get("country", "")
            events.append({
                "name": r.get("title", "Unknown"),
                "market": "global",
                "country_code": country.upper() if country else "GLOBAL",
                "start_date": event_start,
                "end_date": event_end,
                "event_type": map_category(r.get("category", "community")),
                "category_raw": r.get("category", ""),
                "tags": "|".join(r.get("labels", [])),
                "impact_score": min(r.get("rank", 50), 100),
                "description": r.get("description", "")[:200],
            })

        return events


async def main() -> None:
    """Fetch all events and save to CSV."""
    print("=" * 60)
    print("  PredictHQ Event Fetcher — Malaysia + SEA + Global")
    print("=" * 60)

    if not PREDICTHQ_API_KEY:
        print("\n❌ PREDICTHQ_API_KEY not set in .env")
        sys.exit(1)

    all_events: List[Dict[str, Any]] = []

    # 1. Fetch Malaysia (primary — more days, higher limit)
    print("\n🇲🇾 Fetching Malaysia events (180 days, up to 100)...")
    my_events = await fetch_events_for_country("MY", days_ahead=180, limit=100)
    print(f"   → {len(my_events)} events")
    all_events.extend(my_events)

    # 2. Fetch other SEA countries
    for code, name in SEA_COUNTRIES.items():
        if code == "MY":
            continue
        print(f"  🌏 Fetching {name.title()} ({code}) events...")
        events = await fetch_events_for_country(code, days_ahead=180, limit=50)
        print(f"   → {len(events)} events")
        all_events.extend(events)

    # 3. Fetch globally popular events
    print("\n🌐 Fetching global high-impact events (rank >= 70)...")
    global_events = await fetch_global_popular(days_ahead=180)
    print(f"   → {len(global_events)} events")
    all_events.extend(global_events)

    # Deduplicate by name + start_date
    seen = set()
    unique_events = []
    for e in all_events:
        key = (e["name"].lower().strip(), e["start_date"])
        if key not in seen:
            seen.add(key)
            unique_events.append(e)

    print(f"\n📊 Total unique events: {len(unique_events)}")

    # Sort: Malaysia first, then by impact score descending
    def sort_key(e):
        market_order = 0 if e["market"] == "malaysia" else (1 if e["market"] != "global" else 2)
        return (market_order, -e["impact_score"], e["start_date"])

    unique_events.sort(key=sort_key)

    # Save to CSV
    os.makedirs("data", exist_ok=True)
    today_str = datetime.now().strftime("%Y%m%d")
    csv_path = f"data/cultural_events_sea_{today_str}.csv"

    fieldnames = [
        "name", "market", "country_code", "start_date", "end_date",
        "event_type", "category_raw", "tags", "impact_score", "description",
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(unique_events)

    print(f"\n💾 Saved to: {csv_path}")
    print(f"   {len(unique_events)} events written")

    # Print summary table
    print(f"\n{'─' * 80}")
    print(f"  {'Name':<40} {'Market':<12} {'Date':<12} {'Type':<10} {'Score'}")
    print(f"{'─' * 80}")
    for e in unique_events[:30]:
        print(f"  {e['name'][:38]:<40} {e['market']:<12} {e['start_date']:<12} {e['event_type']:<10} {e['impact_score']}")

    if len(unique_events) > 30:
        print(f"  ... and {len(unique_events) - 30} more events (see CSV)")

    print(f"\n✅ Done!")


if __name__ == "__main__":
    asyncio.run(main())
