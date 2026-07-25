"""
hook_search.py
──────────────
YouTube Hook Video Search — finds viral/meme transition clips for ad hooks.

This module is the **business logic layer** that sits on top of the standalone
YouTube client library (``shared.youtube_client``). It adds:

  - Style-aware search query building
  - Preference learning via association rules
  - Relevance scoring and reranking
  - Hook tag taxonomy

The YouTube API details (auth, endpoints, pagination) are handled entirely by
``shared.youtube_client.YouTubeClient``.

Usage::

    from jusads_generation.hook_search import search_hook_videos, learn_preference

    results = await search_hook_videos(
        query="funny transition meme",
        market="malaysia",
        max_results=5,
    )

    learn_preference(user_id="abc", selected_video_id="xyz", tags=["car_crash", "transition"])
"""

import asyncio
import logging
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Optional

from shared.youtube_client import YouTubeClient, VideoSearchResult as YTSearchResult, get_client as get_youtube_client

logger = logging.getLogger(__name__)

# --- Configuration ------------------------------------------------------------

# Market-to-region mapping for YouTube API
_MARKET_REGION_MAP: dict[str, str] = {
    "malaysia": "MY",
    "singapore": "SG",
}

# Market-to-language mapping for relevance language bias
_MARKET_LANGUAGE_MAP: dict[str, str] = {
    "malaysia": "ms",
    "singapore": "en",
}

# Default hook search categories — these produce viral Shorts-style clips
_HOOK_QUERY_TEMPLATES: dict[str, list[str]] = {
    "meme_shock": [
        "funny transition meme ad viral",
        "unexpected product reveal transition tiktok",
        "car crash transition meme commercial",
        "shock reveal ad transition",
        "meme hook marketing viral clip",
    ],
    "culture_anchor": [
        "{market} festival celebration ad",
        "{market} traditional food commercial",
        "{ethnicity} cultural celebration",
    ],
    "problem_punchline": [
        "relatable problem ad funny reveal",
        "before after transformation ad",
        "struggle then solution commercial meme",
    ],
    "testimonial_burst": [
        "multiple reactions product review",
        "rapid testimonial montage ad",
        "customer reaction compilation commercial",
    ],
    "product_hero": [
        "satisfying product video ASMR",
        "product closeup cinematic food",
        "unboxing satisfying macro shot",
    ],
}

# Hook style tags for preference learning
HOOK_TAGS: list[str] = [
    "car_crash_transition",
    "person_flying",
    "meme_face_cut",
    "shock_reveal",
    "unexpected_object",
    "sound_sync_drop",
    "before_after",
    "rapid_fire_cuts",
    "text_hook_overlay",
    "reaction_face",
    "product_slam",
    "cultural_moment",
]

# --- Types --------------------------------------------------------------------


class HookVideoResult:
    """A single YouTube video result suitable as an ad hook reference."""

    def __init__(
        self,
        video_id: str,
        title: str,
        thumbnail_url: str,
        channel: str,
        duration_label: str = "",
        view_count: int = 0,
        tags: Optional[list[str]] = None,
        relevance_score: float = 0.0,
    ):
        self.video_id = video_id
        self.title = title
        self.thumbnail_url = thumbnail_url
        self.channel = channel
        self.duration_label = duration_label
        self.view_count = view_count
        self.tags = tags or []
        self.relevance_score = relevance_score

    @property
    def url(self) -> str:
        """Full YouTube watch URL."""
        return f"https://www.youtube.com/watch?v={self.video_id}"

    @property
    def short_url(self) -> str:
        """Short YouTube URL."""
        return f"https://youtu.be/{self.video_id}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API response or persistence."""
        return {
            "video_id": self.video_id,
            "title": self.title,
            "url": self.url,
            "thumbnail_url": self.thumbnail_url,
            "channel": self.channel,
            "duration_label": self.duration_label,
            "view_count": self.view_count,
            "tags": self.tags,
            "relevance_score": self.relevance_score,
        }


