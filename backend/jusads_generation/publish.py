"""
publish.py
──────────
Human-in-the-loop publish gate for Generated_Ads (NIMBUS diagram § 4).

Generated ads are stored with ``status = 'completed'`` (or ``'draft'``) after
generation. Nothing is distributed automatically: the project owner inspects
the output on the Generation Canvas and explicitly approves it. Calling
:func:`publish_ad` flips ``generated_ads.status`` to ``'published'`` — the
human-approval step that gates downstream distribution hooks.

A compliance-failed ad (``compliance_status = 'final-non-compliant'``) is
blocked from publishing so non-compliant creative cannot reach a platform.
All Supabase access is wrapped in try/except with ``[Publish]``-prefixed
logging and graceful degradation (Req 3.2).
"""

import logging
from datetime import datetime, timezone
from typing import Optional, TypedDict

from shared.clients import supabase

logger = logging.getLogger(__name__)

# ─── Constants ───────────────────────────────────────────────────────────────

PUBLISHABLE_FROM_STATUSES = frozenset({"draft", "completed"})
"""Generation statuses a human may approve for publishing."""

PUBLISHED_STATUS = "published"
"""Terminal status set once the owner approves an ad."""

_COMPLIANCE_BLOCKED_STATUS = "final-non-compliant"
"""Compliance verdict that blocks publishing entirely."""


# ─── Errors ──────────────────────────────────────────────────────────────────


class PublishError(Exception):
    """Raised when an ad cannot be published (not found, blocked, or store down)."""


class AdNotFoundError(PublishError):
    """The referenced Generated_Ad does not exist for the given project."""


class CompliancePublishBlockedError(PublishError):
    """The ad failed compliance and may not be published."""


# ─── Result shape ────────────────────────────────────────────────────────────


class PublishResult(TypedDict):
    """Outcome of a publish request."""

    ad_id: str
    status: str
    compliance_status: str
    already_published: bool


# ─── Public API ──────────────────────────────────────────────────────────────


def publish_ad(project_id: str, ad_id: str) -> PublishResult:
    """Approve and publish one Generated_Ad (human-in-the-loop gate, § 4).

    Reads the ad scoped to ``project_id``, enforces the compliance gate, and
    sets ``status = 'published'``. Publishing is idempotent: an already-published
    ad returns successfully with ``already_published = True``.

    Args:
        project_id: Owning project id (scopes the lookup for safety).
        ad_id: The ``generated_ads.id`` to publish.

    Returns:
        A :class:`PublishResult` describing the post-publish state.

    Raises:
        AdNotFoundError: The ad does not exist for the project.
        CompliancePublishBlockedError: The ad failed compliance.
        PublishError: The persistence store is unavailable or the update failed.
    """
    ad = _get_ad(project_id, ad_id)
    if ad is None:
        raise AdNotFoundError(f"Generated ad {ad_id} not found for project {project_id}")

    current_status = ad.get("status") or "draft"
    compliance_status = ad.get("compliance_status") or "non-final"

    # Already approved — idempotent success.
    if current_status == PUBLISHED_STATUS:
        logger.info("[Publish] Ad %s already published; no-op", ad_id)
        return PublishResult(
            ad_id=ad_id,
            status=PUBLISHED_STATUS,
            compliance_status=compliance_status,
            already_published=True,
        )

    # Compliance gate: block ads that failed compliance (§ 4 — only reviewed,
    # non-failing creative may be approved for distribution).
    if compliance_status == _COMPLIANCE_BLOCKED_STATUS:
        logger.warning(
            "[Publish] Ad %s blocked from publishing (compliance=%s)",
            ad_id,
            compliance_status,
        )
        raise CompliancePublishBlockedError(
            "Ad failed compliance review and cannot be published"
        )

    _set_published(ad_id)
    logger.info("[Publish] Ad %s approved and published by owner", ad_id)
    return PublishResult(
        ad_id=ad_id,
        status=PUBLISHED_STATUS,
        compliance_status=compliance_status,
        already_published=False,
    )


# ─── Private helpers ─────────────────────────────────────────────────────────


def _get_ad(project_id: str, ad_id: str) -> Optional[dict]:
    """Read one Generated_Ad scoped to its project, or ``None`` when absent."""
    try:
        response = (
            supabase.table("generated_ads")
            .select("id, project_id, status, compliance_status, media_type, platform")
            .eq("id", ad_id)
            .eq("project_id", project_id)
            .execute()
        )
        rows = response.data or []
        return rows[0] if rows else None
    except Exception as e:  # noqa: BLE001 - graceful degradation (Req 3.2)
        logger.error("[Publish] Failed to read ad %s: %s", ad_id, e)
        raise PublishError(f"persistence store unavailable: {e}") from e


def _set_published(ad_id: str) -> None:
    """Flip an ad's status to ``published`` (best-effort, raises on failure)."""
    try:
        supabase.table("generated_ads").update(
            {
                "status": PUBLISHED_STATUS,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", ad_id).execute()
    except Exception as e:  # noqa: BLE001 - graceful degradation (Req 3.2)
        logger.error("[Publish] Failed to publish ad %s: %s", ad_id, e)
        raise PublishError(f"failed to update ad status: {e}") from e
