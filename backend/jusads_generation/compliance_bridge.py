"""
compliance_bridge.py
─────────────────────
Compliance integration for the Agentic Ad Studio (Req 8).

This module is the single bridge between a freshly generated ``Generated_Ad``
and the existing JusAds compliance pipeline (``agent/compliance_pipeline.py``).
Every Generated_Ad is submitted here *before* it may be presented as final
(Req 8.1). The bridge:

1. Builds a ``Compliance_State`` (existing ``TypedDict`` from ``agent/models.py``)
   from the Generated_Ad, downloading the media locally when needed.
2. Creates a ``compliance_checks`` row so the pipeline's own persistence has a
   target and the check can be linked back to the ad.
3. Runs the compiled compliance pipeline with a 120-second timeout (Req 8.3).
4. Maps the pipeline verdict to a final compliance status (Req 8.2):
   ``pass → final-compliant``, any other real result → ``final-non-compliant``,
   timeout / error → ``non-final`` (Req 8.5).
5. Records ``compliance_status`` / ``compliance_result`` / ``compliance_check_id``
   onto the ``generated_ads`` row, and reports whether that record succeeded so
   an unpersisted-but-real result is surfaced rather than dropped (Req 8.4).

It is *only* the compliance-bridging concern: no routing, orchestration, agent,
or chat-persistence logic lives here (Req 1.1). Every external call (Supabase,
S3, the compliance pipeline) is wrapped in ``try/except`` with the
``[ComplianceBridge]`` logging prefix and graceful degradation per steering.
"""

import asyncio
import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from shared.clients import s3, supabase
from shared.models import Compliance_State
from config import S3_BUCKET_NAME

from .agents.base import AgentResult

logger = logging.getLogger(__name__)

# --- Constants ---------------------------------------------------------------

COMPLIANCE_TIMEOUT_SECONDS = 120
"""Max seconds a Generated_Ad may wait for a compliance verdict (Req 8.3)."""

# Final compliance-status values recorded on ``generated_ads.compliance_status``.
STATUS_COMPLIANT = "final-compliant"
STATUS_NON_COMPLIANT = "final-non-compliant"
STATUS_NON_FINAL = "non-final"

# Product defaults for the compliance evaluation context (design § Compliance
# pipeline input mapping). These are stable defaults rather than user inputs.
DEFAULT_MARKET = "malaysia"
DEFAULT_ETHNICITY = "all"
DEFAULT_AGE_GROUP = "all_ages"

# The compliance pipeline's terminal ``status`` value that maps to compliant.
_PASS_STATUS = "pass"


# --- Helpers -----------------------------------------------------------------


def _resolve_ad_context(ad: AgentResult) -> dict:
    """Look up owning ``project_id``/``user_email`` for a Generated_Ad.

    The ``AgentResult`` contract does not carry the owning project, so the
    ``generated_ads`` row is read by ``ad_id`` to recover ``project_id``; the
    project's ``owner_email`` supplies the ``user_email`` required by the
    ``compliance_checks`` row. Failures degrade to empty strings rather than
    raising (Req 3.2).

    Args:
        ad: The Generated_Ad result to resolve context for.

    Returns:
        A dict with ``project_id`` and ``user_email`` (each possibly ``""``).
    """
    context = {"project_id": "", "user_email": ""}
    ad_id = ad.get("ad_id")
    if not ad_id:
        return context

    try:
        response = (
            supabase.table("generated_ads")
            .select("project_id")
            .eq("id", ad_id)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if rows:
            context["project_id"] = str(rows[0].get("project_id") or "")
    except Exception as e:
        logger.error("[ComplianceBridge] Could not resolve project for ad %s: %s", ad_id, e)
        return context

    if context["project_id"]:
        try:
            proj_resp = (
                supabase.table("projects")
                .select("owner_email")
                .eq("id", context["project_id"])
                .limit(1)
                .execute()
            )
            proj_rows = proj_resp.data or []
            if proj_rows:
                context["user_email"] = str(proj_rows[0].get("owner_email") or "")
        except Exception as e:
            logger.error(
                "[ComplianceBridge] Could not resolve owner for project %s: %s",
                context["project_id"], e,
            )

    return context


def _download_media(s3_media_key: str) -> Optional[str]:
    """Download an ad's S3 media object to a local temp file.

    Returns the local path on success, or ``None`` on any failure so the caller
    can degrade to a non-final status rather than crashing (Req 3.2, 8.5).

    Args:
        s3_media_key: The S3 object key for the generated media.

    Returns:
        The local temp file path, or ``None`` if the download failed.
    """
    try:
        suffix = Path(s3_media_key).suffix or ""
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.close()
        s3.download_file(S3_BUCKET_NAME, s3_media_key, tmp.name)
        logger.info("[ComplianceBridge] Downloaded media %s → %s", s3_media_key, tmp.name)
        return tmp.name
    except Exception as e:
        logger.error("[ComplianceBridge] Failed to download media %s: %s", s3_media_key, e)
        return None


def _create_compliance_check_row(
    *,
    check_id: str,
    ad: AgentResult,
    project_id: str,
    user_email: str,
) -> bool:
    """Insert a ``compliance_checks`` row so the pipeline can persist to it.

    The pipeline's own ``_persist_compliance_result`` updates the row keyed by
    ``check_id``, so the row must exist first. Returns ``True`` on success and
    ``False`` on failure (logged, non-fatal) so the pipeline can still run and
    surface its result (Req 8.4).

    Args:
        check_id: The unique check identifier for this ad's compliance run.
        ad: The Generated_Ad result being checked.
        project_id: Owning project id (may be empty when unresolved).
        user_email: Owning user email (may be empty when unresolved).

    Returns:
        ``True`` when the row was created, ``False`` otherwise.
    """
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "check_id": check_id,
        "user_email": user_email or "unknown",
        "project_id": project_id or None,
        "media_type": ad["media_type"],
        "market": DEFAULT_MARKET,
        "ethnicity": DEFAULT_ETHNICITY,
        "age_group": DEFAULT_AGE_GROUP,
        "platform": ad["platform"],
        "status": "pending",
        "s3_upload_key": ad.get("s3_media_key"),
        "created_at": now,
        "updated_at": now,
    }
    try:
        supabase.table("compliance_checks").insert(payload).execute()
        logger.info("[ComplianceBridge] Created compliance_checks row %s", check_id)
        return True
    except Exception as e:
        logger.error(
            "[ComplianceBridge] Failed to create compliance_checks row %s: %s",
            check_id, e,
        )
        return False


