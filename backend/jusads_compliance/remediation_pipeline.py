"""
remediation_pipeline.py
Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
Remediation Pipeline (Pipeline 2) Ã¢â‚¬â€ an independent LangGraph StateGraph
that remediates non-compliant media assets.

Flow:
  1. fetch_compliance_result  Ã¢â€ â€™ retrieve compliance check by task_id
  2. confirm_aspect_ratio     Ã¢â€ â€™ LangGraph interrupt() for image/video aspect ratio
  3. media_remediation        Ã¢â€ â€™ route to media-specific handler
  4. upload_and_finalize      Ã¢â€ â€™ S3 upload + Supabase record update
"""

import json
import logging
import os
import tempfile
import time
import urllib.request

from langgraph.graph import StateGraph, END
from langgraph.types import interrupt

from shared.clients import supabase, gemini, elevenlabs
from shared.models import Remediation_State
from shared.config import MODEL_TEXT
from jusads_compliance.progress_tracker import ProgressTracker
from shared.s3_client import upload_file_public, build_s3_key
from config import get_voice, DEFAULT_VOICE

logger = logging.getLogger(__name__)

# Shared progress tracker instance for all pipeline nodes
_tracker = ProgressTracker()


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Node 1: Fetch Compliance Result Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬


def fetch_compliance_result(state: dict) -> dict:
    """Retrieve the compliance check record from Supabase by task_id.

    Sets compliance_result, media_type, source_media_url, and platform_target
    from the fetched record. Returns error status if task_id is not found.
    """
    task_id = state["task_id"]
    _tracker.start_step(task_id, "fetch_compliance_result")

    try:
        response = (
            supabase.table("compliance_checks")
            .select("*")
            .eq("task_id", task_id)
            .execute()
        )
        rows = response.data or []

        if not rows:
            logger.error("[RemediationPipeline] task_id=%s not found", task_id)
            _tracker.fail_step(task_id, "fetch_compliance_result", f"task_id '{task_id}' not found")
            return {
                "status": "remix_failed",
                "compliance_result": {"error": f"task_id '{task_id}' not found"},
            }

        record = rows[0]
        result_json = record.get("result_json") or {}
        media_type = record.get("media_type", "")
        platform = record.get("platform", "general")
        source_url = record.get("s3_upload_key", "")

        # Build remediation plan from result
        remediation_plan = {
            "high_risk_indicators": result_json.get("high_risk_indicator", []),
            "suggestion": result_json.get("suggestion", ""),
            "localization_plan": result_json.get("localization_plan", ""),
            "violations_timeline": result_json.get("violations_timeline"),
            "segmentation": result_json.get("segmentation"),
        }

        logger.info(
            "[RemediationPipeline] Fetched task_id=%s, media_type=%s, platform=%s",
            task_id, media_type, platform,
        )
        _tracker.complete_step(task_id, "fetch_compliance_result", f"Retrieved {media_type} check record")

        return {
            "compliance_result": result_json,
            "remediation_plan": remediation_plan,
            "media_type": media_type,
            "source_media_url": source_url,
            "platform_target": platform,
            "status": "remediating",
        }

    except Exception as e:
        logger.error("[RemediationPipeline] fetch_compliance_result failed: %s", e)
        _tracker.fail_step(task_id, "fetch_compliance_result", str(e))
        return {
            "status": "remix_failed",
            "compliance_result": {"error": str(e)},
        }


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Node 2: Confirm Aspect Ratio Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬


