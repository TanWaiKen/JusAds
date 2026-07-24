"""Date-stable daily creative idea assembled from saved trend intelligence."""

import asyncio
import json
import logging
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from shared.clients import supabase

logger = logging.getLogger(__name__)

_MARKET_TIMEZONES = {
    "malaysia": ("Asia/Kuala_Lumpur", 8),
    "singapore": ("Asia/Singapore", 8),
    "thailand": ("Asia/Bangkok", 7),
}
_CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "daily_creative_ideas.json"
_LOCK = asyncio.Lock()
_KNOWN_2026_MALAYSIA_WINDOWS = {
    # Official sources vary by one announced/observed day, so retain the
    # inclusive March 20-23 window and reject clearly unrelated dates.
    "aidilfitri": (date(2026, 3, 20), date(2026, 3, 23)),
    "hari raya puasa": (date(2026, 3, 20), date(2026, 3, 23)),
}


def _plain_text(value: Any, limit: int = 1200) -> str:
    return str(value or "").strip()[:limit]


def _market_timezone(market: str) -> tuple[timezone, str]:
    timezone_name, utc_offset = _MARKET_TIMEZONES.get(
        market,
        _MARKET_TIMEZONES["malaysia"],
    )
    return timezone(timedelta(hours=utc_offset)), timezone_name


def _market_clock(market: str) -> tuple[datetime, str]:
    timezone_info, timezone_name = _market_timezone(market)
    return datetime.now(timezone_info), timezone_name


def _valid_urls(values: Any) -> list[str]:
    urls: list[str] = []
    if not isinstance(values, list):
        return urls
    for value in values:
        url = _plain_text(value, 2000)
        parsed = urlparse(url)
        if parsed.scheme == "https" and parsed.netloc and url not in urls:
            urls.append(url)
    return urls[:6]


def _read_local_cache(cache_key: str) -> dict[str, Any] | None:
    try:
        cache = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
        value = cache.get(cache_key)
        return value if isinstance(value, dict) else None
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _event_date_is_plausible(event: dict[str, Any], market: str) -> bool:
    if market != "malaysia":
        return True
    name = _plain_text(event.get("name"), 200).lower()
    try:
        start_date = date.fromisoformat(_plain_text(event.get("start_date"), 20))
    except ValueError:
        return False
    for phrase, (window_start, window_end) in _KNOWN_2026_MALAYSIA_WINDOWS.items():
        if phrase in name and start_date.year == 2026:
            return window_start <= start_date <= window_end
    return True


def _cached_payload_is_plausible(
    payload: dict[str, Any],
    idea_date: str,
    market: str,
) -> bool:
    if market != "malaysia":
        return True
    text = " ".join(
        [
            _plain_text(payload.get("title"), 200),
            _plain_text(payload.get("event_name"), 200),
        ]
    ).lower()
    try:
        day = date.fromisoformat(idea_date)
    except ValueError:
        return False
    if day.year == 2026 and any(phrase in text for phrase in _KNOWN_2026_MALAYSIA_WINDOWS):
        # Daily preparation ideas may start up to three weeks before the event.
        return date(2026, 2, 27) <= day <= date(2026, 3, 23)
    return True


def _write_local_cache(cache_key: str, payload: dict[str, Any]) -> None:
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            cache = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
            if not isinstance(cache, dict):
                cache = {}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            cache = {}
        cache[cache_key] = payload
        _CACHE_PATH.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("[DailyIdea] Local cache write failed: %s", exc)


def _load_persisted_idea(idea_date: str, market: str) -> dict[str, Any] | None:
    if supabase is not None:
        try:
            rows = (
                supabase.table("daily_creative_ideas")
                .select("payload")
                .eq("idea_date", idea_date)
                .eq("market", market)
                .limit(1)
                .execute()
                .data
                or []
            )
            if rows and isinstance(rows[0].get("payload"), dict):
                payload = rows[0]["payload"]
                if _cached_payload_is_plausible(payload, idea_date, market):
                    return payload
        except Exception:
            # Migration 022 may not be applied in local development yet.
            logger.info("[DailyIdea] Database cache unavailable; using local cache")
    payload = _read_local_cache(f"{idea_date}:{market}")
    if payload and _cached_payload_is_plausible(payload, idea_date, market):
        return payload
    return None


