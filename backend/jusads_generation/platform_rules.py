"""
platform_rules.py
──────────────────
Backend-authoritative platform sizing resolution for the Agentic Ad Studio.

This module is the single source of truth for the aspect ratio, maximum pixel
dimension, and maximum ad length applied to each Generated_Ad. All sizing is
determined here in the backend; any sizing values supplied by the frontend are
ignored (Req 7.3).

Responsibilities:
- Validate/normalize a requested Target_Platform, defaulting to Instagram when
  none is supplied and rejecting unsupported values (Req 7.4–7.6).
- Resolve the single ``platform_rules`` row for a ``(platform, media_type)``
  combination, raising ``MissingRuleError`` when no entry exists (Req 7.7).

The seed data lives in the ``platform_rules`` Supabase table (migration 015).
This layer reuses the shared Supabase client from ``agent/clients.py`` and
follows the ``[PlatformRules]`` logging prefix per steering conventions.
"""

import logging
from typing import Optional, TypedDict

from shared.clients import supabase

from .state import MediaType

logger = logging.getLogger(__name__)

# --- Supported platforms ----------------------------------------------------

SUPPORTED_PLATFORMS: set[str] = {"tiktok", "instagram", "shopee"}
"""The launch platform set. Any value outside this set is rejected (Req 7.6)."""

DEFAULT_PLATFORM: str = "instagram"
"""Platform applied when a request specifies no Target_Platform (Req 7.5)."""


# --- Resolved rule shape -----------------------------------------------------


class PlatformRule(TypedDict):
    """Resolved sizing constraints for one ``(platform, media_type)`` pair.

    Attributes:
        platform: The normalized platform name (e.g. ``"instagram"``).
        media_type: The media type these rules apply to.
        aspect_ratio: Target aspect ratio string (e.g. ``"9:16"``).
        max_dimension: Maximum pixel dimension (longest side), read from
            ``additional_rules.max_dimension``.
        max_duration_seconds: Maximum ad length in seconds, or ``None`` when the
            media type carries no duration constraint (e.g. text/image).
    """

    platform: str
    media_type: MediaType
    aspect_ratio: str
    max_dimension: int
    max_duration_seconds: Optional[int]


# --- Errors ------------------------------------------------------------------


class UnsupportedPlatformError(ValueError):
    """Raised when a requested Target_Platform is outside the supported set (Req 7.6)."""


class MissingRuleError(LookupError):
    """Raised when no ``platform_rules`` entry exists for a combination (Req 7.7)."""


# --- Public API --------------------------------------------------------------


def normalize_platform(value: Optional[str]) -> str:
    """Normalize and validate a requested Target_Platform.

    Defaults to Instagram when the value is ``None`` or empty (Req 7.5), passes
    through a supported platform in lowercase form, and raises for any value
    outside the supported set (Req 7.6).

    Args:
        value: The raw platform value supplied by the request, if any.

    Returns:
        The normalized (lowercase) platform name.

    Raises:
        UnsupportedPlatformError: When ``value`` is a non-empty string that is
            not one of TikTok, Instagram, or Shopee.
    """
    if value is None or not value.strip():
        logger.info(
            "[PlatformRules] No platform supplied; defaulting to '%s'", DEFAULT_PLATFORM
        )
        return DEFAULT_PLATFORM

    normalized = value.strip().lower()
    if normalized not in SUPPORTED_PLATFORMS:
        logger.warning(
            "[PlatformRules] Rejected unsupported platform: %r", value
        )
        raise UnsupportedPlatformError(
            f"Unsupported platform '{value}'. "
            f"Supported platforms: {sorted(SUPPORTED_PLATFORMS)}."
        )

    logger.info("[PlatformRules] Resolved platform '%s'", normalized)
    return normalized