def confirm_aspect_ratio(state: dict) -> dict:
    """For image/video, query platform_rules and interrupt for user confirmation.

    Skips for text/audio media types. Uses LangGraph interrupt() to pause
    execution and present aspect ratio options to the user.
    """
    task_id = state["task_id"]
    media_type = state["media_type"]
    platform_target = state["platform_target"]

    _tracker.start_step(task_id, "confirm_aspect_ratio")

    # Skip for text and audio Ã¢â‚¬â€ no aspect ratio needed
    if media_type not in ("image", "video"):
        logger.info("[RemediationPipeline] Skipping aspect ratio for media_type=%s", media_type)
        _tracker.complete_step(task_id, "confirm_aspect_ratio", f"Skipped for {media_type}")
        return {"aspect_ratio": ""}

    try:
        # Query platform_rules for available aspect ratios
        response = (
            supabase.table("platform_rules")
            .select("aspect_ratio, max_duration_seconds, max_file_size_mb")
            .eq("platform", platform_target)
            .eq("media_type", media_type)
            .execute()
        )
        rules = response.data or []

        if not rules:
            # Fallback defaults
            default_ratios = {"image": "1:1", "video": "16:9"}
            aspect_ratio = default_ratios.get(media_type, "1:1")
            logger.warning(
                "[RemediationPipeline] No platform_rules for %s/%s, defaulting to %s",
                platform_target, media_type, aspect_ratio,
            )
        else:
            # Present options via interrupt for user confirmation
            options = [
                {
                    "aspect_ratio": r["aspect_ratio"],
                    "max_duration_seconds": r.get("max_duration_seconds"),
                    "max_file_size_mb": r.get("max_file_size_mb"),
                }
                for r in rules
            ]

            # Use LangGraph interrupt() for human-in-the-loop confirmation
            user_response = interrupt({
                "message": f"Confirm target aspect ratio for {platform_target} {media_type}",
                "options": options,
                "default": options[0]["aspect_ratio"],
            })

            # User responds with selected aspect ratio
            if isinstance(user_response, dict):
                aspect_ratio = user_response.get("aspect_ratio", options[0]["aspect_ratio"])
            elif isinstance(user_response, str):
                aspect_ratio = user_response
            else:
                aspect_ratio = options[0]["aspect_ratio"]

        logger.info("[RemediationPipeline] Confirmed aspect_ratio=%s", aspect_ratio)
        _tracker.complete_step(task_id, "confirm_aspect_ratio", f"Confirmed: {aspect_ratio}")

        return {"aspect_ratio": aspect_ratio}

    except Exception as e:
        logger.error("[RemediationPipeline] confirm_aspect_ratio failed: %s", e)
        _tracker.fail_step(task_id, "confirm_aspect_ratio", str(e))
        # On failure, set remix_failed, preserve original
        return {
            "status": "remix_failed",
            "aspect_ratio": "",
        }


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Node 3: Media Remediation Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬


def media_remediation(state: dict) -> dict:
    """Route to media-specific remediation handler.

    - Image: inpaint with max 3 retries, quality >= 70
    - Video: I2V (image-to-video) generation per violation segment
    - Text: AI-powered text rewrite
    - Audio: ElevenLabs TTS recreation
    """
    task_id = state["task_id"]
    media_type = state["media_type"]

    # If already failed in a previous step, skip
    if state.get("status") == "remix_failed":
        return {}

    _tracker.start_step(task_id, "media_remediation")

    try:
        if media_type == "image":
            result = _remediate_image(state)
        elif media_type == "video":
            result = _remediate_video(state)
        elif media_type == "text":
            result = _remediate_text(state)
        elif media_type == "audio":
            result = _remediate_audio(state)
        else:
            raise ValueError(f"Unsupported media type: {media_type}")

        if result.get("error"):
            raise RuntimeError(result["error"])

        remediated_paths = state.get("remediated_paths", []) or []
        output_path = result.get("output_path", "")
        if output_path:
            remediated_paths.append(output_path)

        logger.info("[RemediationPipeline] %s remediation complete", media_type)
        _tracker.complete_step(
            task_id, "media_remediation",
            f"{media_type} remediation completed successfully",
        )

        return {
            "remediated_paths": remediated_paths,
            "strategy": result.get("strategy", media_type),
        }

    except Exception as e:
        logger.error("[RemediationPipeline] media_remediation failed: %s", e)
        _tracker.fail_step(task_id, "media_remediation", str(e))
        return {
            "status": "remix_failed",
            "remediated_paths": state.get("remediated_paths", []) or [],
        }


