"""
routes/remix.py
───────────────
Remix/remediation endpoints for compliance checks.
Handles text rewrite, audio TTS generation, and image editing.

DEPRECATION NOTE: The new Remediation Pipeline (POST /api/compliance/{task_id}/remediate)
supersedes this SSE-based remix endpoint for new clients. This module is retained for
backward compatibility with existing frontend code that uses the SSE streaming approach.
New integrations should use the /remediate endpoint + progress polling instead.
"""

import json
import logging
import os
import time as _time

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

from shared.supabase_client import SupabaseComplianceStore

logger = logging.getLogger(__name__)

router = APIRouter(tags=["remix"])

# ── Shared state (injected from app.py) ───────────────────────────────────────
_supabase_store: SupabaseComplianceStore | None = None


def init_remix(supabase_store: SupabaseComplianceStore | None) -> None:
    """Called from app.py to inject shared clients."""
    global _supabase_store
    _supabase_store = supabase_store


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# POST /api/compliance/{task_id}/remix
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.post("/api/compliance/{task_id}/remix")
async def remix_compliance(task_id: str):
    """Run AI remediation for a compliance check. Returns SSE stream.

    Routes to the appropriate remix strategy based on media type:
    - text: Gemini rewrite preserving brand voice
    - audio: Rewrite + ElevenLabs TTS generation
    - image: Concept analysis → edit (Imagen) or recreate guidance
    - video: Suggestion only (for now)
    """
    if not _supabase_store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        response = _supabase_store.client.table("compliance_checks").select(
            "task_id, media_type, market, ethnicity, age_group, platform, "
            "result_json, s3_upload_key, project_id"
        ).eq("task_id", task_id).execute()
        rows = response.data or []
        if not rows:
            return JSONResponse(status_code=404, content={"error": "Check not found"})
    except Exception as e:
        logger.error("[Remix] Failed to fetch check %s: %s", task_id, e)
        return JSONResponse(status_code=500, content={"error": str(e)})

    check = rows[0]
    media_type = check["media_type"]
    result_json = check.get("result_json") or {}
    market = check.get("market", "malaysia")
    ethnicity = check.get("ethnicity", "malay")
    age_group = check.get("age_group", "all_ages")
    platform = check.get("platform", "general")

    async def generate_events():
        def emit(event: dict) -> str:
            return f"data: {json.dumps(event)}\n\n"

        try:
            violations = result_json.get("high_risk_indicator", [])
            suggestion = result_json.get("suggestion", "")

            yield emit({"type": "node_status", "node": "generate_remediation", "status": "running"})
            start_t = _time.time()
            remix_result_data: dict = {}

            if media_type == "text":
                remix_result_data = _remix_text(violations, result_json, market, platform, ethnicity, age_group)

            elif media_type == "audio":
                remix_result_data = _remix_audio(check, violations, suggestion, result_json, market, platform, ethnicity, age_group)

            elif media_type == "image":
                # Image remix uses yield for progress streaming
                async for event_str in _remix_image_stream(
                    check, task_id, violations, suggestion, result_json,
                    market, platform, ethnicity, age_group
                ):
                    if isinstance(event_str, dict):
                        remix_result_data = event_str
                    else:
                        yield event_str

            else:
                remix_result_data = {"type": "suggestion", "suggestion": suggestion, "violations": violations}

            duration_ms = int((_time.time() - start_t) * 1000)
            yield emit({"type": "node_status", "node": "generate_remediation", "status": "completed", "duration_ms": duration_ms})

            # Persist remix result
            try:
                _supabase_store.update_check_status(
                    task_id, "remediated", result_json={**result_json, "remix": remix_result_data}
                )
            except Exception as e:
                logger.warning("[Remix] Persist failed: %s", e)

            yield emit({"type": "remix_result", "data": remix_result_data})

        except Exception as e:
            logger.error("[Remix] Error for %s: %s", task_id, e, exc_info=True)
            yield emit({"type": "node_status", "node": "error", "status": "error", "description": str(e)[:200]})

    return StreamingResponse(generate_events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEXT REMIX
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _remix_text(violations, result_json, market, platform, ethnicity, age_group) -> dict:
    """Rewrite ad text to fix compliance violations."""
    from jusads_compliance.remix_tools import rewrite_text

    text_input = result_json.get("text_input", "") or result_json.get("explanation", "")
    rewrite_result = rewrite_text.invoke({
        "text": text_input,
        "violations": violations,
        "market": market,
        "platform": platform,
        "ethnicity": ethnicity,
        "age_group": age_group,
    })
    return {
        "type": "text_rewrite",
        "original_text": text_input,
        "rewritten_text": rewrite_result.get("rewritten_text", ""),
        "changes_made": rewrite_result.get("changes_made", []),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AUDIO REMIX
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _remix_audio(check, violations, suggestion, result_json, market, platform, ethnicity, age_group) -> dict:
    """Rewrite transcript + generate replacement TTS audio."""
    from jusads_compliance.remix_tools import rewrite_text, remix_audio

    transcript = result_json.get("_transcript", {})
    transcript_text = transcript.get("transcript", "") if isinstance(transcript, dict) else ""

    rewrite_result = rewrite_text.invoke({
        "text": transcript_text or suggestion,
        "violations": violations,
        "market": market,
        "platform": platform,
        "ethnicity": ethnicity,
        "age_group": age_group,
    })
    rewritten_text = rewrite_result.get("rewritten_text", "")

    violations_timeline = result_json.get("violations_timeline") or [
        {"start": 0, "end": 30, "description": v} for v in violations
    ]
    audio_result = remix_audio.invoke({
        "audio_path": check.get("s3_upload_key", ""),
        "violations": violations_timeline,
        "replacement_text": rewritten_text,
        "market": market,
        "ethnicity": ethnicity,
    })

    remix_data: dict = {"type": "audio_remix", "rewritten_text": rewritten_text}
    if "error" not in audio_result:
        remix_data["audio_output_path"] = audio_result.get("output_path")
        remix_data["voice_id"] = audio_result.get("voice_id")
    else:
        remix_data["error"] = audio_result.get("error")

    return remix_data


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# IMAGE REMIX (async generator — yields SSE strings + final dict)
# Three-outcome triage: COMPLIANT / EDIT / CANNOT_FIX
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Valid values for input validation
_VALID_PLATFORMS = {"tiktok", "meta", "instagram", "general"}
_VALID_MARKETS = {"malaysia", "singapore"}


async def _remix_image_stream(check, task_id, violations, suggestion, result_json, market, platform, ethnicity, age_group):
    """Three-outcome image remix with triage → plan → edit flow.

    Yields SSE strings for progress and a final dict for the remix result.

    Outcomes:
      - COMPLIANT: image passes compliance, no edit needed
      - CANNOT_FIX: product/concept is the violation, return guidance
      - EDIT: plan edit via AIDesigner, execute via Imagen 3.0 inpainting
    """
    from jusads_compliance.triage import triage_decide
    from jusads_compliance.ai_designer import plan_edit
    from shared.models import TriageOutcome

    def emit(event: dict) -> str:
        return f"data: {json.dumps(event)}\n\n"

    try:
        # ── Input validation ──────────────────────────────────────────────
        risk_percentage = result_json.get("risk_percentage", 0)
        if not isinstance(risk_percentage, int):
            try:
                risk_percentage = int(risk_percentage)
            except (ValueError, TypeError):
                risk_percentage = 0
        if risk_percentage < 0 or risk_percentage > 100:
            yield emit({"type": "error", "message": f"Invalid risk_percentage: {risk_percentage}. Must be 0-100."})
            return

        if platform not in _VALID_PLATFORMS:
            yield emit({"type": "error", "message": f"Invalid platform: {platform}. Must be one of {sorted(_VALID_PLATFORMS)}."})
            return

        if market not in _VALID_MARKETS:
            yield emit({"type": "error", "message": f"Invalid market: {market}. Must be one of {sorted(_VALID_MARKETS)}."})
            return

        # ── Step 1: Triage (pure logic, no AI calls) ──────────────────────
        localization_plan = result_json.get("localization_plan", "")
        segmentation = result_json.get("segmentation")

        triage = triage_decide(
            risk_percentage=risk_percentage,
            violations=violations,
            segmentation=segmentation,
            localization_plan=localization_plan,
            platform=platform,
            market=market,
            confidence=result_json.get("overall_confidence", "high"),
        )

        logger.info("[Remix] Triage: %s — %s", triage["outcome"], triage["reasoning"])

        # ── COMPLIANT path ────────────────────────────────────────────────
        if triage["outcome"] == TriageOutcome.COMPLIANT:
            yield emit({"type": "compliant", "message": "Image passes compliance — no fix needed"})
            yield {"type": "compliant", "message": "No remix needed"}
            return

        # ── CANNOT_FIX path ───────────────────────────────────────────────
        if triage["outcome"] == TriageOutcome.CANNOT_FIX:
            yield emit({
                "type": "cannot_fix",
                "guidance": triage["guidance"],
                "reasoning": triage["reasoning"],
                "redirect_to_frontend": True,
                "violations": violations,
            })
            yield {
                "type": "cannot_fix",
                "guidance": triage["guidance"],
                "redirect_to_frontend": True,
                "violations": violations,
                "reasoning": triage["reasoning"],
            }
            return

        # ── EDIT path ─────────────────────────────────────────────────────

        # Step 2: AI Designer plans the edit
        yield emit({"type": "node_status", "node": "plan_edit", "status": "running",
                    "description": "Planning edit strategy..."})

        edit_plan = await plan_edit(
            violations=violations,
            localization_plan=localization_plan,
            platform=platform,
            market=market,
            ethnicity=ethnicity,
            age_group=age_group,
            segmentation=segmentation,
        )

        yield emit({"type": "node_status", "node": "plan_edit", "status": "completed",
                    "description": f"Mode: {edit_plan['mode']}"})

        # Step 3: Execute edit via edit_image tool
        yield emit({"type": "node_status", "node": "edit_image", "status": "running",
                    "description": "Editing image with AI..."})

        from jusads_compliance.remix_tools import edit_image

        edit_result = edit_image.invoke({
            "project_id": str(check.get("project_id", "default")),
            "task_id": task_id,
            "violations": violations,
            "market": market,
            "platform": platform,
            "ethnicity": ethnicity,
            "age_group": age_group,
            "localization_plan": localization_plan,
            "feedback": edit_plan.get("inpaint_prompt", ""),
        })

        if "error" not in edit_result:
            output_path = edit_result.get("output_path", "")
            quality_score = edit_result.get("quality_score", 0)

            # Upload to S3 if we have a local file
            s3_remix_url = None
            if output_path:
                from shared.s3_client import S3MediaClient, build_s3_key
                try:
                    s3_client = S3MediaClient()
                    user_id = str(check.get("project_id", "unknown"))
                    project_id = str(check.get("project_id", "default"))
                    remix_key = build_s3_key("remixed", user_id, project_id, task_id, os.path.basename(output_path))
                    s3_client.upload_file(output_path, remix_key)
                    s3_remix_url = s3_client.get_public_url(remix_key)
                    logger.info("[Remix] Uploaded remix to S3: %s", s3_remix_url)
                except Exception as e:
                    logger.warning("[Remix] S3 upload failed: %s", e)

            # Update DB
            if s3_remix_url and _supabase_store:
                try:
                    _supabase_store.update_check_status(task_id, "remediated", s3_remix_key=s3_remix_url)
                except Exception as e:
                    logger.warning("[Remix] DB update failed: %s", e)

            # Step 4: Lightweight bias check (non-blocking)
            bias_check = None
            if output_path:
                try:
                    from jusads_compliance.remix_tools import check_edit_bias
                    # Get original image path for comparison
                    original_url = check.get("s3_upload_key", "")
                    if original_url:
                        import urllib.request
                        import tempfile
                        original_path = os.path.join(tempfile.gettempdir(), f"bias_orig_{task_id}.png")
                        urllib.request.urlretrieve(original_url, original_path)
                        bias_check = check_edit_bias(original_path, output_path, violations)
                except Exception as e:
                    logger.warning("[Remix] Bias check failed (non-blocking): %s", e)

            yield emit({"type": "node_status", "node": "edit_image", "status": "completed",
                        "description": f"Edit complete — quality: {quality_score}/100"})

            # Build the final result — never include S3 keys or local paths
            image_edit_event = {
                "type": "image_edit",
                "s3_remix_url": s3_remix_url,
                "quality_score": quality_score,
                "edit_mode": edit_result.get("edit_mode", ""),
            }
            if bias_check:
                image_edit_event["bias_check"] = {
                    "passed": bias_check.get("passed", True),
                    "issues": bias_check.get("issues", []),
                }

            yield image_edit_event

        else:
            # All edit attempts failed
            yield emit({"type": "node_status", "node": "edit_image", "status": "failed",
                        "description": "Edit failed after all attempts"})

            yield {
                "type": "edit_failed",
                "fallback_guidance": triage["guidance"] or "Consider manual editing or recreating the image",
                "error": edit_result.get("error", "Unknown error"),
            }

    except Exception as e:
        logger.error("[Remix] Unhandled error for %s: %s", task_id, e, exc_info=True)
        yield emit({"type": "error", "message": "An unexpected error occurred during image remix. Please try again."})