# --- Core Search Function -----------------------------------------------------


async def search_hook_videos(
    query: str = "",
    creative_style: str = "meme_shock",
    market: str = "malaysia",
    ethnicity: str = "all",
    product_category: str = "",
    max_results: int = 8,
    duration_filter: str = "short",
    user_id: Optional[str] = None,
) -> list[HookVideoResult]:
    """Search YouTube Shorts for hook/transition videos.

    Uses the standalone YouTubeClient's ``search_shorts`` method to find
    only Shorts (≤60 seconds) — no long-form videos. These serve as creative
    references for the ad Director's hook scene.

    Args:
        query: Optional custom search query. If empty, uses template queries
            based on creative_style.
        creative_style: The active localize plan strategy (determines default
            search queries).
        market: Target market for locale-specific results.
        ethnicity: Target ethnicity for cultural relevance.
        product_category: Product category to refine search terms.
        max_results: Maximum number of results to return (1–20).
        duration_filter: Ignored — always searches Shorts only (≤60s).
        user_id: Optional user ID to apply learned preferences for reranking.

    Returns:
        List of HookVideoResult objects sorted by relevance.
        Empty list if API key is missing or search fails.
    """
    client = get_youtube_client()
    if not client.is_configured:
        logger.warning("[HookSearch] YouTube client not configured — skipping search")
        return []

    # Build search queries
    queries = _build_search_queries(
        query=query,
        creative_style=creative_style,
        market=market,
        ethnicity=ethnicity,
        product_category=product_category,
    )

    # Execute searches (limit to 3 queries to stay within quota)
    all_results: list[HookVideoResult] = []
    region_code = _MARKET_REGION_MAP.get(market.lower(), None)
    search_queries = queries[:3]

    for search_query in search_queries:
        try:
            # Use search_shorts — only returns YouTube Shorts (≤60 seconds)
            videos = await asyncio.to_thread(
                client.search_shorts,
                query=search_query,
                max_results=max_results,
                region_code=region_code,
                order="relevance",
                strict_duration=True,
            )
            for video in videos:
                relevance = _compute_relevance(video.title, search_query)
                all_results.append(HookVideoResult(
                    video_id=video.video_id,
                    title=video.title,
                    thumbnail_url=video.thumbnail_high_url or video.thumbnail_url,
                    channel=video.channel_title,
                    relevance_score=relevance,
                ))
        except Exception as exc:
            logger.warning("[HookSearch] Search query failed: %s — %s", search_query[:50], exc)

    # Deduplicate by video_id
    seen: set[str] = set()
    unique_results: list[HookVideoResult] = []
    for video in all_results:
        if video.video_id not in seen:
            seen.add(video.video_id)
            unique_results.append(video)

    # Rerank by user preferences if available
    if user_id:
        unique_results = _rerank_by_preference(unique_results, user_id)

    # Sort by relevance score (descending) and trim
    unique_results.sort(key=lambda v: v.relevance_score, reverse=True)
    return unique_results[:max_results]


async def get_video_details(video_ids: list[str]) -> list[dict[str, Any]]:
    """Fetch detailed metadata for specific video IDs.

    Uses the standalone YouTubeClient to get full details (duration, tags,
    statistics) for the generation pipeline.

    Args:
        video_ids: List of YouTube video IDs to fetch details for.

    Returns:
        List of video detail dicts with duration, view_count, tags, etc.
    """
    client = get_youtube_client()
    if not client.is_configured or not video_ids:
        return []

    try:
        details = await asyncio.to_thread(client.get_video_details, video_ids[:10])
        return [d.to_dict() for d in details]
    except Exception as exc:
        logger.error("[HookSearch] Video details fetch failed: %s", exc)
        return []


# --- Preference Learning (Association Rules) ----------------------------------

# In-memory preference store (persisted to Supabase when available)
_user_preferences: dict[str, list[dict]] = defaultdict(list)


