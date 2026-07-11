"""
search_tools.py
───────────────
Lightweight Google Search integration for generation agents.

Uses Gemini's built-in GoogleSearch tool (free, fast) for creative research.
This is the standard search tool for all generation agents — Tavily is reserved
for compliance-only deep research.

Requirements: 4.1–4.7, 5.1–5.4, 11.1–11.5
"""

import logging
from typing import Optional

from google.genai.types import GenerateContentConfig, GoogleSearch, Tool

from shared.clients import gemini
from shared.config import MODEL_TEXT

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

_GEMINI_MODEL = MODEL_TEXT

# Market-to-language mapping for content localization
_LANGUAGE_MAP: dict[tuple[str, str], str] = {
    ("malaysia", "malay"): "ms",
    ("malaysia", "chinese"): "zh",
    ("malaysia", "indian"): "ta",
    ("malaysia", "all"): "ms",
    ("singapore", "malay"): "ms",
    ("singapore", "chinese"): "zh",
    ("singapore", "indian"): "ta",
    ("singapore", "all"): "en",
}

_DEFAULT_LANGUAGE = "en"

# Language display names for search query localization
_LANGUAGE_LABELS: dict[str, str] = {
    "ms": "Bahasa Melayu",
    "zh": "Mandarin Chinese",
    "ta": "Tamil",
    "en": "English",
}


# ─── Public API ───────────────────────────────────────────────────────────────


def get_google_search_config() -> GenerateContentConfig:
    """Return GenerateContentConfig with GoogleSearch tool enabled.

    Used by all generation agents when they need creative research context.

    Returns:
        A GenerateContentConfig with the GoogleSearch tool attached.
    """
    return GenerateContentConfig(
        tools=[Tool(google_search=GoogleSearch())]
    )


def resolve_target_language(market: str, ethnicity: str) -> str:
    """Resolve the target output language from market and ethnicity.

    Mapping:
      - Malaysia + Malay → "ms" (Bahasa Melayu)
      - Malaysia + Chinese → "zh" (Mandarin)
      - Malaysia + Indian → "ta" (Tamil)
      - Singapore → "en" (English)
      - Unknown → "en" (fallback)

    Args:
        market: Target market (e.g. 'malaysia', 'singapore').
        ethnicity: Target ethnic group (e.g. 'malay', 'chinese', 'indian', 'all').

    Returns:
        ISO language code string.
    """
    key = (market.lower().strip(), ethnicity.lower().strip())
    return _LANGUAGE_MAP.get(key, _DEFAULT_LANGUAGE)


def derive_search_query(
    brief: str,
    product_category: str = "",
    market: str = "",
    theme: str = "",
    language: str = "en",
) -> str:
    """Construct a search query from ad brief metadata.

    Ensures the query contains at least one term from the brief's product
    category, market, or theme. Adds language context for non-English targets.

    Args:
        brief: The user's ad brief or campaign description.
        product_category: Product category (e.g. 'food_beverage').
        market: Target market (e.g. 'malaysia').
        theme: Campaign theme or hook.
        language: Target language code (e.g. 'ms', 'zh').

    Returns:
        A search query string for GoogleSearch.
    """
    parts: list[str] = []

    # Extract the first meaningful sentence from brief (max 60 chars)
    brief_snippet = brief.strip()[:60].split("\n")[0] if brief else ""
    if brief_snippet:
        parts.append(brief_snippet)

    # Add category context
    category_labels = {
        "food_beverage": "food and beverage",
        "fashion": "fashion apparel",
        "beauty": "beauty personal care",
        "tech": "technology gadgets",
        "health": "health wellness",
        "finance": "finance banking",
        "travel": "travel tourism",
        "education": "education",
        "automotive": "automotive",
        "entertainment": "entertainment",
        "ecommerce": "e-commerce retail",
    }
    if product_category:
        parts.append(category_labels.get(product_category, product_category))

    # Add market context
    if market:
        parts.append(f"{market} market")

    # Add theme
    if theme:
        parts.append(theme)

    # Add language context for non-English targets
    if language and language != "en":
        lang_label = _LANGUAGE_LABELS.get(language, "")
        if lang_label:
            parts.append(f"in {lang_label}")

    # Add "advertising trends" to focus results
    parts.append("advertising trends 2025")

    return " ".join(parts)


async def search_creative_context(
    query: str,
    market: str = "malaysia",
    language: str = "en",
) -> str:
    """Execute a GoogleSearch query and return summarized context.

    Uses Gemini's built-in GoogleSearch tool to find current trends,
    competitive context, and creative inspiration for ad generation.

    Args:
        query: Search query derived from ad brief.
        market: Target market for localized results.
        language: Target language for query localization.

    Returns:
        Summarized search findings as a string for prompt injection.
        Empty string on failure (graceful degradation).
    """
    if not query or not query.strip():
        return ""

    # Add locale context if non-English
    localized_query = query
    if language and language != "en":
        lang_label = _LANGUAGE_LABELS.get(language, "")
        if lang_label and lang_label.lower() not in query.lower():
            localized_query = f"{query} {lang_label}"

    logger.info(
        "[SearchTools] GoogleSearch query: %s (market=%s, lang=%s)",
        localized_query[:80], market, language,
    )

    try:
        response = gemini.models.generate_content(
            model=_GEMINI_MODEL,
            contents=(
                f"Search for current advertising trends and creative inspiration "
                f"related to: {localized_query}\n\n"
                f"Summarize the top 3-5 most relevant findings in 2-3 sentences each. "
                f"Focus on what's currently trending, popular formats, and creative hooks "
                f"that work well for {market} audiences."
            ),
            config=get_google_search_config(),
        )

        result_text = (response.text or "").strip()
        if result_text:
            logger.info(
                "[SearchTools] GoogleSearch returned %d chars of context",
                len(result_text),
            )
            return result_text

        logger.info("[SearchTools] GoogleSearch returned empty result")
        return ""

    except Exception as e:
        logger.warning("[SearchTools] GoogleSearch failed (graceful degradation): %s", e)
        return ""