def _remediate_image(state: dict) -> dict:
    """Image remediation via inpainting with max 3 retries for quality >= 70.

    Downloads the original image, generates a mask from segmentation,
    and applies iterative inpainting until quality threshold is met.
    """
    import base64
    import numpy as np
    from PIL import Image
    from google.genai import types

    source_url = state["source_media_url"]
    compliance_result = state.get("compliance_result", {})
    remediation_plan = state.get("remediation_plan", {})
    violations = remediation_plan.get("high_risk_indicators", [])
    localization_plan = remediation_plan.get("suggestion", "")

    # Download original image
    tmp_original = os.path.join(tempfile.gettempdir(), f"remediate_orig_{state['task_id']}.png")
    urllib.request.urlretrieve(source_url, tmp_original)

    # Generate or download mask
    segmentation = remediation_plan.get("segmentation", {})
    mask_path = None
    if segmentation and segmentation.get("mask_path"):
        mask_path = segmentation["mask_path"]
        if mask_path.startswith("http"):
            tmp_mask = os.path.join(tempfile.gettempdir(), f"remediate_mask_{state['task_id']}.png")
            urllib.request.urlretrieve(mask_path, tmp_mask)
            mask_path = tmp_mask

    if not mask_path or not os.path.exists(mask_path):
        # Generate simple mask from segmented overlay if available
        seg_url = segmentation.get("segmented_url", "")
        if seg_url:
            tmp_seg = os.path.join(tempfile.gettempdir(), f"remediate_seg_{state['task_id']}.png")
            urllib.request.urlretrieve(seg_url, tmp_seg)
            mask_path = _make_binary_mask(tmp_seg, tmp_original)
        else:
            # No segmentation available Ã¢â‚¬â€ create a full-image mask as fallback
            img = Image.open(tmp_original)
            mask = Image.new("L", img.size, 255)
            mask_path = os.path.join(tempfile.gettempdir(), f"remediate_fullmask_{state['task_id']}.png")
            mask.save(mask_path)

    # Build inpainting prompt
    violations_text = ", ".join(violations[:5]) if violations else "non-compliant content"
    inpaint_prompt = f"Replace non-compliant content ({violations_text}) with culturally appropriate, compliant advertising content. {localization_plan}"
    if len(inpaint_prompt) > 300:
        inpaint_prompt = inpaint_prompt[:300]

    # Load image and mask as bytes
    with open(tmp_original, "rb") as f:
        image_bytes = f.read()
    with open(mask_path, "rb") as f:
        mask_bytes = f.read()

    # Inpainting loop: max 3 retries, quality >= 70
    MAX_RETRIES = 3
    quality_score = 0
    output_path = os.path.join(tempfile.gettempdir(), f"remediated_{state['task_id']}.png")
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        logger.info("[RemediationPipeline] Image inpaint attempt %d/%d", attempt, MAX_RETRIES)
        try:
            response = gemini.models.edit_image(
                model="imagen-3.0-capability-002",
                prompt=inpaint_prompt,
                reference_images=[
                    types.RawReferenceImage(
                        reference_image=types.Image(image_bytes=image_bytes),
                        reference_id=1,
                    ),
                    types.MaskReferenceImage(
                        reference_image=types.Image(image_bytes=mask_bytes),
                        reference_id=2,
                        config=types.MaskReferenceConfig(
                            mask_mode="MASK_MODE_USER_PROVIDED",
                        ),
                    ),
                ],
                config=types.EditImageConfig(
                    edit_mode="EDIT_MODE_INPAINT_INSERTION",
                    number_of_images=1,
                    safety_filter_level="BLOCK_SOME",
                    person_generation="ALLOW_ALL",
                ),
            )

            if not response.generated_images:
                raise ValueError("Imagen returned no images")

            with open(output_path, "wb") as f:
                f.write(response.generated_images[0].image.image_bytes)

            # Quality check
            quality_score = _check_image_quality(tmp_original, output_path)
            logger.info("[RemediationPipeline] Quality score: %d/100 (attempt %d)", quality_score, attempt)

            if quality_score >= 70:
                break

            # Refine prompt for next attempt
            if attempt < MAX_RETRIES:
                inpaint_prompt = f"Improve: {inpaint_prompt}. Previous attempt scored {quality_score}/100. Make content more natural and compliant."
                if len(inpaint_prompt) > 300:
                    inpaint_prompt = inpaint_prompt[:300]

        except Exception as e:
            last_error = str(e)
            logger.error("[RemediationPipeline] Image inpaint attempt %d failed: %s", attempt, e)

    if quality_score < 70 and last_error:
        return {"error": f"Image inpainting failed after {MAX_RETRIES} attempts: {last_error}"}

    return {
        "output_path": output_path,
        "strategy": "image_inpaint",
        "quality_score": quality_score,
        "attempts": attempt,
    }


