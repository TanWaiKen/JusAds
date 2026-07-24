"""
routes/trends.py
────────────────
API routes for the Trend Intelligence page.

Serves scraped trending content from trends_cache and cultural events.
Also provides a manual refresh trigger for admins.

Requirements: 9.1, 9.2, 9.3, 9.4, 9.5
"""

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from shared.clients import supabase
from shared.predicthq_client import PredictHQServiceError, fetch_predicthq_events

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/trends", tags=["trends"])


class TrendResearchRequest(BaseModel):
    """Request parameters for a personalized, grounded trend refresh."""

    owner_email: str = ""
    market: str = "malaysia"
    platform: str = ""
    limit: int = 30


class TrendResearchResponse(BaseModel):
    """Structured response metadata returned by trend research."""

    trends: dict[str, list[dict[str, Any]]]
    last_refresh: dict[str, str]
    total_items: int
    research_provider: str
    freshness: str
    research_sources: list[dict[str, str]]
    message: Optional[str] = None


class CreativeSignalResearchRequest(BaseModel):
    """Request parameters for evidence-backed creative signal research."""

    owner_email: str = ""
    market: str = "malaysia"
    platform: str = ""


@router.get("/daily-idea")
async def get_daily_idea(market: str = "malaysia") -> JSONResponse:
    """Return one market-wide creative idea that stays fixed for the local day."""
    from jusads_trends.daily_idea import get_daily_creative_idea

    try:
        idea = await get_daily_creative_idea(market)
        return JSONResponse(content=idea)
    except Exception:
        logger.exception("[TrendsAPI] Daily creative idea failed")
        return JSONResponse(
            status_code=503,
            content={"error": "Today's creative idea is temporarily unavailable."},
        )


def _trend_item(item: dict[str, Any], platform: str) -> dict[str, Any]:
    """Normalize a cached trend row for the frontend."""
    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "url": item.get("url"),
        "platform": platform,
        "content_type": item.get("content_type"),
        "engagement_metrics": item.get("engagement_metrics", {}),
        "hashtags": item.get("hashtags", []),
        "categories": item.get("categories", []),
        "cultural_event_tag": item.get("cultural_event_tag"),
        "scraped_at": item.get("scraped_at"),
    }