def _persist_idea(idea_date: str, market: str, payload: dict[str, Any]) -> None:
    saved = False
    if supabase is not None:
        try:
            supabase.table("daily_creative_ideas").upsert(
                {
                    "idea_date": idea_date,
                    "market": market,
                    "payload": payload,
                    "generated_at": payload["generated_at"],
                    "expires_at": payload["expires_at"],
                },
                on_conflict="idea_date,market",
            ).execute()
            saved = True
        except Exception:
            logger.info("[DailyIdea] Database cache unavailable; persisting locally")
    if not saved:
        _write_local_cache(f"{idea_date}:{market}", payload)


def _saved_inputs(market: str, today: date) -> dict[str, list[dict[str, Any]]]:
    inputs: dict[str, list[dict[str, Any]]] = {"events": [], "signals": [], "trends": []}
    if supabase is None:
        return inputs
    try:
        inputs["events"] = (
            supabase.table("cultural_events")
            .select("name,market,start_date,end_date,event_type,tags,impact_score")
            .in_("market", [market, "global"])
            .gte("end_date", today.isoformat())
            .lte("start_date", (today + timedelta(days=21)).isoformat())
            .order("impact_score", desc=True)
            .limit(8)
            .execute()
            .data
            or []
        )
        inputs["events"] = [
            event for event in inputs["events"] if _event_date_is_plausible(event, market)
        ]
    except Exception as exc:
        logger.warning("[DailyIdea] Cultural-event cache unavailable: %s", exc)
    try:
        inputs["signals"] = (
            supabase.table("creative_trend_signals")
            .select(
                "title,summary,why_trending,how_it_works,suggested_adaptation,"
                "do_not_do,target_platforms,momentum,confidence,detected_at,"
                "creative_trend_sources(url)"
            )
            .eq("market", market)
            .is_("owner_email", "null")
            .order("detected_at", desc=True)
            .limit(6)
            .execute()
            .data
            or []
        )
    except Exception as exc:
        logger.warning("[DailyIdea] Creative-signal cache unavailable: %s", exc)
    try:
        inputs["trends"] = (
            supabase.table("trends_cache")
            .select("title,url,platform,categories,hashtags,cultural_event_tag,scraped_at")
            .eq("market", market)
            .is_("owner_email", "null")
            .order("scraped_at", desc=True)
            .limit(8)
            .execute()
            .data
            or []
        )
    except Exception as exc:
        logger.warning("[DailyIdea] Trend cache unavailable: %s", exc)
    return inputs


def _source_urls(inputs: dict[str, list[dict[str, Any]]]) -> list[str]:
    candidates: list[str] = []
    for trend in inputs["trends"]:
        candidates.append(_plain_text(trend.get("url"), 2000))
    for signal in inputs["signals"]:
        for source in signal.get("creative_trend_sources") or []:
            if isinstance(source, dict):
                candidates.append(_plain_text(source.get("url"), 2000))
    return _valid_urls(candidates)


