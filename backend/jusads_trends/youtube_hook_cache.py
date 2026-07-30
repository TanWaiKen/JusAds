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
_QUERY_WORD = re.compile(r"[A-Za-z0-9]+")
_GENERIC_CATEGORY_WORDS = frozenset({"product", "products", "service", "services", "other", "general"})


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


def _category_terms(category: str) -> list[str]:
    """Return meaningful category words suitable for a four-word query."""

    return [
        word.casefold()
        for word in _QUERY_WORD.findall(category)
        if len(word) > 1 and word.casefold() not in _GENERIC_CATEGORY_WORDS
    ][:2]


def normalise_hook_query(candidate: str, category: str) -> str | None:
    """Accept only short LLM queries that retain the product category.

    The LLM is allowed to choose hook language, but it must not turn a
    product-specific search into an unhelpful generic query such as
    ``Malaysia viral hooks``.
    """

    words = _QUERY_WORD.findall(candidate or "")
    if not words or len(words) > 4:
        return None
    category_terms = _category_terms(category)
    if category_terms and not any(word.casefold() in category_terms for word in words):
        return None
    return " ".join(words)


def _fallback_hook_query(category: str, company: str, market: str) -> str:
    category_words = _category_terms(category)
    if category_words:
        return " ".join([*category_words, _clean(market, 32) or "Malaysia", "hook"]).strip()
    fallback = _clean(company, 40) or "consumer product"
    return f"{fallback} {_clean(market, 32) or 'Malaysia'} marketing hook"[:100]


def build_hook_query(profile: dict[str, Any], market: str) -> str:
    """Build a YouTube query for popular short-form creative hook references."""
    category = _clean(profile.get("product_category"), 80)
    company = _clean(profile.get("company_name"), 80)
    description = _clean(profile.get("product_description"), 300)
    
    prompt = f"""You are an expert YouTube marketer. Generate a highly effective, short YouTube search query (maximum 4 words) to find viral, trending short-form advertising hooks in the {market.strip() or 'Malaysia'} market for this product.
Do NOT use quotes. Do NOT explain. Just return the raw query string.
If a category is provided, you MUST include at least one category word in the query.

Product/Company: {company}
Category: {category}
Description: {description}"""

    try:
        from shared.clients import gemini
        from shared.config import SMALL_TEXT_MODEL
        import logging
        if gemini:
            response = gemini.models.generate_content(
                model=SMALL_TEXT_MODEL,
                contents=prompt,
            )
            query = normalise_hook_query(response.text.strip().strip('"').strip("'"), category)
            if query:
                logging.getLogger(__name__).info("Generated AI YouTube query: %s", query)
                return query
            logging.getLogger(__name__).warning("AI query omitted the required category; using category-led fallback")
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("AI query generation failed, falling back to static query: %s", e)

    # Fallback to static generation
    return _fallback_hook_query(category, company, market)


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