def _group_trends(items: list[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    """Group trend rows by platform and calculate each platform freshness timestamp."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    last_refresh: dict[str, str] = {}
    for item in items:
        platform = item.get("platform", "unknown")
        grouped.setdefault(platform, []).append(_trend_item(item, platform))
        last_refresh.setdefault(platform, item.get("scraped_at", ""))
    return grouped, last_refresh


@router.get("/signals")
async def get_creative_signals(
    market: str = "malaysia",
    platform: str = "",
    owner_email: str = "",
    limit: int = 30,
) -> JSONResponse:
    """Return persisted evidence-backed Creative Trend Signals."""
    from jusads_trends.creative_signals import CreativeSignalError, fetch_creative_signals

    try:
        signals = fetch_creative_signals(
            market=(market or "malaysia").strip().lower(),
            platform=platform.strip().lower(),
            owner_email=owner_email.strip().lower(),
            limit=max(1, min(limit, 50)),
        )
        return JSONResponse(content={"signals": signals, "count": len(signals)})
    except CreativeSignalError as exc:
        return JSONResponse(status_code=503, content={"error": str(exc), "signals": [], "count": 0})


@router.post("/signals/research")
async def research_creative_signals(body: CreativeSignalResearchRequest) -> JSONResponse:
    """Research and persist only evidence-backed creative patterns for campaign ideation."""
    from jusads_trends.creative_signals import CreativeSignalError, research_creative_signals

    try:
        signals = await research_creative_signals(
            market=(body.market or "malaysia").strip().lower(),
            platform=body.platform.strip().lower(),
            owner_email=body.owner_email.strip().lower(),
        )
        return JSONResponse(content={
            "signals": signals,
            "count": len(signals),
            "freshness": "fresh",
            "message": "Signals are returned for this session. Apply migration 021 to save them for later.",
        })
    except CreativeSignalError as exc:
        message = str(exc)
        if message.startswith("No evidence-backed creative trend signals"):
            logger.info("[TrendsAPI] Creative signal research produced no verified signals")
            return JSONResponse(content={"signals": [], "count": 0, "freshness": "unavailable", "message": message})
        logger.warning("[TrendsAPI] Creative signal research unavailable: %s", exc)
        return JSONResponse(status_code=503, content={"error": message, "signals": [], "count": 0})


@router.post("/research", response_model=TrendResearchResponse)
async def research_trends(body: TrendResearchRequest) -> JSONResponse:
    """Research personalized trends with Google grounding and safely cache the result."""
    market = (body.market or "malaysia").strip().lower()
    platform = (body.platform or "").strip().lower()
    owner_email = body.owner_email.strip().lower()
    limit = max(1, min(body.limit, 50))
    provider = "none"
    sources: list[dict[str, str]] = []

    try:
        profile: dict[str, Any] = {}
        if owner_email and supabase:
            profile_response = (
                supabase.table("business_profiles")
                .select("company_name, product_category, product_description, target_platforms, target_markets")
                .eq("owner_email", owner_email)
                .limit(1)
                .execute()
            )
            profile = (profile_response.data or [{}])[0]

        profile_context = ", ".join(
            value for value in (
                f"company: {profile.get('company_name')}" if profile.get("company_name") else "",
                f"category: {profile.get('product_category')}" if profile.get("product_category") else "",
                f"description: {profile.get('product_description')}" if profile.get("product_description") else "",
                f"target platforms: {', '.join(profile.get('target_platforms') or [])}" if profile.get("target_platforms") else "",
                f"target markets: {', '.join(profile.get('target_markets') or [])}" if profile.get("target_markets") else "",
            )
            if value
        ) or "general advertising and social content"
        platforms = [platform] if platform else ["tiktok", "instagram", "youtube"]
        all_items: list[dict[str, Any]] = []
        batch_id = str(uuid.uuid4())

        from jusads_compliance.agents.research import google_grounded_research

        for current_platform in platforms:
            query = (
                f"top 5 currently trending {current_platform} content and advertisements "
                f"in {market} right now; include real public URLs. "
                f"Business context: {profile_context}"
            )
            research = google_grounded_research(
                query,
                "Find the top 5 trending pieces of content on this platform right now. "
                "Return real, clickable URLs to actual posts/videos. Include engagement numbers if available.",
            )
            if not research:
                continue
            provider = "google_grounding"
            sources.extend(research.get("sources", []))
            parse_prompt = f"""Convert this grounded research into a JSON array of EXACTLY 5 real {current_platform} trend items for {market}.
Business context: {profile_context}
Research:
{research.get('content', '')[:4000]}

IMPORTANT: Only include items where you have a REAL, clickable URL to the actual post/video/ad.
Do NOT invent or hallucinate URLs. If you cannot find a real URL, skip that item.
Each item must include title, url, content_type, hashtags, categories, engagement (views, likes, shares, comments), and why_trending.
Return only a JSON array of up to 5 items."""
            try:
                from google.genai import types as genai_types
                from shared.config import MODEL_TEXT
                from shared.clients import gemini
                parsed = gemini.models.generate_content(
                    model=MODEL_TEXT,
                    contents=parse_prompt,
                    config=genai_types.GenerateContentConfig(response_mime_type="application/json"),
                )
                raw = (parsed.text or "").replace("```json", "").replace("```", "").strip()
                items = json.loads(raw)
                if isinstance(items, list):
                    for item in items[:5]:
                        if item.get("title") and item.get("url"):
                            all_items.append({
                                "platform": current_platform,
                                "content_type": item.get("content_type", "video"),
                                "title": str(item.get("title", ""))[:500],
                                "url": item.get("url", ""),
                                "engagement_metrics": item.get("engagement", {}),
                                "hashtags": item.get("hashtags", [])[:10],
                                "categories": item.get("categories", []),
                                "cultural_event_tag": None,
                                "market": market,
                                "owner_email": owner_email or None,
                                "scrape_batch_id": batch_id,
                            })
                    # If no items with valid URLs were parsed, use grounding sources as clickable links
                    platform_items = [i for i in all_items if i.get("platform") == current_platform]
                    if not platform_items:
                        for src in research.get("sources", [])[:5]:
                            if src.get("url"):
                                all_items.append({
                                    "platform": current_platform,
                                    "content_type": "ad",
                                    "title": src.get("title", "Trending content")[:500],
                                    "url": src["url"],
                                    "engagement_metrics": {},
                                    "hashtags": [],
                                    "categories": ["trending"],
                                    "cultural_event_tag": None,
                                    "market": market,
                                    "owner_email": owner_email or None,
                                    "scrape_batch_id": batch_id,
                                })
            except Exception as parse_error:
                logger.warning("[TrendsAPI] Failed to parse grounded %s research: %s", current_platform, parse_error)

        # Cached rows are only replaced within this exact owner/market/platform scope.
        if all_items and supabase:
            delete_query = supabase.table("trends_cache").delete().eq("market", market)
            if owner_email:
                delete_query = delete_query.eq("owner_email", owner_email)
            else:
                delete_query = delete_query.is_("owner_email", "null")
            if platform:
                delete_query = delete_query.eq("platform", platform)
            delete_query.execute()
            for offset in range(0, len(all_items), 25):
                supabase.table("trends_cache").insert(all_items[offset:offset + 25]).execute()

        if all_items:
            grouped, last_refresh = _group_trends(all_items)
            freshness = "fresh"
            message = None
        else:
            # Grounding may be unavailable; return scoped cached data rather than failing the page.
            query = supabase.table("trends_cache").select("*").eq("market", market).order("scraped_at", desc=True).limit(limit)
            if owner_email:
                query = query.eq("owner_email", owner_email)
            else:
                query = query.is_("owner_email", "null")
            if platform:
                query = query.eq("platform", platform)
            cached = query.execute().data or [] if supabase else []
            grouped, last_refresh = _group_trends(cached)
            freshness = "cached" if cached else "unavailable"
            message = "Live research is temporarily unavailable; showing the latest scoped trend data." if cached else "No trend data currently available."

        unique_sources = {source.get("url"): source for source in sources if source.get("url")}
        return JSONResponse(content={
            "trends": grouped,
            "last_refresh": last_refresh,
            "total_items": sum(len(items) for items in grouped.values()),
            "research_provider": provider,
            "freshness": freshness,
            "research_sources": list(unique_sources.values())[:10],
            "message": message,
        })
    except Exception as exc:
        logger.exception("[TrendsAPI] Personalized trend research failed: %s", exc)
        return JSONResponse(status_code=200, content={
            "trends": {}, "last_refresh": {}, "total_items": 0,
            "research_provider": provider, "freshness": "unavailable",
            "research_sources": [], "message": "Trend research is temporarily unavailable.",
        })

@router.get("")
@router.get("/")
async def get_trends(
    platform: Optional[str] = None,
    market: Optional[str] = None,
    owner_email: Optional[str] = None,
    limit: int = 50,
) -> JSONResponse:
    """Fetch scoped cached trending content, grouped by platform."""
    try:
        query = supabase.table("trends_cache").select("*")

        if platform:
            query = query.eq("platform", platform)
        if market:
            query = query.eq("market", market)
        if owner_email:
            query = query.eq("owner_email", owner_email.strip().lower())
        else:
            query = query.is_("owner_email", "null")

        query = query.order("scraped_at", desc=True).limit(limit)
        response = query.execute()
        items = response.data or []

        if not items:
            return JSONResponse(content={
                "trends": [],
                "last_refresh": {},
                "message": "No trend data currently available. Data refreshes weekly.",
            })

        grouped, last_refresh = _group_trends(items)
        return JSONResponse(content={
            "trends": grouped,
            "last_refresh": last_refresh,
            "total_items": len(items),
        })

    except Exception:
        logger.exception("[TrendsAPI] Failed to fetch trends")
        return JSONResponse(
            status_code=500,
            content={"error": "Unable to load trend data.", "trends": [], "last_refresh": {}},
        )


@router.get("/events")
async def get_cultural_events(
    market: Optional[str] = None,
    country: Optional[str] = None,
    window_days: int = 60,
) -> JSONResponse:
    """Fetch upcoming events with country-based filtering.

    Filters:
    - market: 'malaysia', 'thailand', 'singapore', etc. Shows that market + global events.
    - country: alias for market (frontend sends country code like 'MY' → mapped to market name).
    - If market is 'all' or 'worldwide', returns everything.
    - Global events (market='global') are always included alongside country-specific ones.
    """
    try:
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        window_end = (now + timedelta(days=window_days)).strftime("%Y-%m-%d")
        today = now.strftime("%Y-%m-%d")

        # Map country codes to market names
        country_to_market = {
            "MY": "malaysia", "TH": "thailand", "SG": "singapore",
            "ID": "indonesia", "VN": "vietnam", "PH": "philippines",
        }

        # Resolve the effective market filter
        effective_market = None
        if country and country.upper() in country_to_market:
            effective_market = country_to_market[country.upper()]
        elif market and market.lower() not in ("all", "worldwide", "global"):
            effective_market = market.lower()

        # Fetch events within date window
        query = (
            supabase.table("cultural_events")
            .select("*")
            .gte("end_date", today)
            .lte("start_date", window_end)
        )

        response = query.order("start_date", desc=False).execute()
        all_events = response.data or []

        # Filter: show country-specific + global events
        if effective_market:
            filtered_events = [
                e for e in all_events
                if e.get("market") == effective_market or e.get("market") == "global"
            ]
        else:
            filtered_events = all_events

        # Split into sections
        global_types = {"sports", "global"}
        national_types = {"religious", "festive", "national"}

        global_events = [e for e in filtered_events if e.get("event_type") in global_types]
        national_events = [e for e in filtered_events if e.get("event_type") in national_types]

        # Get distinct markets for the filter dropdown
        all_markets = sorted(set(
            e.get("market", "") for e in all_events if e.get("market") != "global"
        ))

        return JSONResponse(content={
            "global_events": global_events,
            "national_events": national_events,
            "all_events": filtered_events,
            "events": filtered_events,
            "market": effective_market or "all",
            "available_markets": all_markets,
            "window_days": window_days,
            "count": len(filtered_events),
        })

    except Exception:
        logger.exception("[TrendsAPI] Failed to fetch cultural events")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Unable to load cultural events.",
                "events": [],
                "global_events": [],
                "national_events": [],
            },
        )


@router.post("/events/sync")
async def sync_cultural_events() -> JSONResponse:
    """Synchronize local database events with PredictHQ API for the next 30 days."""
    try:
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

    except PredictHQServiceError as exc:
        logger.warning("[TrendsAPI] PredictHQ sync unavailable: %s", exc)
        return JSONResponse(
            status_code=503 if exc.not_configured else 502,
            content={
                "error": str(exc),
                "code": "predicthq_not_configured" if exc.not_configured else "predicthq_unavailable",
            },
        )
    except Exception:
        logger.exception("[TrendsAPI] PredictHQ sync failed")
        return JSONResponse(
            status_code=500,
            content={"error": "Unable to synchronize cultural events."},
        )


@router.post("/refresh")
async def trigger_refresh(
    owner_email: str = "",
    market: str = "malaysia",
) -> JSONResponse:
    """Manually refresh a scoped trend cache using Gemini GoogleSearch."""
    import asyncio
    import uuid
    import json
    from google.genai.types import GenerateContentConfig, GoogleSearch, Tool
    from google.genai import types as genai_types
    from shared.clients import gemini
    from shared.config import MODEL_TEXT

    try:
        # For now, fetch for requested market and scope writes to this owner.
        market = (market or "malaysia").strip().lower()
        owner_email = owner_email.strip().lower()
        batch_id = str(uuid.uuid4())
        all_items = []

        platforms = ["tiktok", "instagram", "youtube"]

        for platform in platforms:
            try:
                # Step 1: GoogleSearch for trending content (top 5 only)
                search_prompt = (
                    f"Find the top 5 currently trending {platform} content and advertisements in {market}. "
                    f"Include real clickable URLs to the actual posts/videos, view counts, and descriptions."
                )

                search_response = gemini.models.generate_content(
                    model=MODEL_TEXT,
                    contents=search_prompt,
                    config=GenerateContentConfig(tools=[Tool(google_search=GoogleSearch())]),
                )
                search_text = (search_response.text or "").strip()
                if not search_text:
                    continue

                # Extract grounding source URLs from search response
                grounding_sources: list[dict[str, str]] = []
                if search_response.candidates:
                    metadata = getattr(search_response.candidates[0], "grounding_metadata", None)
                    for chunk in getattr(metadata, "grounding_chunks", []) or []:
                        web = getattr(chunk, "web", None)
                        uri = getattr(web, "uri", None)
                        if uri:
                            grounding_sources.append({"url": uri, "title": getattr(web, "title", "")})

                # Step 2: Parse into structured JSON (top 5)
                parse_prompt = (
                    f"Parse these search results about trending {platform} content in {market} into a JSON array. "
                    f"Return EXACTLY 5 items. IMPORTANT: Only include items with REAL, clickable URLs. "
                    f"Do NOT invent URLs. Each item: "
                    f'{{"title":"...","url":"...","content_type":"video/image/ad",'
                    f'"hashtags":["..."],"categories":["..."],'
                    f'"engagement":{{"views":0,"likes":0,"shares":0,"comments":0}},'
                    f'"why_trending":"..."}}\n\n'
                    f"SEARCH RESULTS:\n{search_text[:3000]}\n\nReturn ONLY JSON array of up to 5 items."
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
                    for item in items[:5]:
                        if item.get("title") and item.get("url"):
                            all_items.append({
                                "platform": platform,
                                "content_type": item.get("content_type", "video"),
                                "title": (item.get("title") or "")[:500],
                                "url": item.get("url", ""),
                                "engagement_metrics": item.get("engagement", {}),
                                "hashtags": item.get("hashtags", [])[:10],
                                "categories": item.get("categories", []),
                                "market": market,
                                "owner_email": owner_email or None,
                                "scrape_batch_id": batch_id,
                            })
                    # If parsed items have no valid URLs, use grounding sources directly
                    if not any(i.get("url") for i in all_items if i.get("platform") == platform):
                        for src in grounding_sources[:5]:
                            all_items.append({
                                "platform": platform,
                                "content_type": "ad",
                                "title": src.get("title", "Trending content")[:500],
                                "url": src.get("url", ""),
                                "engagement_metrics": {},
                                "hashtags": [],
                                "categories": ["trending"],
                                "market": market,
                                "owner_email": owner_email or None,
                                "scrape_batch_id": batch_id,
                            })
            except Exception as platform_err:
                logger.warning("[TrendsAPI] %s search failed: %s", platform, platform_err)

        # Store to database
        if all_items and supabase:
            delete_query = supabase.table("trends_cache").delete().eq("market", market)
            if owner_email:
                delete_query = delete_query.eq("owner_email", owner_email)
            else:
                delete_query = delete_query.is_("owner_email", "null")
            delete_query.execute()
            for i in range(0, len(all_items), 25):
                supabase.table("trends_cache").insert(all_items[i:i+25]).execute()

        logger.info("[TrendsAPI] Refresh complete: %d items stored", len(all_items))
        return JSONResponse(content={
            "status": "completed",
            "message": f"Refreshed {len(all_items)} trending items across {len(platforms)} platforms.",
            "items_count": len(all_items),
        })

    except Exception:
        logger.exception("[TrendsAPI] Refresh failed")
        return JSONResponse(
            status_code=500,
            content={"error": "Unable to refresh trends.", "status": "failed"},
        )