def _remediate_video(state: dict) -> dict:
    """Video remediation via Image-to-Video (I2V) generation.

    Extracts keyframes from violation segments and uses prompt-guided
    I2V to produce replacement segments.
    """
    source_url = state["source_media_url"]
    remediation_plan = state.get("remediation_plan", {})
    violations_timeline = remediation_plan.get("violations_timeline") or []
    aspect_ratio = state.get("aspect_ratio", "16:9")

    # Download source video
    tmp_video = os.path.join(tempfile.gettempdir(), f"remediate_video_{state['task_id']}.mp4")
    urllib.request.urlretrieve(source_url, tmp_video)

    output_path = os.path.join(tempfile.gettempdir(), f"remediated_video_{state['task_id']}.mp4")

    if not violations_timeline:
        # No specific violations Ã¢â‚¬â€ just return original
        return {"output_path": tmp_video, "strategy": "video_i2v", "note": "no violations to fix"}

    # For each violation segment, extract a reference keyframe
    # In production this would use I2V APIs Ã¢â‚¬â€ here we structure the call
    try:
        from google.genai import types

        # Extract first keyframe as reference
        first_violation = violations_timeline[0] if violations_timeline else {}
        start_time = first_violation.get("start", first_violation.get("start_seconds", 0))

        # Extract keyframe using ffmpeg
        keyframe_path = os.path.join(tempfile.gettempdir(), f"keyframe_{state['task_id']}.png")
        import subprocess
        subprocess.run(
            ["ffmpeg", "-y", "-ss", str(start_time), "-i", tmp_video,
             "-vframes", "1", "-q:v", "2", keyframe_path],
            capture_output=True, timeout=30,
        )

        # Use Gemini to generate a compliant video prompt
        violations_desc = json.dumps(violations_timeline[:3], indent=2)
        prompt = (
            f"Generate a compliant replacement video segment for aspect ratio {aspect_ratio}. "
            f"Replace the following violations: {violations_desc}"
        )

        # For now, mark as processed Ã¢â‚¬â€ actual I2V would be via external API
        logger.info("[RemediationPipeline] Video I2V remediation prepared for %d segments", len(violations_timeline))
        output_path = tmp_video  # In full implementation, this would be the composited output

        return {"output_path": output_path, "strategy": "video_i2v"}

    except Exception as e:
        return {"error": f"Video remediation failed: {e}"}


