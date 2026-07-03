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
from typing import Optional

import requests

from shared.clients import supabase
from config import ZERNIO_API_KEY, ZERNIO_ACCOUNT_TIKTOK, ZERNIO_ACCOUNT_INSTAGRAM

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

_ZERNIO_BASE = "https://zernio.com/api/v1"
_TIMEOUT_SECONDS = 30


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _resolve_account_id(platform: str) -> Optional[str]:
    """Map a platform name to the configured Zernio account ID.

    Returns ``None`` when no account is configured for the platform, so the
    caller can surface a clear error rather than a cryptic Zernio 400.
    """
    mapping = {
        "tiktok": ZERNIO_ACCOUNT_TIKTOK,
        "instagram": ZERNIO_ACCOUNT_INSTAGRAM,
        "youtube": ZERNIO_ACCOUNT_INSTAGRAM,  # reuse IG account or add a YT account later
    }
    return mapping.get(platform.lower().strip()) or None


def _build_platform_data(platform: str) -> dict:
    """Build platform-specific settings for the Zernio post.

    TikTok has privacy/duet/stitch settings; Instagram and others are simpler.
    """
    if platform == "tiktok":
        return {
            "tiktokSettings": {
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "allow_comment": True,
                "allow_duet": True,
                "allow_stitch": True,
            }
        }
    return {}


# ─── Public API ───────────────────────────────────────────────────────────────


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
) -> dict:
    """Push a published ad to a social platform via Zernio.

    Calls the Zernio unified ``POST /api/v1/posts`` endpoint. On success,
    records the distribution metadata on the ``generated_ads`` row
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

    account_id = _resolve_account_id(platform)
    if not account_id:
        raise AccountNotConfiguredError(
            f"No Zernio account configured for platform '{platform}'. "
            f"Set ZERNIO_ACCOUNT_{platform.upper()} in backend/.env."
        )

    # Map our media_type to Zernio's mediaItems type.
    zernio_media_type = "video" if media_type in ("video", "audio") else "image"

    body = {
        "content": caption or "",
        "mediaItems": [{"type": zernio_media_type, "url": media_url}],
        "platforms": [
            {
                "platform": platform.lower(),
                "accountId": account_id,
                "platformSpecificData": _build_platform_data(platform),
            }
        ],
        "publishNow": True,
    }

    headers = {
        "Authorization": f"Bearer {ZERNIO_API_KEY}",
        "Content-Type": "application/json",
    }

    logger.info(
        "[Distribution] Posting ad %s to %s via Zernio (media=%s)",
        ad_id, platform, media_url[:80],
    )

    try:
        resp = requests.post(
            f"{_ZERNIO_BASE}/posts",
            json=body,
            headers=headers,
            timeout=_TIMEOUT_SECONDS,
        )
    except requests.RequestException as e:
        raise DistributionError(f"Zernio request failed: {e}") from e

    if resp.status_code not in (200, 201):
        raise DistributionError(
            f"Zernio returned {resp.status_code}: {resp.text[:300]}"
        )

    result = resp.json()
    post_id = result.get("post", {}).get("_id") or result.get("id") or ""

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

    return {"post_id": post_id, "status": "distributed", "platform": platform}