def resolve_rule(platform: str, media_type: MediaType) -> PlatformRule:
    """Resolve the single sizing rule for a ``(platform, media_type)`` pair.

    Reads one row from the ``platform_rules`` table and maps it into a
    ``PlatformRule``, sourcing ``max_dimension`` from
    ``additional_rules.max_dimension``. Any sizing supplied by the frontend is
    not consulted (Req 7.3).

    For text and audio media types, when no explicit row exists the function
    returns sensible platform-agnostic defaults rather than raising, because
    these types do not require strict pixel/dimension rules.

    Args:
        platform: A normalized platform name (see :func:`normalize_platform`).
        media_type: The media type to resolve rules for.

    Returns:
        The resolved ``PlatformRule``.

    Raises:
        MissingRuleError: When no rule exists for image/video combinations
            (Req 7.7), or when the Supabase lookup fails and no rule can be
            resolved for a dimension-sensitive media type.
    """
    try:
        response = (
            supabase.table("platform_rules")
            .select("platform, media_type, aspect_ratio, max_duration_seconds, additional_rules")
            .ilike("platform", platform)
            .eq("media_type", media_type)
            .limit(1)
            .execute()
        )
        rows = response.data or []
    except Exception as e:
        # Resilient handling of the external Supabase call: surface as a missing
        # rule so the orchestrator rejects that media generation (Req 7.7)
        # rather than crashing the whole turn.
        logger.error(
            "[PlatformRules] Supabase lookup failed for (%s, %s): %s",
            platform,
            media_type,
            e,
        )
        # For text/audio, provide sensible defaults even if DB lookup fails.
        if media_type in ("text", "audio"):
            logger.info(
                "[PlatformRules] Using built-in defaults for (%s, %s) after DB failure",
                platform, media_type,
            )
            return _default_rule(platform, media_type)
        raise MissingRuleError(
            f"Could not resolve platform rule for ('{platform}', '{media_type}'): {e}"
        ) from e

    if not rows:
        # Text and audio don't require strict pixel/dimension rules — return
        # sensible defaults so generation can proceed rather than rejecting.
        if media_type in ("text", "audio"):
            logger.info(
                "[PlatformRules] No DB rule for (%s, %s); using built-in defaults",
                platform, media_type,
            )
            return _default_rule(platform, media_type)
        logger.warning(
            "[PlatformRules] No rule defined for (%s, %s)", platform, media_type
        )
        raise MissingRuleError(
            f"No platform rule defined for platform '{platform}' and media type '{media_type}'."
        )

    row = rows[0]
    additional_rules = row.get("additional_rules") or {}
    max_dimension = int(additional_rules.get("max_dimension", 0) or 0)

    rule: PlatformRule = {
        "platform": row["platform"],
        "media_type": row["media_type"],
        "aspect_ratio": row["aspect_ratio"],
        "max_dimension": max_dimension,
        "max_duration_seconds": row.get("max_duration_seconds"),
    }
    logger.info(
        "[PlatformRules] Resolved rule for (%s, %s): aspect_ratio=%s, "
        "max_dimension=%s, max_duration_seconds=%s",
        platform,
        media_type,
        rule["aspect_ratio"],
        rule["max_dimension"],
        rule["max_duration_seconds"],
    )
    return rule


# --- Built-in fallback defaults for text/audio --------------------------------

_TEXT_DEFAULTS: dict[str, dict] = {
    "tiktok": {"aspect_ratio": "9:16", "max_caption_chars": 2200},
    "instagram": {"aspect_ratio": "1:1", "max_caption_chars": 2200},
    "shopee": {"aspect_ratio": "1:1", "max_caption_chars": 3000},
}

_AUDIO_DEFAULTS: dict[str, dict] = {
    "tiktok": {"aspect_ratio": "9:16", "max_duration_seconds": 180},
    "instagram": {"aspect_ratio": "1:1", "max_duration_seconds": 90},
    "shopee": {"aspect_ratio": "1:1", "max_duration_seconds": 60},
}


def _default_rule(platform: str, media_type: MediaType) -> PlatformRule:
    """Return a hardcoded sensible default rule for text or audio."""
    if media_type == "text":
        defaults = _TEXT_DEFAULTS.get(platform, {"aspect_ratio": "1:1", "max_caption_chars": 2200})
        return {
            "platform": platform,
            "media_type": "text",
            "aspect_ratio": defaults["aspect_ratio"],
            "max_dimension": 0,
            "max_duration_seconds": None,
        }
    # audio
    defaults = _AUDIO_DEFAULTS.get(platform, {"aspect_ratio": "1:1", "max_duration_seconds": 120})
    return {
        "platform": platform,
        "media_type": "audio",
        "aspect_ratio": defaults["aspect_ratio"],
        "max_dimension": 0,
        "max_duration_seconds": defaults.get("max_duration_seconds", 120),
    }