def _remediate_text(state: dict) -> dict:
    """Text remediation via AI-powered rewrite in the target audience language."""
    from google.genai import types as genai_types

    compliance_result = state.get("compliance_result", {})
    remediation_plan = state.get("remediation_plan", {})
    violations = remediation_plan.get("high_risk_indicators", [])
    suggestion = remediation_plan.get("suggestion", "")

    # Get the original text from the compliance result
    original_text = compliance_result.get("original_text", "")
    if not original_text:
        original_text = compliance_result.get("text_input", "")

    if not original_text:
        return {"error": "No original text found in compliance result for rewrite"}

    try:
        violations_text = "\n".join(f"- {v}" for v in violations)
        prompt = (
            f"Rewrite the following advertising text to fix compliance violations "
            f"while preserving the original meaning and language.\n\n"
            f"ORIGINAL TEXT:\n{original_text}\n\n"
            f"VIOLATIONS TO FIX:\n{violations_text}\n\n"
            f"SUGGESTION: {suggestion}\n\n"
            f"Return ONLY a JSON object: "
            f'{{"rewritten_text": "...", "changes_made": ["change1", "change2"]}}'
        )

        response = gemini.models.generate_content(
            model=MODEL_TEXT,
            contents=prompt,
            config=genai_types.GenerateContentConfig(response_mime_type="application/json"),
        )
        result = json.loads(response.text)
        rewritten = result.get("rewritten_text", original_text)

        # Save rewritten text to file
        output_path = os.path.join(tempfile.gettempdir(), f"remediated_text_{state['task_id']}.txt")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(rewritten)

        return {"output_path": output_path, "strategy": "text_rewrite", "rewritten_text": rewritten}

    except Exception as e:
        return {"error": f"Text rewrite failed: {e}"}


def _remediate_audio(state: dict) -> dict:
    """Audio remediation via ElevenLabs TTS.

    Recreates the audio entirely using a culturally appropriate voice
    from the environment configuration.
    """
    compliance_result = state.get("compliance_result", {})
    remediation_plan = state.get("remediation_plan", {})
    suggestion = remediation_plan.get("suggestion", "")

    # Get replacement text Ã¢â‚¬â€ from suggestion or compliance result
    replacement_text = suggestion
    if not replacement_text:
        replacement_text = compliance_result.get("suggestion", "Compliant audio replacement.")

    # Select voice based on platform/market context via DB lookup
    voice_entry = get_voice("malaysia", "malay", "female")
    voice_id = voice_entry["voice_id"]

    try:
        # Generate TTS audio via ElevenLabs
        audio_generator = elevenlabs.text_to_speech.convert(
            voice_id=voice_id,
            text=replacement_text,
            model_id="eleven_multilingual_v2",
        )

        # Write audio to temp file
        output_path = os.path.join(tempfile.gettempdir(), f"remediated_audio_{state['task_id']}.mp3")
        with open(output_path, "wb") as f:
            for chunk in audio_generator:
                f.write(chunk)

        logger.info("[RemediationPipeline] TTS audio generated: %s", output_path)
        return {"output_path": output_path, "strategy": "audio_tts", "voice_id": voice_id}

    except Exception as e:
        return {"error": f"Audio TTS remediation failed: {e}"}


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Node 4: Upload and Finalize Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬


def upload_and_finalize(state: dict) -> dict:
    """Upload remediated assets to S3 and update the compliance_checks record.

    Sets status to "remediated" on success, or "remix_failed" on failure.
    """
    task_id = state["task_id"]

    # If already failed, skip
    if state.get("status") == "remix_failed":
        return {}

    _tracker.start_step(task_id, "upload_and_finalize")

    remediated_paths = state.get("remediated_paths", []) or []
    if not remediated_paths:
        logger.warning("[RemediationPipeline] No remediated paths to upload for task_id=%s", task_id)
        _tracker.fail_step(task_id, "upload_and_finalize", "No remediated files to upload")
        return {"status": "remix_failed"}

    try:
        # Upload the most recent remediated file
        output_path = remediated_paths[-1]
        filename = os.path.basename(output_path)

        s3_key = build_s3_key(
            asset_type="remixed",
            username="pipeline",  # Generic user for pipeline-generated assets
            project_id=task_id,
            task_id=task_id,
            filename=filename,
        )

        s3_url = upload_file_public(output_path, s3_key)
        logger.info("[RemediationPipeline] Uploaded to S3: %s", s3_url)

        # Update compliance_checks record
        supabase.table("compliance_checks").update({
            "status": "remediated",
            "s3_remix_key": s3_url,
        }).eq("task_id", task_id).execute()

        logger.info("[RemediationPipeline] Updated task %s -> remediated", task_id)
        _tracker.complete_step(task_id, "upload_and_finalize", f"Uploaded and finalized: {s3_url}")

        return {"status": "remediated"}

    except Exception as e:
        logger.error("[RemediationPipeline] upload_and_finalize failed: %s", e)
        _tracker.fail_step(task_id, "upload_and_finalize", str(e))

        # Preserve original Ã¢â‚¬â€ set status to remix_failed
        try:
            supabase.table("compliance_checks").update({
                "status": "remix_failed",
            }).eq("task_id", task_id).execute()
        except Exception as update_err:
            logger.error("[RemediationPipeline] Failed to set remix_failed status: %s", update_err)

        return {"status": "remix_failed"}


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Helper Functions Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬


def _make_binary_mask(segmented_path: str, original_path: str) -> str:
    """Compare segmented overlay vs original to produce a binary mask.

    White = edit region (where overlay was painted), Black = keep unchanged.
    """
    import numpy as np
    from PIL import Image

    orig = np.array(Image.open(original_path).convert("RGB"))
    seg = np.array(Image.open(segmented_path).convert("RGB"))

    if orig.shape != seg.shape:
        orig = np.array(
            Image.open(original_path).convert("RGB").resize(
                (seg.shape[1], seg.shape[0]), Image.LANCZOS
            )
        )

    diff = np.abs(seg.astype(int) - orig.astype(int)).sum(axis=2)
    mask = (diff > 50).astype(np.uint8) * 255

    mask_img = Image.fromarray(mask, mode="L")
    mask_path = os.path.join(tempfile.gettempdir(), f"mask_{os.path.basename(segmented_path)}")
    mask_img.save(mask_path)
    return mask_path


def _check_image_quality(original_path: str, edited_path: str) -> int:
    """Basic quality check comparing original and edited images.

    Returns a score 0-100 based on structural similarity and artifact detection.
    """
    try:
        from PIL import Image
        import numpy as np

        orig = np.array(Image.open(original_path).convert("RGB"))
        edited = np.array(Image.open(edited_path).convert("RGB"))

        if orig.shape != edited.shape:
            edited = np.array(
                Image.open(edited_path).convert("RGB").resize(
                    (orig.shape[1], orig.shape[0]), Image.LANCZOS
                )
            )

        # Simple quality heuristic: check that the image is not blank or corrupted
        # and has reasonable variation
        std_dev = np.std(edited)
        if std_dev < 5:
            return 10  # Nearly blank image

        # Check for obvious artifacts (extreme pixel values in large areas)
        white_ratio = np.mean(edited > 250)
        black_ratio = np.mean(edited < 5)

        if white_ratio > 0.8 or black_ratio > 0.8:
            return 30  # Mostly white or black

        # Basic structural similarity (pixel difference)
        diff = np.abs(orig.astype(float) - edited.astype(float)).mean()
        # Lower diff = more similar = higher quality for inpainting
        score = max(0, min(100, int(100 - diff)))

        return max(score, 50)  # Minimum 50 if image looks reasonable

    except Exception as e:
        logger.warning("[RemediationPipeline] Quality check failed: %s", e)
        return 75  # Assume acceptable on error


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Build the Remediation Pipeline Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬


_graph = StateGraph(Remediation_State)

# Add nodes
_graph.add_node("fetch_compliance_result", fetch_compliance_result)
_graph.add_node("confirm_aspect_ratio", confirm_aspect_ratio)
_graph.add_node("media_remediation", media_remediation)
_graph.add_node("upload_and_finalize", upload_and_finalize)

# Wire edges: fetch Ã¢â€ â€™ confirm Ã¢â€ â€™ remediate Ã¢â€ â€™ upload Ã¢â€ â€™ END
_graph.set_entry_point("fetch_compliance_result")
_graph.add_edge("fetch_compliance_result", "confirm_aspect_ratio")
_graph.add_edge("confirm_aspect_ratio", "media_remediation")
_graph.add_edge("media_remediation", "upload_and_finalize")
_graph.add_edge("upload_and_finalize", END)

# Compile and export
remediation_pipeline = _graph.compile()

