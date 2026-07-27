"""Persisted company-context YouTube hook-reference service."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from jusads_trends.youtube_hook_cache import (
    build_hook_query,
    market_region_code,
    profile_fingerprint,
    serialise_video,
)


class YouTubeHookReferenceError(RuntimeError):
    """Stable service error that is safe for the API adapter to handle."""


async def get_company_hook_references(
    supabase: Any,
    *,
    owner_email: str,
    market: str,
) -> dict[str, Any]:
    """Return a 24-hour cached public YouTube Shorts reference set.

    The cache key changes when a saved company/product context changes. The
    only external API request occurs on a cache miss.
    """
    if supabase is None:
        raise YouTubeHookReferenceError("datastore unavailable")
    normalized_market = (market or "malaysia").strip().lower()[:64] or "malaysia"
    try:
        profile_response = (
            supabase.table("business_profiles")
            .select("company_name, product_category, product_description")
            .eq("owner_email", owner_email)
            .limit(1)
            .execute()
        )
        profile = (profile_response.data or [{}])[0]
        fingerprint = profile_fingerprint(profile, normalized_market)
        cached_response = (
            supabase.table("youtube_hook_reference_cache")
            .select("results, fetched_at, expires_at")
            .eq("owner_email", owner_email)
            .eq("market", normalized_market)
            .eq("profile_fingerprint", fingerprint)
            .gt("expires_at", datetime.now(timezone.utc).isoformat())
            .limit(1)
            .execute()
        )
        cached = cached_response.data or []
        if cached:
            record = cached[0]
            return {
                "items": record.get("results") or [], "cached": True,
                "fetched_at": record.get("fetched_at"), "expires_at": record.get("expires_at"),
            }

        from shared.youtube_client import YouTubeClient

        client = YouTubeClient()
        if not client.is_configured:
            raise YouTubeHookReferenceError("youtube unavailable")
        query = build_hook_query(profile, normalized_market)
        videos = await asyncio.to_thread(
            client.search_shorts, query, 8, market_region_code(normalized_market), "viewCount", True
        )
        items = [serialise_video(video) for video in videos if getattr(video, "video_id", "")]
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=24)
        cache_row = {
            "owner_email": owner_email, "market": normalized_market,
            "profile_fingerprint": fingerprint, "query_text": query,
            "results": items, "fetched_at": now.isoformat(), "expires_at": expires_at.isoformat(),
            "updated_at": now.isoformat(),
        }
        supabase.table("youtube_hook_reference_cache").upsert(
            cache_row, on_conflict="owner_email,market,profile_fingerprint"
        ).execute()
        return {"items": items, "cached": False, "fetched_at": cache_row["fetched_at"], "expires_at": cache_row["expires_at"]}
    except YouTubeHookReferenceError:
        raise
    except Exception as exc:
        raise YouTubeHookReferenceError("youtube reference lookup failed") from exc
