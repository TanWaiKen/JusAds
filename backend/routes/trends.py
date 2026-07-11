"""
routes/trends.py
────────────────
API routes for the Trend Intelligence page.

Serves scraped trending content from trends_cache and cultural events.
Also provides a manual refresh trigger for admins.

Requirements: 9.1, 9.2, 9.3, 9.4, 9.5
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from shared.clients import supabase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/trends", tags=["trends"])


@router.get("")
@router.get("/")
async def get_trends(
    platform: Optional[str] = None,
    market: Optional[str] = None,
    limit: int = 50,
) -> JSONResponse:
    """Fetch trending content from trends_cache, grouped by platform.

    Returns items with last_refresh timestamp per platform.
    Empty message when no data is available.
    """
    try:
        query = supabase.table("trends_cache").select("*")

        if platform:
            query = query.eq("platform", platform)
        if market:
            query = query.eq("market", market)

        query = query.order("scraped_at", desc=True).limit(limit)
        response = query.execute()
        items = response.data or []

        if not items:
            return JSONResponse(content={
                "trends": [],
                "last_refresh": {},
                "message": "No trend data currently available. Data refreshes weekly.",
            })

        # Group by platform
        grouped: dict[str, list] = {}
        last_refresh: dict[str, str] = {}

        for item in items:
            p = item.get("platform", "unknown")
            if p not in grouped:
                grouped[p] = []
                last_refresh[p] = item.get("scraped_at", "")
            grouped[p].append({
                "id": item.get("id"),
                "title": item.get("title"),
                "url": item.get("url"),
                "platform": p,
                "content_type": item.get("content_type"),
                "engagement_metrics": item.get("engagement_metrics", {}),
                "hashtags": item.get("hashtags", []),
                "categories": item.get("categories", []),
                "cultural_event_tag": item.get("cultural_event_tag"),
                "scraped_at": item.get("scraped_at"),
            })

        return JSONResponse(content={
            "trends": grouped,
            "last_refresh": last_refresh,
            "total_items": len(items),
        })

    except Exception as e:
        logger.error("[TrendsAPI] Failed to fetch trends: %s", e)
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "trends": [], "last_refresh": {}},
        )


@router.get("/events")
async def get_cultural_events(
    market: str = "malaysia",
    window_days: int = 30,
) -> JSONResponse:
    """Fetch upcoming events split into Global and National sections.

    Supports 'worldwide' or 'global' market values to fetch all events,
    or filters to a specific market (e.g. 'malaysia').
    """
    try:
        now = datetime.now(timezone.utc)
        window_end = (now + timedelta(days=window_days)).strftime("%Y-%m-%d")
        today = now.strftime("%Y-%m-%d")

        query = (
            supabase.table("cultural_events")
            .select("*")
            .gte("end_date", today)
            .lte("start_date", window_end)
        )

        # Filter by market unless worldwide is requested
        if market.lower() not in ("worldwide", "global", "all"):
            query = query.eq("market", market.lower())

        response = query.order("start_date", desc=False).execute()
        all_events = response.data or []

        # Split into global vs national/regional
        global_types = {"sports", "global"}
        national_types = {"religious", "festive", "national"}

        global_events = [e for e in all_events if e.get("event_type") in global_types]
        national_events = [e for e in all_events if e.get("event_type") in national_types]

        return JSONResponse(content={
            "global_events": global_events,
            "national_events": national_events,
            "all_events": all_events,
            "events": all_events,  # Align with frontend TrendsResponse expectation
            "market": market,
            "window_days": window_days,
            "count": len(all_events),
        })

    except Exception as e:
        logger.error("[TrendsAPI] Failed to fetch cultural events: %s", e)
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "events": [], "global_events": [], "national_events": []},
        )


@router.post("/events/sync")
async def sync_cultural_events() -> JSONResponse:
    """Synchronize local database events with PredictHQ API for the next 30 days."""
    try:
        from shared.predicthq_client import fetch_predicthq_events

        logger.info("[TrendsAPI] Starting PredictHQ event sync...")

        # Fetch Malaysia events and global events
        my_events = await fetch_predicthq_events(country_code="MY", days_ahead=30)
        global_events = await fetch_predicthq_events(country_code=None, days_ahead=30)

        all_fetched = my_events + global_events

        # Deduplicate
        seen = set()
        deduped = []
        for e in all_fetched:
            key = (e["name"], e["start_date"], e["market"])
            if key not in seen:
                seen.add(key)
                deduped.append(e)

        # Query existing events in DB to avoid duplicating or overwriting pre-seeded ones
        response = supabase.table("cultural_events").select("name, start_date").execute()
        existing = {(r["name"].lower(), str(r["start_date"])) for r in (response.data or [])}

        # Filter out already existing events
        to_insert = []
        for e in deduped:
            key = (e["name"].lower(), str(e["start_date"]))
            if key not in existing:
                to_insert.append(e)

        # Insert only the genuinely new events
        if to_insert:
            supabase.table("cultural_events").insert(to_insert).execute()

        logger.info("[TrendsAPI] PredictHQ event sync complete. Added %d new events.", len(to_insert))
        return JSONResponse(content={
            "status": "success",
            "message": f"Successfully synchronized {len(to_insert)} new events from PredictHQ.",
            "count": len(to_insert),
        })

    except Exception as e:
        logger.error("[TrendsAPI] PredictHQ sync failed: %s", e)
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )


@router.post("/refresh")
async def trigger_refresh() -> JSONResponse:
    """Manually trigger a trend research using Gemini GoogleSearch.

    Fetches personalized trending content based on user's business profile.
    Uses Gemini's built-in GoogleSearch tool for market-specific results.
    """
    import asyncio
    import uuid
    import json
    from google.genai.types import GenerateContentConfig, GoogleSearch, Tool
    from google.genai import types as genai_types
    from shared.clients import gemini
    from shared.config import MODEL_TEXT

    try:
        # For now, fetch for default market (could be parameterized)
        market = "malaysia"
        batch_id = str(uuid.uuid4())
        all_items = []

        platforms = ["tiktok", "instagram", "youtube"]

        for platform in platforms:
            try:
                # Step 1: GoogleSearch for trending content
                search_prompt = (
                    f"Search for the latest trending {platform} content and advertisements in {market}. "
                    f"Find 10 REAL currently trending posts/videos/ads with their actual URLs, view counts, and descriptions."
                )

                search_response = gemini.models.generate_content(
                    model=MODEL_TEXT,
                    contents=search_prompt,
                    config=GenerateContentConfig(tools=[Tool(google_search=GoogleSearch())]),
                )
                search_text = (search_response.text or "").strip()
                if not search_text:
                    continue

                # Step 2: Parse into structured JSON
                parse_prompt = (
                    f"Parse these search results about trending {platform} content in {market} into a JSON array. "
                    f"Return exactly 10 items. Each item: "
                    f'{{"title":"...","url":"...","content_type":"video/image/ad",'
                    f'"hashtags":["..."],"categories":["..."],'
                    f'"engagement":{{"views":0,"likes":0,"shares":0,"comments":0}},'
                    f'"why_trending":"..."}}\n\n'
                    f"SEARCH RESULTS:\n{search_text[:3000]}\n\nReturn ONLY JSON array."
                )

                parse_response = gemini.models.generate_content(
                    model=MODEL_TEXT,
                    contents=parse_prompt,
                    config=genai_types.GenerateContentConfig(response_mime_type="application/json"),
                )

                import re
                raw = parse_response.text.strip().replace("```json", "").replace("```", "")
                cleaned = re.sub(r',\s*([}\]])', r'\1', raw)
                items = json.loads(cleaned)

                if isinstance(items, list):
                    for item in items[:10]:
                        if item.get("title"):
                            all_items.append({
                                "platform": platform,
                                "content_type": item.get("content_type", "video"),
                                "title": (item.get("title") or "")[:500],
                                "url": item.get("url", ""),
                                "engagement_metrics": item.get("engagement", {}),
                                "hashtags": item.get("hashtags", [])[:10],
                                "categories": item.get("categories", []),
                                "market": market,
                                "scrape_batch_id": batch_id,
                            })
            except Exception as platform_err:
                logger.warning("[TrendsAPI] %s search failed: %s", platform, platform_err)

        # Store to database
        if all_items and supabase:
            supabase.table("trends_cache").delete().eq("market", market).execute()
            for i in range(0, len(all_items), 25):
                supabase.table("trends_cache").insert(all_items[i:i+25]).execute()

        logger.info("[TrendsAPI] Refresh complete: %d items stored", len(all_items))
        return JSONResponse(content={
            "status": "completed",
            "message": f"Refreshed {len(all_items)} trending items across {len(platforms)} platforms.",
            "items_count": len(all_items),
        })

    except Exception as e:
        logger.error("[TrendsAPI] Refresh failed: %s", e)
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "status": "failed"},
        )
