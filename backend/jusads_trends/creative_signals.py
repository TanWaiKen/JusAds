"""Evidence-backed creative trend signal research and persistence."""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, TypedDict
from urllib.parse import urlparse

from google.genai import types as genai_types

from jusads_compliance.agents.research import google_grounded_research
from shared.clients import gemini, supabase
from shared.config import MODEL_TEXT

logger = logging.getLogger(__name__)

SIGNAL_TYPES = {
    "sound", "music", "dance_or_challenge", "hook", "meme_or_phrase",
    "format_or_template", "visual_style", "creator_behavior",
    "hashtag_or_topic", "seasonal_or_cultural_moment",
}
MOMENTUM_VALUES = {"rising", "peaking", "stable", "declining", "unknown"}
CONFIDENCE_VALUES = {"low", "medium", "high"}


class CreativeTrendSignal(TypedDict):
    """A reusable, source-backed creative pattern for campaign ideation."""

    id: str
    signal_type: str
    title: str
    summary: str
    why_trending: str
    how_it_works: str
    suggested_adaptation: str
    do_not_do: str
    target_platforms: list[str]
    audience: str
    language: str
    momentum: str
    confidence: str
    evidence_urls: list[str]
    detected_at: str


class CreativeSignalError(RuntimeError):
    """Raised when creative signal research or persistence is unavailable."""


def _text(value: Any, limit: int = 1200) -> str:
    """Return a trimmed plain-text value suitable for persisted signal fields."""
    return str(value or "").strip()[:limit]


def _strings(value: Any, limit: int = 8) -> list[str]:
    """Return a bounded list of non-empty string values."""
    if not isinstance(value, list):
        return []
    return [_text(item, 120) for item in value if _text(item, 120)][:limit]


def _valid_evidence_urls(sources: list[dict[str, Any]]) -> list[str]:
    """Deduplicate valid HTTPS source URLs collected by grounded research."""
    urls: list[str] = []
    for source in sources:
        url = _text(source.get("url"), 2000)
        parsed = urlparse(url)
        if parsed.scheme == "https" and parsed.netloc and url not in urls:
            urls.append(url)
    return urls[:10]


def _normalise_signal(raw: dict[str, Any], evidence_urls: list[str]) -> CreativeTrendSignal | None:
    """Validate an AI candidate without manufacturing missing evidence or facts."""
    signal_type = _text(raw.get("signal_type"), 80).lower()
    if signal_type not in SIGNAL_TYPES:
        return None
    title = _text(raw.get("title"), 240)
    summary = _text(raw.get("summary"))
    adaptation = _text(raw.get("suggested_adaptation"))
    raw_evidence_urls = raw.get("evidence_urls")
    candidate_evidence_urls = (
        [_text(url, 2000) for url in raw_evidence_urls if _text(url, 2000)]
        if isinstance(raw_evidence_urls, list) else []
    )
    evidence_urls = [url for url in candidate_evidence_urls if url in evidence_urls]
    if not title or not summary or not adaptation or not evidence_urls:
        return None
    momentum = _text(raw.get("momentum"), 30).lower()
    confidence = _text(raw.get("confidence"), 30).lower()
    return {
        "id": str(uuid.uuid4()),
        "signal_type": signal_type,
        "title": title,
        "summary": summary,
        "why_trending": _text(raw.get("why_trending")),
        "how_it_works": _text(raw.get("how_it_works")),
        "suggested_adaptation": adaptation,
        "do_not_do": _text(raw.get("do_not_do")),
        "target_platforms": _strings(raw.get("target_platforms")),
        "audience": _text(raw.get("audience"), 300),
        "language": _text(raw.get("language"), 80),
        "momentum": momentum if momentum in MOMENTUM_VALUES else "unknown",
        "confidence": confidence if confidence in CONFIDENCE_VALUES else "low",
        "evidence_urls": evidence_urls,
        "detected_at": datetime.now(timezone.utc).isoformat(),
    }


def _extract_signals(report: str, evidence_urls: list[str], market: str, platform: str) -> list[CreativeTrendSignal]:
    """Use Gemini to turn grounded evidence into bounded, safe creative signals."""
    if gemini is None:
        raise CreativeSignalError("Creative signal research is unavailable")
    evidence_catalog = "\n".join(f"- {url}" for url in evidence_urls)
    prompt = f"""You are a creative-trend analyst for culturally safe advertising.

MARKET: {market}
PLATFORM: {platform or 'multiple social platforms'}
GROUNDED RESEARCH REPORT:
{report[:6000]}

VERIFIED SOURCE URLS:
{evidence_catalog}

Return a JSON array of at most 8 actionable creative signals. A signal may be a sound/music cue, dance/challenge, opening hook, meme/phrase, recurring creator behavior, reusable content format/template, visual style, hashtag/topic, or seasonal/cultural moment.

Every signal must be grounded in the supplied report. Do not invent song names, artists, sound IDs, metrics, post URLs, audience claims, or trend momentum. When evidence is insufficient, omit the signal. Do not suggest copyrighted music reproduction; describe a safe creative direction instead.

Each object must contain:
- signal_type: one of sound, music, dance_or_challenge, hook, meme_or_phrase, format_or_template, visual_style, creator_behavior, hashtag_or_topic, seasonal_or_cultural_moment
- title, summary, why_trending, how_it_works, suggested_adaptation, do_not_do
- target_platforms: string array
- audience, language
- momentum: rising, peaking, stable, declining, or unknown
- confidence: low, medium, or high
- evidence_urls: array containing only URLs from the grounded report that support this specific signal

For suggested_adaptation, explain how a brand can adapt the pattern without copying a creator. For do_not_do, include cultural, policy, safety, or intellectual-property cautions when applicable. Return only JSON."""
    try:
        response = gemini.models.generate_content(
            model=MODEL_TEXT,
            contents=prompt,
            config=genai_types.GenerateContentConfig(response_mime_type="application/json"),
        )
        raw = json.loads((response.text or "").replace("```json", "").replace("```", "").strip())
    except Exception as exc:
        logger.exception("[CreativeSignals] Signal extraction failed")
        raise CreativeSignalError("Creative signal analysis is unavailable") from exc
    if not isinstance(raw, list):
        return []
    return [signal for item in raw[:8] if isinstance(item, dict)
            if (signal := _normalise_signal(item, evidence_urls)) is not None]