def _build_compliance_state(
    *,
    check_id: str,
    ad: AgentResult,
    input_path: str,
    market: str = DEFAULT_MARKET,
) -> Compliance_State:
    """Build a ``Compliance_State`` for the pipeline from a Generated_Ad.

    Maps the Generated_Ad onto the existing compliance state schema
    (design § Compliance pipeline input mapping). ``text_input`` carries the
    caption for text ads; ``input_path`` points to the locally downloaded media
    for image/audio/video ads.

    Args:
        check_id: The unique check identifier.
        ad: The Generated_Ad result being checked.
        input_path: Local media path (``""`` for text ads).

    Returns:
        A fully-populated ``Compliance_State`` ready for the pipeline.
    """
    return Compliance_State(
        session_id=check_id,
        media_type=ad["media_type"],
        input_path=input_path,
        text_input=ad.get("caption") or "",
        market=DEFAULT_MARKET,
        platform=ad["platform"],
        ethnicity=DEFAULT_ETHNICITY,
        age_group=DEFAULT_AGE_GROUP,
        iteration=0,
        result={},
        status="pending",
        user_prompt_context="",
        check_id=check_id,
        remediated_path="",
        remix_iteration=0,
    )


def _map_verdict(final_state: Optional[dict]) -> str:
    """Map a compliance pipeline terminal state to a final compliance status.

    Mapping (Req 8.2): a ``pass`` verdict → ``final-compliant``; any other real
    result (``remediate`` / ``critical_regen`` / anything else) →
    ``final-non-compliant``. A missing/empty state (no real result) →
    ``non-final`` (Req 8.5).

    Args:
        final_state: The pipeline's final state dict, or ``None``.

    Returns:
        One of the ``STATUS_*`` values.
    """
    if not final_state:
        return STATUS_NON_FINAL

    status = (final_state.get("status") or "").strip().lower()
    if not status:
        # A result object with no terminal decision is not a usable verdict.
        return STATUS_NON_FINAL
    if status == _PASS_STATUS:
        return STATUS_COMPLIANT
    return STATUS_NON_COMPLIANT