def _fallback_idea(
    inputs: dict[str, list[dict[str, Any]]],
    *,
    today: date,
    market: str,
) -> dict[str, Any]:
    event = inputs["events"][0] if inputs["events"] else None
    signal = inputs["signals"][0] if inputs["signals"] else None
    trend = inputs["trends"][0] if inputs["trends"] else None
    if event:
        event_name = _plain_text(event.get("name"), 160)
        try:
            event_date = date.fromisoformat(_plain_text(event.get("start_date"), 20))
            days_until = max(0, (event_date - today).days)
        except ValueError:
            logger.warning("[DailyIdea] Ignoring malformed event date for %s", event_name)
            event = None
    if event:
        signal_adaptation = (
            _plain_text(signal.get("suggested_adaptation"), 700)
            if signal
            else ""
        )
        signal_hook = (
            _plain_text(signal.get("how_it_works"), 400)
            if signal
            else ""
        )
        return {
            "title": f"{event_name}: preparation moment",
            "why_today": (
                f"{event_name} begins in {days_until} day{'s' if days_until != 1 else ''}. "
                "Use preparation and anticipation rather than unsupported festive claims."
            ),
            "idea": signal_adaptation or (
                "Show a relatable before-and-after preparation ritual, then reveal how the product "
                "fits naturally into the moment."
            ),
            "hook": signal_hook
            or "Open on the unfinished preparation, then snap to the satisfying finished moment.",
            "format": "15-second vertical video",
            "execution_steps": [
                "0-3s: unfinished preparation or relatable tension",
                "3-10s: product action or transformation",
                "10-15s: finished moment and approved CTA",
            ],
            "event_name": event_name,
            "confidence": "event-backed",
        }
    if signal:
        return {
            "title": _plain_text(signal.get("title"), 160),
            "why_today": _plain_text(signal.get("why_trending"), 400)
            or "Based on the latest saved evidence-backed creative signal.",
            "idea": _plain_text(signal.get("suggested_adaptation"), 700),
            "hook": _plain_text(signal.get("how_it_works"), 400),
            "format": "15-second vertical video",
            "execution_steps": [
                "0-3s: apply the signal as an original opening hook",
                "3-10s: demonstrate the product clearly",
                "10-15s: resolve with an approved CTA",
            ],
            "event_name": None,
            "confidence": _plain_text(signal.get("confidence"), 30) or "low",
        }
    if trend:
        return {
            "title": _plain_text(trend.get("title"), 160),
            "why_today": "Adapted from the latest saved public trend reference.",
            "idea": "Borrow the pacing and format, not the creator's identity or copyrighted assets.",
            "hook": "Start with a recognisable format pattern, then pivot immediately to the product.",
            "format": "15-second vertical video",
            "execution_steps": [
                "0-3s: original pattern-based hook",
                "3-10s: product demonstration",
                "10-15s: concise approved CTA",
            ],
            "event_name": None,
            "confidence": "cached-signal",
        }
    return {
        "title": "Show the proof behind the product",
        "why_today": (
            "No verified live trend signal is saved today, so this is explicitly an evergreen "
            "creative fallback—not a claimed trend."
        ),
        "idea": "Show one real preparation, production, packing, or service detail that customers rarely see.",
        "hook": "Open with the most visually satisfying behind-the-scenes action.",
        "format": "15-second vertical video",
        "execution_steps": [
            "0-3s: unexpected behind-the-scenes action",
            "3-10s: demonstrate the real process",
            "10-15s: product result and approved CTA",
        ],
        "event_name": None,
        "confidence": "evergreen-fallback",
    }


def _generate_idea(
    inputs: dict[str, list[dict[str, Any]]],
    *,
    today: date,
    market: str,
) -> dict[str, Any]:
    # The source research is already AI-assisted and evidence-backed. Combining it
    # deterministically here keeps the daily endpoint fast, private, and immune to
    # another model quota failure.
    return _fallback_idea(inputs, today=today, market=market)


async def get_daily_creative_idea(market: str = "malaysia") -> dict[str, Any]:
    """Return one immutable idea for the market's current calendar day."""
    normalized_market = _plain_text(market, 50).lower() or "malaysia"
    now, timezone_name = _market_clock(normalized_market)
    idea_date = now.date().isoformat()
    cached = await asyncio.to_thread(_load_persisted_idea, idea_date, normalized_market)
    if cached:
        return cached

    async with _LOCK:
        cached = await asyncio.to_thread(_load_persisted_idea, idea_date, normalized_market)
        if cached:
            return cached
        inputs = await asyncio.to_thread(_saved_inputs, normalized_market, now.date())
        idea = await asyncio.to_thread(
            _generate_idea,
            inputs,
            today=now.date(),
            market=normalized_market,
        )
        tomorrow = now.date() + timedelta(days=1)
        timezone_info, _ = _market_timezone(normalized_market)
        expires_at = datetime.combine(
            tomorrow,
            time.min,
            tzinfo=timezone_info,
        )
        payload = {
            **idea,
            "idea_date": idea_date,
            "market": normalized_market,
            "timezone": timezone_name,
            "generated_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "source_urls": _source_urls(inputs),
            "locked_for_day": True,
        }
        await asyncio.to_thread(_persist_idea, idea_date, normalized_market, payload)
        return payload