def learn_preference(
    user_id: str,
    selected_video_id: str,
    tags: list[str],
    creative_style: str = "meme_shock",
    product_category: str = "",
) -> None:
    """Record a user's hook video preference for future reranking.

    Uses a simple association rules approach:
    - Track which tags/styles the user selects repeatedly
    - Build a frequency profile per user
    - Use this to boost matching videos in future searches

    This is lightweight collaborative filtering — no heavy ML needed.
    The pattern: {user} selects {tags} → next search boosts {similar tags}.

    Args:
        user_id: The user identifier.
        selected_video_id: YouTube video ID the user chose.
        tags: Hook style tags associated with the selection.
        creative_style: The creative strategy active when selected.
        product_category: Product category context when selected.
    """
    preference = {
        "video_id": selected_video_id,
        "tags": tags,
        "creative_style": creative_style,
        "product_category": product_category,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _user_preferences[user_id].append(preference)

    # Persist to Supabase if available
    _persist_preference_async(user_id, preference)

    logger.info(
        "[HookSearch] Learned preference for user %s: tags=%s, style=%s",
        user_id[:8], tags, creative_style,
    )


def get_user_tag_profile(user_id: str) -> dict[str, float]:
    """Get a user's learned tag preference profile.

    Returns a dict of {tag: weight} where weight is normalized frequency
    (0.0–1.0). Tags selected more often get higher weights.

    This profile drives the reranking algorithm — videos with tags matching
    the user's profile get a relevance boost.

    Args:
        user_id: The user identifier.

    Returns:
        Dict mapping tag names to normalized weights (0.0–1.0).
    """
    prefs = _user_preferences.get(user_id, [])
    if not prefs:
        return {}

    # Count tag frequencies
    tag_counts: Counter = Counter()
    for pref in prefs:
        for tag in pref.get("tags", []):
            tag_counts[tag] += 1

    if not tag_counts:
        return {}

    # Normalize to 0.0–1.0 range
    max_count = max(tag_counts.values())
    return {tag: count / max_count for tag, count in tag_counts.items()}


def suggest_hook_tags_for_brief(
    brief: str,
    creative_style: str = "meme_shock",
) -> list[str]:
    """Suggest hook tags based on an ad brief and creative style.

    Uses keyword matching to recommend which hook styles might work for the
    given campaign. This drives the initial search before user preferences
    are established.

    Args:
        brief: The ad campaign brief text.
        creative_style: The active creative strategy.

    Returns:
        List of suggested HOOK_TAGS relevant to the brief.
    """
    brief_lower = brief.lower()
    suggestions: list[str] = []

    # Style-based defaults
    style_defaults: dict[str, list[str]] = {
        "meme_shock": ["car_crash_transition", "person_flying", "meme_face_cut", "shock_reveal"],
        "culture_anchor": ["cultural_moment", "reaction_face"],
        "problem_punchline": ["before_after", "text_hook_overlay"],
        "testimonial_burst": ["reaction_face", "rapid_fire_cuts"],
        "speaker_led": ["text_hook_overlay"],
        "product_hero": ["product_slam", "sound_sync_drop"],
    }
    suggestions.extend(style_defaults.get(creative_style, ["shock_reveal"]))

    # Brief keyword matching
    keyword_tag_map: dict[str, str] = {
        "car": "car_crash_transition",
        "crash": "car_crash_transition",
        "fly": "person_flying",
        "meme": "meme_face_cut",
        "shock": "shock_reveal",
        "surprise": "unexpected_object",
        "beat": "sound_sync_drop",
        "music": "sound_sync_drop",
        "before": "before_after",
        "after": "before_after",
        "fast": "rapid_fire_cuts",
        "reaction": "reaction_face",
        "slam": "product_slam",
        "festival": "cultural_moment",
        "raya": "cultural_moment",
        "cny": "cultural_moment",
    }
    for keyword, tag in keyword_tag_map.items():
        if keyword in brief_lower and tag not in suggestions:
            suggestions.append(tag)

    return suggestions[:6]


# --- Internal Helpers ---------------------------------------------------------


def _build_search_queries(
    query: str,
    creative_style: str,
    market: str,
    ethnicity: str,
    product_category: str,
) -> list[str]:
    """Build YouTube search queries from style templates + user input."""
    queries: list[str] = []

    # User's custom query first (if provided)
    if query.strip():
        queries.append(query.strip())

    # Add template queries for the style
    templates = _HOOK_QUERY_TEMPLATES.get(creative_style, _HOOK_QUERY_TEMPLATES["meme_shock"])
    for template in templates:
        formatted = template.format(
            market=market,
            ethnicity=ethnicity,
            product_category=product_category,
        )
        queries.append(formatted)

    # Add product-specific query if category provided
    if product_category:
        category_labels = {
            "food_beverage": "food",
            "fashion": "fashion",
            "beauty": "beauty",
            "tech": "tech gadget",
            "health": "health",
        }
        label = category_labels.get(product_category, product_category)
        queries.append(f"{label} ad hook viral transition {market}")

    return queries


def _compute_relevance(title: str, query: str) -> float:
    """Score relevance of a video title against the search query.

    Simple keyword overlap scoring — higher score = more relevant.
    """
    title_words = set(title.lower().split())
    query_words = set(query.lower().split())

    if not query_words:
        return 0.5

    overlap = len(title_words & query_words)
    score = overlap / len(query_words)

    # Boost for viral/hook indicators in title
    boost_keywords = {"transition", "meme", "viral", "hook", "ad", "commercial", "shocking"}
    bonus = len(title_words & boost_keywords) * 0.1

    return min(1.0, score + bonus)


def _rerank_by_preference(
    results: list[HookVideoResult],
    user_id: str,
) -> list[HookVideoResult]:
    """Boost videos that match the user's learned tag preferences.

    Association rules approach:
    - Get user's tag profile (frequency-weighted)
    - For each video, check if its tags overlap with preferred tags
    - Add a preference boost to relevance_score

    This is simple but effective for personalization without heavy ML.
    """
    profile = get_user_tag_profile(user_id)
    if not profile:
        return results

    for video in results:
        preference_boost = sum(
            profile.get(tag, 0.0) * 0.3  # Max 0.3 boost per matching tag
            for tag in video.tags
        )
        video.relevance_score = min(1.0, video.relevance_score + preference_boost)

    return results


def _persist_preference_async(user_id: str, preference: dict) -> None:
    """Persist preference to Supabase (fire-and-forget).

    Stores in hook_preferences table. Non-blocking — failures are logged
    but don't interrupt the user flow.
    """
    try:
        from shared.clients import supabase
        if not supabase:
            return

        supabase.table("hook_preferences").insert({
            "user_id": user_id,
            "video_id": preference["video_id"],
            "tags": preference["tags"],
            "creative_style": preference["creative_style"],
            "product_category": preference["product_category"],
            "created_at": preference["timestamp"],
        }).execute()
    except Exception as exc:
        logger.debug("[HookSearch] Preference persist failed (non-critical): %s", exc)


async def load_user_preferences(user_id: str) -> None:
    """Load persisted preferences from Supabase into memory.

    Called once per session to hydrate the in-memory preference store.
    Silently no-ops if Supabase is unavailable.
    """
    try:
        from shared.clients import supabase
        if not supabase:
            return

        resp = (
            supabase.table("hook_preferences")
            .select("video_id, tags, creative_style, product_category, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        if resp.data:
            _user_preferences[user_id] = [
                {
                    "video_id": row["video_id"],
                    "tags": row["tags"] if isinstance(row["tags"], list) else [],
                    "creative_style": row.get("creative_style", ""),
                    "product_category": row.get("product_category", ""),
                    "timestamp": row.get("created_at", ""),
                }
                for row in resp.data
            ]
            logger.info(
                "[HookSearch] Loaded %d preferences for user %s",
                len(resp.data), user_id[:8],
            )
    except Exception as exc:
        logger.debug("[HookSearch] Preference load failed (non-critical): %s", exc)
