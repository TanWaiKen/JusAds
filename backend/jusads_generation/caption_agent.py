"""Platform-aware social caption generation for approved JusAds creatives."""

from __future__ import annotations

import logging
import re
from typing import Any

from shared.clients import gemini
from shared.config import MODEL_TEXT

logger = logging.getLogger(__name__)

# TikTok photo posts use ``content`` as a slideshow title.  Keep a small
# buffer below the documented 90-character limit for platform-side counting.
_CAPTION_LIMITS: dict[tuple[str, str], int] = {
    ("tiktok", "image"): 88,
}


def _limit_for(platform: str, media_type: str) -> int | None:
    return _CAPTION_LIMITS.get((platform.lower().strip(), media_type.lower().strip()))


def _clean_caption(value: str, *, limit: int | None) -> str:
    text = re.sub(r"\s+", " ", (value or "").strip().strip('"'))
    if not text:
        text = "Discover our latest collection."
    if limit is not None and len(text) > limit:
        text = text[: max(1, limit - 1)].rstrip(" ,.;:-") + "…"
    return text


def normalize_platform_caption(
    caption: str,
    *,
    platform: str,
    media_type: str,
) -> str:
    """Apply the platform's publish-safe caption constraint to supplied copy."""
    return _clean_caption(caption, limit=_limit_for(platform, media_type))


def generate_platform_caption(
    *,
    platform: str,
    media_type: str,
    prompt_used: str | None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Create concise, localized post copy and enforce platform hard limits.

    The creative-generation prompt is never sent directly to a social platform.
    If the model is unavailable, a safe concise fallback is still returned so a
    publish retry cannot accidentally reuse a long image prompt as a caption.
    """
    normalized_platform = (platform or "instagram").lower().strip()
    normalized_media = (media_type or "image").lower().strip()
    limit = _limit_for(normalized_platform, normalized_media)
    context = metadata or {}
    market = context.get("market") or "the target market"
    language = context.get("language") or context.get("target_language") or "the audience language"
    brief = (prompt_used or "a newly generated advertising creative").strip()

    limit_instruction = (
        f"The final caption MUST be {limit} characters or fewer, including hashtags. "
        if limit is not None
        else "Keep the caption concise and platform-native. "
    )
    prompt = f"""You are a careful social media copywriter.
Write one ready-to-publish caption for a {normalized_media} ad on {normalized_platform}.
Market: {market}. Preferred language: {language}.
Creative brief: {brief[:1800]}

{limit_instruction}Do not invent prices, guarantees, certifications, endorsements, or facts not in the brief.
Use at most three relevant hashtags. Return only the caption, with no label, quotes, or explanation."""

    try:
        response = gemini.models.generate_content(model=MODEL_TEXT, contents=prompt)
        caption = normalize_platform_caption(
            response.text or "",
            platform=normalized_platform,
            media_type=normalized_media,
        )
        logger.info(
            "[CaptionAgent] Generated %s/%s caption (%s chars)",
            normalized_platform,
            normalized_media,
            len(caption),
        )
        return caption
    except Exception as exc:  # A resilient fallback is required for publishing.
        logger.warning("[CaptionAgent] Model call failed; using safe fallback: %s", exc)
        return normalize_platform_caption(
            "Discover our latest collection.",
            platform=normalized_platform,
            media_type=normalized_media,
        )
