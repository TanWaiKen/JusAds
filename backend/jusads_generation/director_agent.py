"""
director_agent.py
─────────────────
Director Agent — plans creative strategy with trend data and requires
human approval before dispatching to Media Agents.

Flow:
  1. Query trends_cache for relevant trending content
  2. Correlate with upcoming cultural events
  3. Generate a CreativePlan via Gemini
  4. Present plan for human approval (interrupt)
  5. On approval → proceed to generation fan-out
  6. On rejection → revise plan based on feedback

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 8.2, 8.3, 11.2
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, TypedDict

from shared.clients import gemini, supabase
from shared.config import MODEL_TEXT
from jusads_generation.search_tools import resolve_target_language

logger = logging.getLogger(__name__)


# --- TypedDicts ---------------------------------------------------------------


class CreativePlan(TypedDict):
    """Structured creative strategy output requiring human approval."""

    target_platforms: list[str]
    media_types: list[str]
    trend_references: list[dict]
    creative_direction: str
    target_language: str
    cultural_event_refs: list[dict]


class DirectorState(TypedDict):
    """LangGraph state for the Director Agent planning phase."""

    project_id: str
    task_id: str
    user_message: str
    market: str
    platform: str
    ethnicity: str
    age_group: str
    language: str
    trends_data: list[dict]
    creative_plan: dict
    approval_status: str
    feedback: str
    generated_ads: list[dict]


# --- Public API ---------------------------------------------------------------


async def plan_creative_strategy(
    brief: str,
    market: str = "malaysia",
    platform: str = "instagram",
    ethnicity: str = "all",
    age_group: str = "all_ages",
    product_name: str = "",
    product_category: str = "",
) -> CreativePlan:
    """Generate a creative plan incorporating trend data and cultural events.

    Queries trends_cache for relevant trends, correlates with cultural events,
    and produces a structured plan for human approval.

    Args:
        brief: The user's campaign brief.
        market: Target market.
        platform: Target platform.
        ethnicity: Target ethnicity.
        age_group: Target age group.
        product_name: Product/brand name.
        product_category: Product category.

    Returns:
        A CreativePlan dict with all required fields.
    """
    # Resolve target language
    target_language = resolve_target_language(market, ethnicity)

    # Fetch trending data
    trends_data = _fetch_relevant_trends(platform, market)

    # Fetch upcoming cultural events
    cultural_events = _fetch_upcoming_events(market)

    # Build the plan via Gemini
    plan = await _generate_plan_with_ai(
        brief=brief,
        market=market,
        platform=platform,
        ethnicity=ethnicity,
        age_group=age_group,
        target_language=target_language,
        trends_data=trends_data,
        cultural_events=cultural_events,
        product_name=product_name,
        product_category=product_category,
    )

    return plan


async def revise_plan(
    original_plan: CreativePlan,
    feedback: str,
    brief: str = "",
) -> CreativePlan:
    """Revise the creative plan based on human feedback.

    Args:
        original_plan: The plan that was rejected/modified.
        feedback: Human feedback text.
        brief: Original brief for context.

    Returns:
        A revised CreativePlan.
    """
    from google.genai import types as genai_types

    prompt = f"""You are a Creative Director AI. The user rejected your previous creative plan
and provided this feedback:

FEEDBACK: {feedback}

ORIGINAL PLAN:
{json.dumps(original_plan, indent=2)}

ORIGINAL BRIEF: {brief}