def _to_record(signal: CreativeTrendSignal, market: str, owner_email: str) -> dict[str, Any]:
    """Map an API signal to the database record used by Supabase."""
    return {
        "id": signal["id"],
        "signal_type": signal["signal_type"],
        "title": signal["title"],
        "summary": signal["summary"],
        "why_trending": signal["why_trending"],
        "how_it_works": signal["how_it_works"],
        "suggested_adaptation": signal["suggested_adaptation"],
        "do_not_do": signal["do_not_do"],
        "target_platforms": signal["target_platforms"],
        "market": market,
        "owner_email": owner_email or None,
        "audience": signal["audience"],
        "language": signal["language"],
        "momentum": signal["momentum"],
        "confidence": signal["confidence"],
        "detected_at": signal["detected_at"],
    }


async def research_creative_signals(market: str, platform: str, owner_email: str) -> list[CreativeTrendSignal]:
    """Research, validate, and persist evidence-backed creative trend signals."""
    query = (
        f"current {platform or 'social media'} creative trends in {market}: sounds, music, "
        "dances, challenges, opening hooks, meme phrases, recurring creator behaviours, "
        "and reusable content formats. Include only current public evidence."
    )
    research = await asyncio.to_thread(
        google_grounded_research,
        query,
        "Find current creative patterns that could inspire ads. Provide public evidence links and "
        "distinguish verified observations from speculation. Do not fabricate music or trend metrics.",
    )
    evidence_urls = _valid_evidence_urls(research.get("sources", [])) if research else []
    if not research or not evidence_urls:
        raise CreativeSignalError("No evidence-backed creative trend signals are currently available")
    signals = await asyncio.to_thread(
        _extract_signals, research.get("content", ""), evidence_urls, market, platform
    )
    if not signals:
        raise CreativeSignalError("No evidence-backed creative trend signals were identified")
    if supabase is None:
        logger.warning("[CreativeSignals] Supabase unavailable; returning non-persisted signals")
        return signals
    try:
        delete_query = supabase.table("creative_trend_signals").delete().eq("market", market)
        delete_query = delete_query.eq("owner_email", owner_email) if owner_email else delete_query.is_("owner_email", "null")
        if platform:
            delete_query = delete_query.contains("target_platforms", [platform])
        delete_query.execute()
        supabase.table("creative_trend_signals").insert(
            [_to_record(signal, market, owner_email) for signal in signals]
        ).execute()
        source_rows = [
            {"signal_id": signal["id"], "url": url, "source_title": "Grounded research evidence"}
            for signal in signals for url in signal["evidence_urls"]
        ]
        supabase.table("creative_trend_sources").insert(source_rows).execute()
    except Exception:
        # The migration may not be applied yet, or storage may be temporarily
        # unavailable. The grounded signals remain useful for this request, but
        # are deliberately not represented as saved cache entries.
        logger.exception("[CreativeSignals] Persistence failed; returning ephemeral signals")
        return signals
    return signals


def fetch_creative_signals(market: str, platform: str, owner_email: str, limit: int) -> list[CreativeTrendSignal]:
    """Return previously persisted signals with their evidence URLs."""
    if supabase is None:
        raise CreativeSignalError("Creative trend storage is unavailable")
    try:
        query = supabase.table("creative_trend_signals").select(
            "*, creative_trend_sources(url)"
        ).eq("market", market)
        query = query.eq("owner_email", owner_email) if owner_email else query.is_("owner_email", "null")
        if platform:
            query = query.contains("target_platforms", [platform])
        rows = query.order("detected_at", desc=True).limit(limit).execute().data or []
    except Exception as exc:
        logger.exception("[CreativeSignals] Fetch failed")
        raise CreativeSignalError("Creative signal storage is unavailable") from exc
    signals: list[CreativeTrendSignal] = []
    for row in rows:
        sources = row.get("creative_trend_sources") or []
        signals.append({
            "id": _text(row.get("id")), "signal_type": _text(row.get("signal_type")),
            "title": _text(row.get("title")), "summary": _text(row.get("summary")),
            "why_trending": _text(row.get("why_trending")), "how_it_works": _text(row.get("how_it_works")),
            "suggested_adaptation": _text(row.get("suggested_adaptation")), "do_not_do": _text(row.get("do_not_do")),
            "target_platforms": _strings(row.get("target_platforms")), "audience": _text(row.get("audience")),
            "language": _text(row.get("language")), "momentum": _text(row.get("momentum")) or "unknown",
            "confidence": _text(row.get("confidence")) or "low",
            "evidence_urls": [url for source in sources if (url := _text(source.get("url"), 2000))],
            "detected_at": _text(row.get("detected_at")),
        })
    return signals
