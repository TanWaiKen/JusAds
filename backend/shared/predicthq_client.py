"""
predicthq_client.py
───────────────────
PredictHQ API client for dynamic event fetching.

Fetches real-world events for SEA (Malaysia) and worldwide from the PredictHQ API,
mapping them into our local DB cultural_events schema.
Defers to a rich mock generator when PREDICTHQ_API_KEY is not configured.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
import httpx

from shared.config import PREDICTHQ_API_KEY

logger = logging.getLogger(__name__)

# PredictHQ Categories mapping to our local event_type check constraints:
# 'religious', 'festive', 'sports', 'national', 'global'
CATEGORY_MAPPING = {
    "sports": "sports",
    "festivals": "festive",
    "concerts": "festive",
    "expos": "global",
    "conferences": "global",
    "public-holidays": "national",
    "school-holidays": "national",
    "observances": "national",
    "community": "global",
    "politics": "global",
    "academic": "global",
}

def map_category(categories: List[str]) -> str:
    """Map PredictHQ categories to local event_type."""
    if not categories:
        return "global"
    
    # Try mapping each category, default to first match or 'global'
    for cat in categories:
        mapped = CATEGORY_MAPPING.get(cat.lower())
        if mapped:
            return mapped
            
    return "global"

async def fetch_predicthq_events(
    country_code: Optional[str] = None,
    days_ahead: int = 30,
) -> List[Dict[str, Any]]:
    """Fetch events from PredictHQ API for the next N days.

    If country_code is None, fetches worldwide events.
    If PREDICTHQ_API_KEY is not configured, returns mock events.
    """
    now = datetime.now(timezone.utc)
    start_date = now.strftime("%Y-%m-%d")
    end_date = (now + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    # Graceful degradation / Mock fallback
    if not PREDICTHQ_API_KEY or PREDICTHQ_API_KEY.strip() == "":
        logger.warning(
            "[PredictHQ] PREDICTHQ_API_KEY not configured — returning mock fallback events"
        )
        return _get_mock_events(country_code, start_date, end_date)

    url = "https://api.predicthq.com/v1/events/"
    headers = {
        "Authorization": f"Bearer {PREDICTHQ_API_KEY}",
        "Accept": "application/json",
    }
    
    # Categories we are interested in
    categories = [
        "festivals", "sports", "public-holidays", "concerts", 
        "expos", "conferences", "observances"
    ]
    
    params = {
        "active.gte": start_date,
        "active.lte": end_date,
        "category": ",".join(categories),
        "limit": 50,
        "sort": "start",
    }
    
    if country_code:
        params["country"] = country_code.upper()

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, params=params, timeout=15.0)
            if resp.status_code != 200:
                logger.error(
                    "[PredictHQ] API request failed with status %d: %s", 
                    resp.status_code, resp.text
                )
                return _get_mock_events(country_code, start_date, end_date)
            
            data = resp.json()
            results = data.get("results", [])
            
            mapped_events = []
            for r in results:
                mapped_events.append({
                    "name": r.get("title", "Unknown Event"),
                    "market": country_code.lower() if country_code else "global",
                    "start_date": r.get("start", start_date)[:10],
                    "end_date": r.get("end", end_date)[:10],
                    "event_type": map_category(r.get("category", [])),
                    "tags": r.get("labels", []),
                    "impact_score": r.get("rank", 50),
                })
            
            logger.info(
                "[PredictHQ] Successfully fetched and mapped %d events from API", 
                len(mapped_events)
            )
            return mapped_events

    except Exception as e:
        logger.error("[PredictHQ] Connection failed: %s — falling back to mock events", e)
        return _get_mock_events(country_code, start_date, end_date)


def _get_mock_events(
    country_code: Optional[str],
    start_date: str,
    end_date: str,
) -> List[Dict[str, Any]]:
    """Return realistic mock events for Malaysia (MY) and Worldwide (global)."""
    # Parse dates to generate relative dates
    now = datetime.now()
    
    malaysia_events = [
        {
            "name": "Merdeka Parade Rehearsals",
            "market": "malaysia",
            "start_date": (now + timedelta(days=2)).strftime("%Y-%m-%d"),
            "end_date": (now + timedelta(days=5)).strftime("%Y-%m-%d"),
            "event_type": "national",
            "tags": ["parade", "national-day", "merdeka"],
            "impact_score": 85,
        },
        {
            "name": "Kuala Lumpur International Book Fair",
            "market": "malaysia",
            "start_date": (now + timedelta(days=10)).strftime("%Y-%m-%d"),
            "end_date": (now + timedelta(days=15)).strftime("%Y-%m-%d"),
            "event_type": "festive",
            "tags": ["exhibition", "books", "culture"],
            "impact_score": 70,
        },
        {
            "name": "Hari Raya Aidilfitri Festive Bazars",
            "market": "malaysia",
            "start_date": (now + timedelta(days=18)).strftime("%Y-%m-%d"),
            "end_date": (now + timedelta(days=30)).strftime("%Y-%m-%d"),
            "event_type": "religious",
            "tags": ["holiday", "raya", "food"],
            "impact_score": 95,
        },
        {
            "name": "George Town Heritage Festival",
            "market": "malaysia",
            "start_date": (now + timedelta(days=22)).strftime("%Y-%m-%d"),
            "end_date": (now + timedelta(days=25)).strftime("%Y-%m-%d"),
            "event_type": "festive",
            "tags": ["culture", "penang", "festival"],
            "impact_score": 65,
        }
    ]

    global_events = [
        {
            "name": "Summer Olympic Games Opening Ceremony",
            "market": "global",
            "start_date": (now + timedelta(days=4)).strftime("%Y-%m-%d"),
            "end_date": (now + timedelta(days=5)).strftime("%Y-%m-%d"),
            "event_type": "sports",
            "tags": ["sports", "olympics", "global"],
            "impact_score": 99,
        },
        {
            "name": "Global Tech Summit 2026",
            "market": "global",
            "start_date": (now + timedelta(days=8)).strftime("%Y-%m-%d"),
            "end_date": (now + timedelta(days=11)).strftime("%Y-%m-%d"),
            "event_type": "global",
            "tags": ["technology", "expo", "business"],
            "impact_score": 75,
        },
        {
            "name": "World Music Festival Live",
            "market": "global",
            "start_date": (now + timedelta(days=14)).strftime("%Y-%m-%d"),
            "end_date": (now + timedelta(days=16)).strftime("%Y-%m-%d"),
            "event_type": "festive",
            "tags": ["concert", "music", "global"],
            "impact_score": 80,
        },
        {
            "name": "Global Shopping Festival (Double 11 Deals)",
            "market": "global",
            "start_date": (now + timedelta(days=25)).strftime("%Y-%m-%d"),
            "end_date": (now + timedelta(days=28)).strftime("%Y-%m-%d"),
            "event_type": "global",
            "tags": ["shopping", "sales", "e-commerce"],
            "impact_score": 90,
        }
    ]

    if country_code and country_code.lower() == "my":
        return malaysia_events
    elif country_code:
        return [] # No mock events for other specific countries
    else:
        # Worldwide view returns a combination of both
        return malaysia_events + global_events