Revise the plan to address the feedback. Return a JSON object with:
{{
  "target_platforms": ["platform1"],
  "media_types": ["text", "image", "video", "audio"],
  "trend_references": [{{"title": "...", "url": "...", "platform": "...", "relevance": "..."}}],
  "creative_direction": "Revised creative strategy...",
  "target_language": "{original_plan.get('target_language', 'en')}",
  "cultural_event_refs": [{{"name": "...", "dates": "...", "tags": ["..."]}}]
}}"""

    try:
        response = gemini.models.generate_content(
            model=MODEL_TEXT,
            contents=prompt,
            config=genai_types.GenerateContentConfig(response_mime_type="application/json"),
        )
        revised = json.loads(response.text)
        return _validate_plan(revised, original_plan.get("target_language", "en"))
    except Exception as e:
        logger.error("[DirectorAgent] Plan revision failed: %s", e)
        # Return original plan unchanged on failure
        return original_plan


# --- Private Helpers ----------------------------------------------------------


def _fetch_relevant_trends(platform: str, market: str, limit: int = 10) -> list[dict]:
    """Fetch trending content from trends_cache, prioritizing cultural-event-tagged items.

    Items tagged with upcoming cultural events appear first.
    Returns up to `limit` items.
    """
    if not supabase:
        return []

    try:
        # First: items with cultural event tags (prioritized)
        tagged_resp = (
            supabase.table("trends_cache")
            .select("title, url, platform, engagement_metrics, cultural_event_tag, hashtags")
            .eq("platform", platform)
            .eq("market", market)
            .not_.is_("cultural_event_tag", "null")
            .order("scraped_at", desc=True)
            .limit(5)
            .execute()
        )
        tagged = tagged_resp.data or []

        # Then: general trending items
        remaining = limit - len(tagged)
        if remaining > 0:
            general_resp = (
                supabase.table("trends_cache")
                .select("title, url, platform, engagement_metrics, cultural_event_tag, hashtags")
                .eq("platform", platform)
                .eq("market", market)
                .order("scraped_at", desc=True)
                .limit(remaining)
                .execute()
            )
            general = general_resp.data or []
        else:
            general = []

        # Combine: tagged first, then general (deduplicated)
        seen_urls = set()
        combined = []
        for item in tagged + general:
            url = item.get("url", "")
            if url not in seen_urls:
                seen_urls.add(url)
                combined.append(item)

        return combined[:limit]

    except Exception as e:
        logger.warning("[DirectorAgent] Failed to fetch trends: %s", e)
        return []


def _fetch_upcoming_events(market: str, window_days: int = 30) -> list[dict]:
    """Fetch cultural events within the next window_days."""
    if not supabase:
        return []

    try:
        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")
        window_end = (now + timedelta(days=window_days)).strftime("%Y-%m-%d")

        response = (
            supabase.table("cultural_events")
            .select("name, start_date, end_date, event_type, tags, impact_score")
            .eq("market", market)
            .gte("end_date", today)
            .lte("start_date", window_end)
            .order("start_date", desc=False)
            .limit(5)
            .execute()
        )
        return response.data or []

    except Exception as e:
        logger.warning("[DirectorAgent] Failed to fetch cultural events: %s", e)
        return []


async def _generate_plan_with_ai(
    brief: str,
    market: str,
    platform: str,
    ethnicity: str,
    age_group: str,
    target_language: str,
    trends_data: list[dict],
    cultural_events: list[dict],
    product_name: str,
    product_category: str,
) -> CreativePlan:
    """Use Gemini to generate a structured creative plan."""
    from google.genai import types as genai_types

    trends_summary = json.dumps(trends_data[:5], indent=2) if trends_data else "No trend data available."
    events_summary = json.dumps(cultural_events[:3], indent=2) if cultural_events else "No upcoming events."

    prompt = f"""You are a Creative Director AI planning an advertising campaign.

CAMPAIGN BRIEF: {brief}
PRODUCT: {product_name or 'Not specified'} ({product_category or 'general'})
TARGET MARKET: {market}
TARGET PLATFORM: {platform}
TARGET AUDIENCE: {ethnicity} ethnicity, {age_group} age group
TARGET LANGUAGE: {target_language}

CURRENT TRENDING CONTENT ({platform}):
{trends_summary}

UPCOMING CULTURAL EVENTS:
{events_summary}

Create a creative strategy plan. Return a JSON object:
{{
  "target_platforms": ["{platform}"],
  "media_types": ["list of media types to generate: text, image, audio, video"],
  "trend_references": [up to 5 items: {{"title": "...", "url": "...", "platform": "...", "relevance": "why this trend matters"}}],
  "creative_direction": "A 2-3 sentence creative strategy describing the tone, style, and key message",
  "target_language": "{target_language}",
  "cultural_event_refs": [relevant events: {{"name": "...", "dates": "start - end", "tags": ["..."]}}]
}}

Rules:
- trend_references: max 5 items from the trending data above (or empty if none relevant)
- media_types: at least 1, based on what makes sense for the brief
- creative_direction: must be actionable and specific
- cultural_event_refs: only include if relevant to the campaign timing"""

    try:
        response = gemini.models.generate_content(
            model=MODEL_TEXT,
            contents=prompt,
            config=genai_types.GenerateContentConfig(response_mime_type="application/json"),
        )
        plan_data = json.loads(response.text)
        return _validate_plan(plan_data, target_language)

    except Exception as e:
        logger.error("[DirectorAgent] AI plan generation failed: %s", e)
        # Return a minimal valid plan as fallback
        return CreativePlan(
            target_platforms=[platform],
            media_types=["text", "image"],
            trend_references=[],
            creative_direction=f"Create a compelling {platform} ad for: {brief}",
            target_language=target_language,
            cultural_event_refs=[],
        )


def _validate_plan(raw: dict, default_language: str) -> CreativePlan:
    """Validate and sanitize a raw plan dict into a proper CreativePlan."""
    trend_refs = raw.get("trend_references", [])
    if isinstance(trend_refs, list):
        trend_refs = trend_refs[:5]  # Cap at 5
    else:
        trend_refs = []

    return CreativePlan(
        target_platforms=raw.get("target_platforms", ["instagram"]) or ["instagram"],
        media_types=raw.get("media_types", ["text", "image"]) or ["text", "image"],
        trend_references=trend_refs,
        creative_direction=raw.get("creative_direction", "") or "Generate creative ad content.",
        target_language=raw.get("target_language", default_language) or default_language,
        cultural_event_refs=raw.get("cultural_event_refs", []) or [],
    )
