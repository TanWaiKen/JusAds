"""Company-context YouTube hook-reference query helpers.

This module intentionally does not determine whether a video is a paid ad or
whether its creative claims are compliant.  It builds a conservative search
query and a stable cache fingerprint for public YouTube reference videos.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any


_MARKET_REGION_CODES = {
    "malaysia": "MY", "singapore": "SG", "thailand": "TH", "indonesia": "ID",
    "vietnam": "VN", "philippines": "PH",
}
_SPACE = re.compile(r"\s+")


def market_region_code(market: str) -> str:
    """Return the YouTube region code, falling back to Malaysia."""

    return _MARKET_REGION_CODES.get((market or "").strip().lower(), "MY")


def _clean(value: Any, limit: int = 140) -> str:
    return _SPACE.sub(" ", str(value or "").strip())[:limit]


def company_context(profile: dict[str, Any]) -> str:
    """Produce a bounded, non-sensitive product context for a public search."""

    values = [_clean(profile.get("product_category"), 80), _clean(profile.get("product_description"), 140)]
    context = " ".join(value for value in values if value)
    return context or "consumer product"


def profile_fingerprint(profile: dict[str, Any], market: str) -> str:
    """Hash only fields that influence a cached public-reference result."""

    material = "|".join((
        (market or "malaysia").strip().lower(),
        _clean(profile.get("company_name"), 120).casefold(),
        _clean(profile.get("product_category"), 120).casefold(),
        _clean(profile.get("product_description"), 300).casefold(),
    ))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def build_hook_query(profile: dict[str, Any], market: str) -> str:
    """Build a YouTube query for popular short-form creative hook references."""

    return f"{company_context(profile)} {market.strip() or 'Malaysia'} popular advertising hook"[:350]


def serialise_video(video: Any) -> dict[str, str]:
    """Convert a YouTube search result to the cache's safe public shape."""

    return {
        "video_id": _clean(getattr(video, "video_id", ""), 32),
        "title": _clean(getattr(video, "title", ""), 500),
        "channel_title": _clean(getattr(video, "channel_title", ""), 300),
        "published_at": _clean(getattr(video, "published_at", ""), 64),
        "thumbnail_url": _clean(getattr(video, "thumbnail_high_url", "") or getattr(video, "thumbnail_url", ""), 2000),
        "watch_url": _clean(getattr(video, "watch_url", ""), 2000),
    }

