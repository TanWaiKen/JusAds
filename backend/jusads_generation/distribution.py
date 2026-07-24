"""
distribution.py
───────────────
Zernio distribution integration for the Agentic Ad Studio.

After an ad is published (human-in-the-loop approval), this module handles
pushing it to the configured social platform (TikTok, Instagram, YouTube) via
the Zernio unified ``POST /api/v1/posts`` endpoint.

Zernio API docs: https://zernio.com/tiktok-api (TikTok),
https://zernio.com/instagram (Instagram). Both use the same endpoint; only the
``platform`` field and optional ``platformSpecificData`` differ.

Every external call is wrapped in ``try/except`` with the ``[Distribution]``
logging prefix and graceful degradation per steering.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from zernio import Zernio

from shared.clients import supabase
from config import ZERNIO_API_KEY, ZERNIO_ACCOUNT_TIKTOK, ZERNIO_ACCOUNT_INSTAGRAM

logger = logging.getLogger(__name__)

# --- Constants ----------------------------------------------------------------

_TIMEOUT_SECONDS = 30


# --- Helpers ------------------------------------------------------------------


def _resolve_account_id(platform: str) -> Optional[str]:
    """Map a platform name to the configured Zernio account ID.

    Returns ``None`` when no account is configured for the platform, so the
    caller can surface a clear error rather than a cryptic Zernio 400.
    """
    mapping = {
        "tiktok": ZERNIO_ACCOUNT_TIKTOK,
        "instagram": ZERNIO_ACCOUNT_INSTAGRAM,
    }
    return mapping.get(platform.lower().strip()) or None


def configured_distribution_accounts() -> list[dict]:
    """Expose configured defaults when live Zernio account discovery is unavailable."""
    accounts = []
    for platform, account_id in {
        "tiktok": ZERNIO_ACCOUNT_TIKTOK,
        "instagram": ZERNIO_ACCOUNT_INSTAGRAM,
    }.items():
        if account_id:
            accounts.append({
                "id": account_id,
                "platform": platform,
                "label": f"Configured {platform.title()} account",
            })
    return accounts


def _is_instagram_story_asset(metadata: dict[str, Any] | None) -> bool:
    """Return whether an image is too tall for an Instagram feed post.

    Instagram feed images must be at least 0.75:1. Generated 9:16 creative is
    therefore sent as a Story, preserving the ad instead of attempting an
    invisible crop or returning a platform 400.
    """
    aspect_ratio = (metadata or {}).get("aspect_ratio")
    if not isinstance(aspect_ratio, str) or ":" not in aspect_ratio:
        return False
    try:
        width, height = (float(value.strip()) for value in aspect_ratio.split(":", 1))
        return width > 0 and height > 0 and width / height < 0.75
    except ValueError:
        return False


# --- Public API ---------------------------------------------------------------


class DistributionError(Exception):
    """Raised when distribution to the social platform fails."""
    pass


class AccountNotConfiguredError(DistributionError):
    """Raised when no Zernio account is configured for the target platform."""
    pass


def distribute_ad(
    *,
    ad_id: str,
    platform: str,
    media_url: str,
    media_type: str,
    caption: Optional[str] = None,
    account_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict:
    """Push a published ad to a social platform via Zernio using the official SDK.

    On success, records the distribution metadata on the ``generated_ads`` row
    (``distributed_at``, ``distribution_platform``, ``distribution_post_id``).

    Args:
        ad_id: The ``generated_ads.id`` to distribute.
        platform: Target platform (``tiktok`` / ``instagram`` / ``youtube``).
        media_url: The public S3 URL of the ad's media file.
        media_type: The ad's media type (``image`` / ``video`` / ``audio``).
        caption: Optional text caption / copy for the post.

    Returns:
        A dict ``{post_id, status, platform}`` on success.

    Raises:
        AccountNotConfiguredError: When no Zernio account is set for the platform.
        DistributionError: On any Zernio API failure.
    """
    if not ZERNIO_API_KEY:
        raise DistributionError(
            "ZERNIO_API_KEY is not configured. Set it in backend/.env to enable distribution."
        )

    resolved_account_id = account_id or _resolve_account_id(platform)
    if not resolved_account_id:
        raise AccountNotConfiguredError(
            f"No Zernio account configured for platform '{platform}'. "
            f"Set ZERNIO_ACCOUNT_{platform.upper()} in backend/.env."
        )

    # Map our media_type to Zernio's mediaItems type.
    zernio_media_type = "video" if media_type in ("video", "audio") else "image"
    media_items = [{"type": zernio_media_type, "url": media_url}]

    normalized_platform = platform.lower().strip()
    platform_target: dict[str, Any] = {
        "platform": normalized_platform,
        "accountId": resolved_account_id,
    }
    content_type = "feed"
    if (
        normalized_platform == "instagram"
        and zernio_media_type == "image"
        and _is_instagram_story_asset(metadata)
    ):
        platform_target["platformSpecificData"] = {"contentType": "story"}
        content_type = "story"
    platforms_payload = [platform_target]

    tiktok_settings = None
    if platform.lower() == "tiktok":
        tiktok_settings = {
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "allow_comment": True,
            "allow_duet": True,
            "allow_stitch": True,
        }

    logger.info(
        "[Distribution] Posting ad %s to %s (%s) via Zernio SDK (media=%s)",
        ad_id, platform, content_type, media_url[:80],
    )

    try:
        client = Zernio(api_key=ZERNIO_API_KEY, timeout=_TIMEOUT_SECONDS)
        result = client.posts.create(
            content=caption or "",
            platforms=platforms_payload,
            media_items=media_items,
            publish_now=True,
            tiktok_settings=tiktok_settings,
        )
    except Exception as e:
        raise DistributionError(f"Zernio SDK request failed: {e}") from e

    # The SDK returns a PostCreateResponse or dict. Let's parse the ID out of it.
    post_id = ""
    if isinstance(result, dict):
        post_id = result.get("post", {}).get("_id") or result.get("id") or ""
    elif hasattr(result, "post"):
        post_obj = getattr(result, "post")
        if isinstance(post_obj, dict):
            post_id = post_obj.get("_id") or post_obj.get("id") or ""
        else:
            # The generated Zernio SDK maps JSON ``_id`` to ``field_id``
            # because leading-underscore names are reserved by Pydantic.
            post_id = (
                getattr(post_obj, "id", "")
                or getattr(post_obj, "field_id", "")
                or getattr(post_obj, "_id", "")
            )
    elif hasattr(result, "id"):
        post_id = getattr(result, "id", "")

    # Record distribution on the generated_ads row (best-effort).
    try:
        supabase.table("generated_ads").update(
            {
                "distributed_at": datetime.now(timezone.utc).isoformat(),
                "distribution_platform": platform,
                "distribution_post_id": str(post_id),
            }
        ).eq("id", ad_id).execute()
        logger.info("[Distribution] Recorded distribution on ad %s (post_id=%s)", ad_id, post_id)
    except Exception as e:
        logger.warning("[Distribution] Failed to record distribution on ad %s: %s", ad_id, e)

    return {
        "post_id": str(post_id),
        "status": "distributed",
        "platform": platform,
        "account_id": resolved_account_id,
        "caption": caption or "",
        "content_type": content_type,
    }


def get_ad_analytics(ad_id: str, project_id: str) -> dict:
    """Retrieve live Zernio analytics for a distributed ad.

    Draft ads return an explicit zero-valued draft state. Configured posts never
    receive synthetic metrics: unavailable upstream analytics raise a
    :class:`DistributionError` for the API layer to report.
    """
    try:
        response = (
            supabase.table("generated_ads")
            .select("id, distribution_platform, distribution_post_id, media_type")
            .eq("id", ad_id)
            .eq("project_id", project_id)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if not rows:
            raise ValueError(f"Ad {ad_id} not found")

        ad_row = rows[0]
        platform = ad_row.get("distribution_platform")
        post_id = ad_row.get("distribution_post_id")
        if not post_id or not platform:
            return {
                "status": "draft",
                "source": "none",
                "metrics": {
                    "impressions": 0,
                    "reach": 0,
                    "likes": 0,
                    "comments": 0,
                    "shares": 0,
                    "clicks": 0,
                },
                "chart_data": [],
            }

        if not ZERNIO_API_KEY:
            raise DistributionError("Zernio analytics are not configured")

        client = Zernio(api_key=ZERNIO_API_KEY, timeout=_TIMEOUT_SECONDS)
        data = client.analytics.get_analytics(post_id=str(post_id), platform=platform)
        metrics = data if isinstance(data, dict) else {}
        return {
            "status": "active",
            "source": "zernio",
            "platform": platform,
            "post_id": post_id,
            "raw_data": metrics,
            "metrics": {
                "impressions": metrics.get("impressions", 0),
                "reach": metrics.get("reach", 0),
                "likes": metrics.get("likes", 0),
                "comments": metrics.get("comments", 0),
                "shares": metrics.get("shares", 0),
                "clicks": metrics.get("clicks", 0),
            },
            "chart_data": [],
        }
    except (ValueError, DistributionError):
        raise
    except Exception as exc:
        logger.exception("[Distribution] Live analytics request failed")
        raise DistributionError("Zernio analytics are temporarily unavailable") from exc
