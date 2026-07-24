"""PredictHQ client for fetching real cultural and advertising events."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

from shared.config import PREDICTHQ_API_KEY

logger = logging.getLogger(__name__)

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


class PredictHQServiceError(RuntimeError):
    """Raised when live PredictHQ events cannot be retrieved."""

    def __init__(self, message: str, *, not_configured: bool = False) -> None:
        super().__init__(message)
        self.not_configured = not_configured


def map_category(categories: list[str]) -> str:
    """Map PredictHQ categories to the local event-type vocabulary."""
    for category in categories:
        mapped = CATEGORY_MAPPING.get(category.lower())
        if mapped:
            return mapped
    return "global"


async def fetch_predicthq_events(
    country_code: Optional[str] = None,
    days_ahead: int = 30,
) -> list[dict[str, Any]]:
    """Fetch real events for the requested country and future date window."""
    if not PREDICTHQ_API_KEY.strip():
        raise PredictHQServiceError(
            "PredictHQ event synchronization is not configured.",
            not_configured=True,
        )

    now = datetime.now(timezone.utc)
    start_date = now.strftime("%Y-%m-%d")
    end_date = (now + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    params = {
        "active.gte": start_date,
        "active.lte": end_date,
        "category": ",".join([
            "festivals", "sports", "public-holidays", "concerts",
            "expos", "conferences", "observances",
        ]),
        "limit": 50,
        "sort": "start",
    }
    if country_code:
        params["country"] = country_code.upper()

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://api.predicthq.com/v1/events/",
                headers={
                    "Authorization": f"Bearer {PREDICTHQ_API_KEY}",
                    "Accept": "application/json",
                },
                params=params,
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.exception("[PredictHQ] Live event request failed")
        raise PredictHQServiceError(
            "PredictHQ events are temporarily unavailable.",
        ) from exc

    results = payload.get("results", []) if isinstance(payload, dict) else []
    mapped_events: list[dict[str, Any]] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        categories = result.get("category", [])
        mapped_events.append({
            "name": result.get("title", "Unknown Event"),
            "market": country_code.lower() if country_code else "global",
            "start_date": str(result.get("start", start_date))[:10],
            "end_date": str(result.get("end", end_date))[:10],
            "event_type": map_category(categories if isinstance(categories, list) else []),
            "tags": result.get("labels", []),
            "impact_score": result.get("rank", 50),
        })

    logger.info("[PredictHQ] Fetched %d live events", len(mapped_events))
    return mapped_events
