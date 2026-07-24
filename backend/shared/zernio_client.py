"""Async-safe client helpers for the live Zernio analytics API."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional, TypeVar

from shared.config import ZERNIO_API_KEY

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ZernioServiceError(RuntimeError):
    """Raised when live Zernio analytics are unavailable."""

    def __init__(self, message: str, *, not_configured: bool = False) -> None:
        super().__init__(message)
        self.not_configured = not_configured


def _get_client() -> Any:
    """Create a Zernio client only when a production API key is configured."""
    if not ZERNIO_API_KEY.strip():
        raise ZernioServiceError(
            "Zernio analytics are not configured.",
            not_configured=True,
        )
    from zernio import Zernio

    return Zernio(api_key=ZERNIO_API_KEY, timeout=30)


async def _call(operation: str, callback: Callable[[], T]) -> T:
    """Run the synchronous Zernio SDK outside FastAPI's event loop."""
    try:
        return await asyncio.to_thread(callback)
    except ZernioServiceError:
        raise
    except Exception as exc:
        logger.exception("[ZernioClient] %s failed", operation)
        raise ZernioServiceError("Zernio analytics are temporarily unavailable.") from exc


async def get_overall_analytics(period: str = "30d") -> dict[str, Any]:
    """Return live account analytics; period is reserved for SDK support."""
    client = _get_client()
    data = await _call("get_analytics", client.analytics.get_analytics)
    result = _serialize(data)
    result.setdefault("requested_period", period)
    result["source"] = "zernio"
    return result


async def get_daily_metrics() -> dict[str, Any]:
    """Return live daily aggregate metrics from Zernio."""
    client = _get_client()
    data = await _call("get_daily_metrics", client.analytics.get_daily_metrics)
    result = _serialize(data)
    result["source"] = "zernio"
    return result


async def get_best_time_to_post() -> dict[str, Any]:
    """Return live recommended posting times from Zernio."""
    client = _get_client()
    data = await _call("get_best_time_to_post", client.analytics.get_best_time_to_post)
    result = _serialize(data)
    result["source"] = "zernio"
    return result


async def get_connected_accounts() -> dict[str, Any]:
    """Return live connected social accounts from Zernio."""
    client = _get_client()
    data = await _call("accounts.list", client.accounts.list)
    result = _serialize(data)
    result["source"] = "zernio"
    return result


async def get_posts_list(platform: Optional[str] = None) -> dict[str, Any]:
    """Return live posts separated into JusAds and external account content."""
    client = _get_client()
    analytics_data = await _call(
        "posts analytics",
        lambda: client.analytics.get_analytics(platform=platform),
    )
    serialized = _serialize(analytics_data)
    posts_raw = serialized.get("posts", [])
    posts_formatted: list[dict[str, Any]] = []

    if not isinstance(posts_raw, list):
        raise ZernioServiceError("Zernio returned an unexpected analytics response.")

    for post in posts_raw:
        if not isinstance(post, dict):
            continue
        metrics = post.get("analytics") or {}
        if not isinstance(metrics, dict):
            metrics = {}
        impressions = metrics.get("impressions") or metrics.get("views") or 0
        likes = metrics.get("likes") or 0
        content = post.get("content") or ""
        title = post.get("title") or ""
        content_preview = title or (content.replace("\n", " ")[:80] if content else "")
        posts_formatted.append({
            "post_external_id": content_preview or post.get("_id") or "Untitled Post",
            "platform": post.get("platform") or "unknown",
            "impressions": impressions,
            "clicks": metrics.get("clicks") or 0,
            "engagement_rate": float(metrics.get("engagementRate") or 0.0),
            "reach": metrics.get("reach") or 0,
            "conversions": likes,
            "likes": likes,
            "comments": metrics.get("comments") or 0,
            "shares": metrics.get("shares") or 0,
            "is_external": bool(post.get("isExternal")),
            "published_at": post.get("publishedAt"),
            "post_url": post.get("platformPostUrl"),
            "thumbnail_url": post.get("thumbnailUrl") or post.get("coverImageUrl"),
        })

    jusads_posts = [post for post in posts_formatted if not post["is_external"]]
    organic_posts = [post for post in posts_formatted if post["is_external"]]
    return _build_response(jusads_posts, organic_posts, posts_formatted)


def _calculate_totals(posts: list[dict[str, Any]]) -> dict[str, float | int]:
    """Aggregate normalized post metrics."""
    impressions = sum(int(post["impressions"]) for post in posts)
    clicks = sum(int(post["clicks"]) for post in posts)
    likes = sum(int(post.get("likes", 0)) for post in posts)
    comments = sum(int(post.get("comments", 0)) for post in posts)
    shares = sum(int(post.get("shares", 0)) for post in posts)
    return {
        "impressions": impressions,
        "clicks": clicks,
        "engagement_rate": clicks / impressions * 100 if impressions else 0.0,
        "reach": sum(int(post["reach"]) for post in posts),
        "conversions": likes,
        "likes": likes,
        "comments": comments,
        "shares": shares,
    }


def _build_response(
    jusads_posts: list[dict[str, Any]],
    organic_posts: list[dict[str, Any]],
    all_posts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a live-data response with explicit source metadata."""
    jusads_totals = _calculate_totals(jusads_posts)
    organic_totals = _calculate_totals(organic_posts)
    all_totals = _calculate_totals(all_posts)
    platforms: dict[str, dict[str, int]] = {}
    for post in all_posts:
        platform = str(post["platform"])
        totals = platforms.setdefault(
            platform,
            {"posts": 0, "impressions": 0, "likes": 0, "reach": 0},
        )
        totals["posts"] += 1
        totals["impressions"] += int(post["impressions"])
        totals["likes"] += int(post.get("likes", 0))
        totals["reach"] += int(post["reach"])

    return {
        "jusads_posts": jusads_posts,
        "jusads_totals": jusads_totals,
        "jusads_count": len(jusads_posts),
        "organic_posts": organic_posts,
        "organic_totals": organic_totals,
        "organic_count": len(organic_posts),
        "posts": all_posts,
        "totals": all_totals,
        "post_count": len(all_posts),
        "account_overview": {
            "total_followers_reached": all_totals["reach"],
            "total_engagement": (
                int(all_totals["likes"])
                + int(all_totals["comments"])
                + int(all_totals["shares"])
            ),
            "platforms": platforms,
        },
        "source": "zernio",
        "is_stale": False,
        "last_refresh": datetime.now(timezone.utc).isoformat(),
    }


def _serialize(obj: Any) -> dict[str, Any]:
    """Recursively convert Zernio SDK objects to a plain dictionary."""
    def default_handler(value: Any) -> Any:
        if hasattr(value, "__dict__"):
            return {
                key: item
                for key, item in value.__dict__.items()
                if not key.startswith("_")
            }
        if hasattr(value, "value"):
            return value.value
        return str(value)

    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        dumped = obj.model_dump()
        return dumped if isinstance(dumped, dict) else {"data": dumped}
    try:
        serialized = json.loads(json.dumps(obj, default=default_handler))
        return serialized if isinstance(serialized, dict) else {"data": serialized}
    except (TypeError, ValueError) as exc:
        raise ZernioServiceError("Zernio returned an unreadable response.") from exc