def _record_on_generated_ad(
    *,
    ad_id: Optional[str],
    compliance_status: str,
    compliance_result: dict,
    compliance_check_id: str,
) -> bool:
    """Persist compliance outcome onto the ``generated_ads`` row.

    Records ``compliance_status``, ``compliance_result`` (jsonb), and
    ``compliance_check_id`` for the ad. Returns ``True`` when the update
    succeeds and ``False`` otherwise; the caller uses this to surface an
    unpersisted-but-real result rather than dropping it (Req 8.4).

    Args:
        ad_id: The ``generated_ads`` row id (``None`` when unknown).
        compliance_status: The mapped final/non-final status.
        compliance_result: The full pipeline result payload.
        compliance_check_id: The linked ``compliance_checks.check_id``.

    Returns:
        ``True`` when persisted, ``False`` otherwise.
    """
    if not ad_id:
        logger.warning(
            "[ComplianceBridge] No ad_id; cannot persist compliance status '%s'",
            compliance_status,
        )
        return False

    try:
        supabase.table("generated_ads").update(
            {
                "compliance_status": compliance_status,
                "compliance_result": compliance_result,
                "compliance_check_id": compliance_check_id,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", ad_id).execute()
        logger.info(
            "[ComplianceBridge] Recorded compliance_status=%s on ad %s",
            compliance_status, ad_id,
        )
        return True
    except Exception as e:
        logger.error(
            "[ComplianceBridge] Failed to record compliance status on ad %s: %s",
            ad_id, e,
        )
        return False


def summarize_reasons(compliance_result: dict) -> dict:
    """Distill a raw compliance-pipeline result into a compact "why" payload.

    The compliance pipeline returns a large ``result`` dict (rules, persona,
    transcripts, evaluation, etc.). The UI only needs the human-facing reasons an
    ad was flagged, so this extracts a stable, small subset:

    * ``risk_level`` / ``risk_percentage`` — the headline severity.
    * ``explanation`` — the model's concise reasoning.
    * ``suggestion`` — the actionable fix advice.
    * ``indicators`` — the ranked list of flagged items (``high_risk_indicator``).
    * ``skipped`` / ``error`` — surfaced verbatim so a skipped or errored check is
      explained rather than shown as a bare status.

    Missing fields are simply omitted so the caller can present only what exists.
    Never raises: any non-dict or unexpected shape degrades to an empty dict.

    Args:
        compliance_result: The pipeline result payload (or an error/skip dict).

    Returns:
        A compact dict with only the populated reason fields.
    """
    if not isinstance(compliance_result, dict):
        return {}

    reasons: dict = {}

    # Pass-through of non-verdict outcomes so the UI can explain them.
    if compliance_result.get("skipped"):
        reasons["skipped"] = True
        if compliance_result.get("reason"):
            reasons["reason"] = str(compliance_result["reason"])
    if compliance_result.get("error"):
        reasons["error"] = str(compliance_result["error"])

    # Headline severity.
    if compliance_result.get("risk_level"):
        reasons["risk_level"] = str(compliance_result["risk_level"])
    if compliance_result.get("risk_percentage") is not None:
        reasons["risk_percentage"] = compliance_result["risk_percentage"]

    # Human-facing narrative.
    if compliance_result.get("explanation"):
        reasons["explanation"] = str(compliance_result["explanation"])
    if compliance_result.get("suggestion"):
        reasons["suggestion"] = str(compliance_result["suggestion"])

    # Ranked flagged items (cap defensively so the payload stays small).
    indicators = compliance_result.get("high_risk_indicator")
    if isinstance(indicators, list) and indicators:
        reasons["indicators"] = [str(item) for item in indicators[:10]]

    # For compliant/low-risk ads with no explanation, synthesize a default one
    # so the UI "Why this verdict" panel has something meaningful to show (C2).
    if not reasons.get("explanation") and reasons.get("risk_level"):
        risk = reasons["risk_level"].lower()
        if risk == "low":
            pct = reasons.get("risk_percentage", 0)
            reasons["explanation"] = (
                f"This ad was assessed as Low risk ({pct}%). No cultural or regulatory "
                "issues were detected for the target market and audience."
            )

    return reasons


# --- Public API --------------------------------------------------------------


async def run_compliance_for_ad(
    ad: AgentResult,
    *,
    project_id: Optional[str] = None,
    user_email: Optional[str] = None,
    market: Optional[str] = None,
    product_name: Optional[str] = None,
    product_category: Optional[str] = None,
) -> dict:
    """Run the compliance pipeline for one Generated_Ad before it is final.

    Submits ``ad`` to the compliance pipeline (Req 8.1) with a 120-second
    timeout (Req 8.3), maps the verdict to a final status (Req 8.2), records the
    outcome on the ``generated_ads`` row, and returns the result. A timeout or
    pipeline error yields a ``non-final`` status (Req 8.5). When a real result
    is obtained but cannot be persisted, it is still returned with
    ``persisted=False`` so the caller can surface it (Req 8.4).

    Args:
        ad: The Generated_Ad result produced by a Media Agent.
        project_id: Optional owning project id; resolved from the ad when
            omitted (avoids a lookup when the orchestrator already knows it).
        user_email: Optional owning user email; resolved from the project when
            omitted.

    Returns:
        A dict ``{compliance_status, compliance_result, persisted}`` where
        ``compliance_status`` is one of ``final-compliant`` /
        ``final-non-compliant`` / ``non-final``, ``compliance_result`` is the
        pipeline payload (or an ``{"error": ...}``/empty dict), and ``persisted``
        indicates whether the outcome was recorded on the ad.
    """
    ad_id = ad.get("ad_id")
    check_id = uuid.uuid4().hex
    logger.info(
        "[ComplianceBridge] Starting compliance for ad %s (media_type=%s, check_id=%s)",
        ad_id, ad.get("media_type"), check_id,
    )

    # A failed generation has no usable output to check — withhold as non-final.
    if ad.get("status") != "completed":
        logger.info(
            "[ComplianceBridge] Ad %s is not 'completed' (status=%s); marking non-final.",
            ad_id, ad.get("status"),
        )
        result = {"error": "generation did not complete; compliance skipped"}
        persisted = _record_on_generated_ad(
            ad_id=ad_id,
            compliance_status=STATUS_NON_FINAL,
            compliance_result=result,
            compliance_check_id=check_id,
        )
        return {
            "compliance_status": STATUS_NON_FINAL,
            "compliance_result": result,
            "persisted": persisted,
        }

    # Resolve owning context (needed for the compliance_checks row).
    if project_id is None or user_email is None:
        resolved = _resolve_ad_context(ad)
        project_id = project_id if project_id is not None else resolved["project_id"]
        user_email = user_email if user_email is not None else resolved["user_email"]

    # Create the compliance_checks row so the pipeline can persist to it.
    _create_compliance_check_row(
        check_id=check_id,
        ad=ad,
        project_id=project_id or "",
        user_email=user_email or "",
    )

    # Download media locally for non-text ads.
    local_path = ""
    if ad["media_type"] != "text":
        s3_media_key = ad.get("s3_media_key")
        if s3_media_key:
            downloaded = _download_media(s3_media_key)
            if downloaded is None:
                # Cannot obtain media -> cannot run compliance -> non-final (Req 8.5).
                result = {"error": "media download failed; compliance incomplete"}
                persisted = _record_on_generated_ad(
                    ad_id=ad_id,
                    compliance_status=STATUS_NON_FINAL,
                    compliance_result=result,
                    compliance_check_id=check_id,
                )
                return {
                    "compliance_status": STATUS_NON_FINAL,
                    "compliance_result": result,
                    "persisted": persisted,
                }
            local_path = downloaded

    try:
        resolved_market = (market or DEFAULT_MARKET).strip().lower()
        state = _build_compliance_state(
            check_id=check_id, ad=ad, input_path=local_path, market=resolved_market
        )
        # Inject product context so the judge knows what the ad is for (fixes C1 hallucination).
        if product_name:
            state["user_prompt_context"] = (
                f"Product: {product_name}"
                + (f" (Category: {product_category})" if product_category else "")
                + ". Evaluate this ad for THIS product — do not flag content that matches the product."
            )
        else:
            # No product specified — tell the judge to evaluate what's visually shown,
            # NOT to hallucinate a product from the business_profiles table.
            state["user_prompt_context"] = (
                "No specific product was provided by the user. "
                "Evaluate the ad based on what is visually shown in the content. "
                "Do NOT assume a product that isn't visible. "
                "Focus on cultural, platform, and regulatory compliance only."
            )

        try:
            from jusads_compliance.compliance_pipeline import compliance_pipeline

            final_state = await asyncio.wait_for(
                compliance_pipeline.ainvoke(state),
                timeout=COMPLIANCE_TIMEOUT_SECONDS,
            )
            compliance_status = _map_verdict(final_state)
            compliance_result = (final_state or {}).get("result", {}) or {}
            # Preserve the terminal verdict alongside the analysis payload.
            if final_state and final_state.get("status"):
                compliance_result = {**compliance_result, "_verdict": final_state["status"]}
            logger.info(
                "[ComplianceBridge] Compliance completed for ad %s → %s",
                ad_id, compliance_status,
            )
        except asyncio.TimeoutError:
            logger.error(
                "[ComplianceBridge] Compliance timed out (>%ds) for ad %s",
                COMPLIANCE_TIMEOUT_SECONDS, ad_id,
            )
            compliance_status = STATUS_NON_FINAL
            compliance_result = {
                "error": f"compliance check timed out after {COMPLIANCE_TIMEOUT_SECONDS}s"
            }
        except Exception as e:
            logger.error("[ComplianceBridge] Compliance pipeline failed for ad %s: %s", ad_id, e)
            compliance_status = STATUS_NON_FINAL
            compliance_result = {"error": f"compliance pipeline failed: {e}"}

        # Record the outcome; a real result that fails to persist is still
        # surfaced with persisted=False (Req 8.4).
        persisted = _record_on_generated_ad(
            ad_id=ad_id,
            compliance_status=compliance_status,
            compliance_result=compliance_result,
            compliance_check_id=check_id,
        )

        return {
            "compliance_status": compliance_status,
            "compliance_result": compliance_result,
            "persisted": persisted,
        }
    finally:
        if local_path and os.path.exists(local_path):
            try:
                os.unlink(local_path)
            except Exception:
                pass
