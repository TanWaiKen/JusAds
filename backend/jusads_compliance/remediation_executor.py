"""
remediation_executor.py
───────────────────────
Intelligent Remediation Executor — takes RoutingDecision from the AI Tool Router
and executes the selected tools in order.

This is the bridge between the AI's decision and actual tool execution.
Each tool execution is non-destructive (original preserved, new version created).

Flow:
  1. Receive RoutingDecision from tool_router
  2. Download source media
  3. Execute tools sequentially (output of one feeds into next)
  4. Upload final result to S3
  5. Create new version record (linked via parent_ad_id)
"""

import json
import logging
import os
import tempfile
import urllib.request
from typing import Optional

from shared.clients import supabase, gemini
from shared.s3_client import upload_file_public, build_s3_key
from shared.config import MODEL_TEXT
from jusads_compliance.tool_router import RoutingDecision, ToolSelection

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Main executor
# -----------------------------------------------------------------------------


async def execute_remediation(
    routing_decision: RoutingDecision,
    check_id: str,
    source_media_url: str,
    project_id: str,
    user_email: str,
    compliance_result: Optional[dict] = None,
    market: str = "malaysia",
    ethnicity: str = "malay",
    gender: str = "female",
) -> dict:
    """Execute the remediation plan from the AI Tool Router.

    Downloads the source media, applies each tool sequentially, uploads
    the result, and records the new version.

    Args:
        routing_decision: The RoutingDecision from tool_router.route_remediation().
        check_id: Compliance check ID this remediation belongs to.
        source_media_url: S3 URL of the original media.
        project_id: Project this belongs to.
        user_email: Owner's email.
        compliance_result: Full compliance result dict for context.
        market: Market context for voice selection etc.
        ethnicity: Ethnicity context.
        gender: Gender context.

    Returns:
        Dict with:
          - status: "remediated" | "partially_remediated" | "failed"
          - output_url: S3 URL of the remediated media (if success)
          - tools_applied: List of tool names that were applied
          - tools_failed: List of tools that failed
          - strategy_summary: Description of what was done
    """
    media_type = routing_decision.media_type
    tools = routing_decision.tools

    if not tools:
        return {"status": "failed", "error": "No tools in routing decision"}

    # Download source media to temp
    extension = _get_extension(media_type, source_media_url)
    tmp_source = os.path.join(tempfile.gettempdir(), f"remediate_src_{check_id}{extension}")

    try:
        urllib.request.urlretrieve(source_media_url, tmp_source)
    except Exception as e:
        logger.error("[Executor] Failed to download source: %s", e)
        return {"status": "failed", "error": f"Source download failed: {e}"}

    # Execute tools sequentially — output of one is input to next
    current_path = tmp_source
    tools_applied: list[str] = []
    tools_failed: list[str] = []
    tool_results: list[dict] = []

    for tool_selection in tools:
        logger.info("[Executor] Applying tool: %s", tool_selection.tool)

        try:
            result = _execute_tool(
                tool_name=tool_selection.tool,
                input_path=current_path,
                media_type=media_type,
                tool_selection=tool_selection,
                check_id=check_id,
                project_id=project_id,
                compliance_result=compliance_result or {},
                market=market,
                ethnicity=ethnicity,
                gender=gender,
            )

            if "error" in result:
                logger.warning("[Executor] Tool %s failed: %s", tool_selection.tool, result["error"])
                tools_failed.append(tool_selection.tool)
                tool_results.append({"tool": tool_selection.tool, "status": "failed", "error": result["error"]})
            else:
                new_path = result.get("output_path")
                if new_path and os.path.exists(new_path):
                    current_path = new_path
                    tools_applied.append(tool_selection.tool)
                    tool_results.append({"tool": tool_selection.tool, "status": "success"})
                else:
                    tools_failed.append(tool_selection.tool)
                    tool_results.append({"tool": tool_selection.tool, "status": "failed", "error": "No output file"})

        except Exception as e:
            logger.error("[Executor] Tool %s crashed: %s", tool_selection.tool, e)
            tools_failed.append(tool_selection.tool)
            tool_results.append({"tool": tool_selection.tool, "status": "failed", "error": str(e)})

    # Determine final status
    if not tools_applied:
        status = "failed"
    elif tools_failed:
        status = "partially_remediated"
    else:
        status = "remediated"

    # Upload result to S3
    output_url = None
    if tools_applied and current_path != tmp_source:
        try:
            filename = f"remediated_{check_id}{extension}"
            s3_key = build_s3_key("remixed", user_email, project_id, check_id, filename)
            output_url = upload_file_public(current_path, s3_key)
            logger.info("[Executor] Uploaded remediated media: %s", output_url)
        except Exception as e:
            logger.error("[Executor] S3 upload failed: %s", e)
            status = "partially_remediated"

    # Update compliance check record
    if supabase and output_url:
        try:
            supabase.table("compliance_checks").update({
                "status": status,
                "s3_remix_key": output_url,
                "result_json": supabase.table("compliance_checks")
                    .select("result_json")
                    .eq("check_id", check_id)
                    .execute()
                    .data[0].get("result_json", {}),
            }).eq("check_id", check_id).execute()

            # Actually update with remix info merged into result_json
            existing = supabase.table("compliance_checks").select("result_json").eq("check_id", check_id).execute()
            existing_result = (existing.data[0] if existing.data else {}).get("result_json", {})
            existing_result["remix"] = {
                "output_url": output_url,
                "tools_applied": tools_applied,
                "strategy": routing_decision.strategy_summary,
                "severity": routing_decision.overall_severity,
            }
            supabase.table("compliance_checks").update({
                "status": status,
                "s3_remix_key": output_url,
                "result_json": existing_result,
            }).eq("check_id", check_id).execute()

        except Exception as e:
            logger.warning("[Executor] DB update failed: %s", e)

    # Cleanup temp files
    _cleanup_temp(tmp_source, current_path)

    return {
        "status": status,
        "output_url": output_url,
        "tools_applied": tools_applied,
        "tools_failed": tools_failed,
        "tool_results": tool_results,
        "strategy_summary": routing_decision.strategy_summary,
        "overall_severity": routing_decision.overall_severity,
        "confidence": routing_decision.confidence,
    }


# -----------------------------------------------------------------------------
# Tool dispatcher
# -----------------------------------------------------------------------------


def _execute_tool(
    tool_name: str,
    input_path: str,
    media_type: str,
    tool_selection: ToolSelection,
    check_id: str,
    project_id: str,
    compliance_result: dict,
    market: str,
    ethnicity: str,
    gender: str,
) -> dict:
    """Dispatch to the specific tool implementation.

    Returns dict with output_path on success, or error key on failure.
    """
    target = tool_selection.target_description

    # -- VIDEO TOOLS -------------------------------------------------------
    if tool_name == "capcut_text_overlay":
        from jusads_compliance.capcut_client import add_text_overlay
        # Use target_description as the overlay text
        overlay_text = target if target else "Compliant content"
        return add_text_overlay(input_path, overlay_text)

    elif tool_name == "capcut_trim":
        from jusads_compliance.capcut_client import trim_segment
        # Extract timestamps from violations_timeline
        timeline = compliance_result.get("violations_timeline", [])
        if timeline:
            first = timeline[0]
            start = first.get("start", first.get("start_seconds", 0))
            end = first.get("end", first.get("end_seconds", start + 5))
            return trim_segment(input_path, start, end)
        return {"error": "No violation timeline for trim"}

    elif tool_name == "capcut_speed_ramp":
        from jusads_compliance.capcut_client import speed_ramp
        timeline = compliance_result.get("violations_timeline", [])
        if timeline:
            first = timeline[0]
            start = first.get("start", 0)
            end = first.get("end", start + 5)
            return speed_ramp(input_path, start, end, speed_factor=1.5)
        return speed_ramp(input_path, 0, 5, speed_factor=1.5)

    elif tool_name == "capcut_scene_replace":
        # Scene replacement: trim out the bad segment, add transition
        from jusads_compliance.capcut_client import trim_segment, add_transition
        timeline = compliance_result.get("violations_timeline", [])
        if timeline:
            first = timeline[0]
            start = first.get("start", 0)
            end = first.get("end", start + 5)
            trim_result = trim_segment(input_path, start, end)
            if "error" not in trim_result:
                # Add smooth transition at the cut point
                return add_transition(trim_result["output_path"], start, "fade", 0.5)
            return trim_result
        return {"error": "No violation timeline for scene replace"}

    elif tool_name == "capcut_transition":
        from jusads_compliance.capcut_client import add_transition
        timeline = compliance_result.get("violations_timeline", [])
        point = timeline[0].get("start", 3.0) if timeline else 3.0
        return add_transition(input_path, point, "fade", 0.5)

    elif tool_name == "omni_video_edit":
        # AI-powered video-to-video editing / character change via gemini-omni-flash-preview
        instruction = target if target else "Edit the video to be compliant"
        return _execute_omni_video_edit(input_path, instruction)

    elif tool_name == "veo_regenerate":
        # Full video regeneration using Gemini Omni
        instruction = target if target else "Regenerate the video to be compliant"
        return _execute_veo_regenerate(instruction, compliance_result)

    # -- IMAGE TOOLS -------------------------------------------------------
    elif tool_name == "inpaint_area":
        # Use existing inpainting from remediation_pipeline
        from jusads_compliance.remediation_pipeline import _remediate_image
        state = {
            "check_id": check_id,
            "source_media_url": input_path if input_path.startswith("http") else f"file://{input_path}",
            "compliance_result": compliance_result,
            "remediation_plan": {
                "high_risk_indicators": compliance_result.get("high_risk_indicator", []),
                "suggestion": compliance_result.get("suggestion", ""),
                "segmentation": compliance_result.get("segmentation"),
            },
        }
        # For local files, we need to adjust
        result = _inpaint_local(input_path, compliance_result)
        return result

    elif tool_name == "imagen_constrained":
        return _inpaint_local(input_path, compliance_result, max_retries=2)

    elif tool_name == "imagen_full_regen":
        return {"error": "Full image regeneration — use generation pipeline instead"}

    # -- AUDIO TOOLS -------------------------------------------------------
    elif tool_name == "elevenlabs_dub_segment":
        from jusads_compliance.voice_clone_manager import dub_segment
        # Get the replacement text from compliance suggestion
        replacement_text = target or compliance_result.get("suggestion", "Compliant audio")
        output = dub_segment(replacement_text, project_id=project_id, market=market, ethnicity=ethnicity, gender=gender)
        if output:
            return {"output_path": output}
        return {"error": "Dub segment generation failed"}

    elif tool_name == "elevenlabs_voice_clone_reread":
        from jusads_compliance.voice_clone_manager import full_reread
        script = target or compliance_result.get("suggestion", "")
        if not script:
            # Try to get from transcript
            transcript = compliance_result.get("_transcript", {})
            script = transcript.get("transcript", "") if isinstance(transcript, dict) else ""
        if not script:
            return {"error": "No script text for voice clone re-read"}
        output = full_reread(script, project_id=project_id, market=market, ethnicity=ethnicity, gender=gender)
        if output:
            return {"output_path": output}
        return {"error": "Voice clone re-read failed"}

    elif tool_name == "elevenlabs_new_vo":
        from jusads_compliance.voice_clone_manager import full_reread
        # New VO from scratch using compliance suggestion as script
        new_script = compliance_result.get("suggestion", target or "New compliant voiceover")
        output = full_reread(new_script, project_id=project_id, market=market, ethnicity=ethnicity, gender=gender)
        if output:
            return {"output_path": output}
        return {"error": "New VO generation failed"}

    elif tool_name == "elevenlabs_sfx_replace":
        # SFX replacement via ElevenLabs sound generation
        return _generate_sfx_replacement(target or "ambient background music", check_id)

    # -- TEXT TOOLS --------------------------------------------------------
    elif tool_name == "gemini_rewrite_phrase":
        return _rewrite_text(input_path, compliance_result, mode="phrase")

    elif tool_name == "gemini_full_rewrite":
        return _rewrite_text(input_path, compliance_result, mode="full")

    elif tool_name == "gemini_new_copy":
        return _rewrite_text(input_path, compliance_result, mode="new")

    else:
        return {"error": f"Unknown tool: {tool_name}"}


# -----------------------------------------------------------------------------
# Tool implementations
# -----------------------------------------------------------------------------


def _inpaint_local(input_path: str, compliance_result: dict, max_retries: int = 3) -> dict:
    """Inpaint an image using Imagen, working with local file path."""
    from google.genai import types
    from PIL import Image
    import numpy as np

    violations = compliance_result.get("high_risk_indicator", [])
    suggestion = compliance_result.get("suggestion", "")
    segmentation = compliance_result.get("segmentation", {})

    try:
        # Read image bytes
        with open(input_path, "rb") as f:
            image_bytes = f.read()

        # Generate or load mask
        mask_bytes = None
        if segmentation and segmentation.get("mask_path"):
            mask_path = segmentation["mask_path"]
            if mask_path.startswith("http"):
                tmp_mask = os.path.join(tempfile.gettempdir(), f"mask_{os.path.basename(input_path)}")
                urllib.request.urlretrieve(mask_path, tmp_mask)
                with open(tmp_mask, "rb") as f:
                    mask_bytes = f.read()
            elif os.path.exists(mask_path):
                with open(mask_path, "rb") as f:
                    mask_bytes = f.read()

        if not mask_bytes:
            # Create full-image mask as fallback
            img = Image.open(input_path)
            mask = Image.new("L", img.size, 255)
            tmp_mask = os.path.join(tempfile.gettempdir(), f"fullmask_{os.path.basename(input_path)}")
            mask.save(tmp_mask)
            with open(tmp_mask, "rb") as f:
                mask_bytes = f.read()

        # Build prompt
        violations_text = ", ".join(violations[:3]) if violations else "non-compliant content"
        prompt = f"Replace ({violations_text}) with compliant content. {suggestion}"[:300]

        # Inpaint with retry
        output_path = os.path.join(tempfile.gettempdir(), f"inpainted_{os.path.basename(input_path)}")

        for attempt in range(1, max_retries + 1):
            try:
                response = gemini.models.edit_image(
                    model="imagen-3.0-capability-002",
                    prompt=prompt,
                    reference_images=[
                        types.RawReferenceImage(
                            reference_image=types.Image(image_bytes=image_bytes),
                            reference_id=1,
                        ),
                        types.MaskReferenceImage(
                            reference_image=types.Image(image_bytes=mask_bytes),
                            reference_id=2,
                            config=types.MaskReferenceConfig(mask_mode="MASK_MODE_USER_PROVIDED"),
                        ),
                    ],
                    config=types.EditImageConfig(
                        edit_mode="EDIT_MODE_INPAINT_INSERTION",
                        number_of_images=1,
                        safety_filter_level="BLOCK_SOME",
                        person_generation="ALLOW_ALL",
                    ),
                )

                if response.generated_images:
                    with open(output_path, "wb") as f:
                        f.write(response.generated_images[0].image.image_bytes)
                    return {"output_path": output_path, "operation": "inpaint", "attempts": attempt}

            except Exception as e:
                logger.warning("[Executor] Inpaint attempt %d failed: %s", attempt, e)

        return {"error": f"Inpainting failed after {max_retries} attempts"}

    except Exception as e:
        return {"error": f"Inpaint setup failed: {e}"}


def _generate_sfx_replacement(description: str, check_id: str) -> dict:
    """Generate replacement SFX using ElevenLabs sound generation."""
    from shared.clients import elevenlabs as el_client

    if not el_client:
        return {"error": "ElevenLabs unavailable for SFX generation"}

    try:
        result = el_client.text_to_sound_effects.convert(
            text=description,
            duration_seconds=5.0,
        )

        output_path = os.path.join(tempfile.gettempdir(), f"sfx_{check_id}.mp3")
        with open(output_path, "wb") as f:
            for chunk in result:
                f.write(chunk)

        return {"output_path": output_path, "operation": "sfx_replace"}

    except Exception as e:
        return {"error": f"SFX generation failed: {e}"}


def _rewrite_text(input_path: str, compliance_result: dict, mode: str = "phrase") -> dict:
    """Rewrite text content using Gemini.

    Modes:
      - phrase: Fix only the flagged phrases (minimal change)
      - full: Rewrite the entire text preserving tone
      - new: Generate completely new copy from the brief
    """
    from google.genai import types as genai_types

    if not gemini:
        return {"error": "Gemini unavailable for text rewrite"}

    # Read original text
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            original_text = f.read()
    except Exception:
        original_text = compliance_result.get("text_input", "")

    if not original_text:
        return {"error": "No text content to rewrite"}

    violations = compliance_result.get("high_risk_indicator", [])
    suggestion = compliance_result.get("suggestion", "")

    mode_instructions = {
        "phrase": "Fix ONLY the specific flagged phrases. Keep everything else identical. Minimal change.",
        "full": "Rewrite the entire text to be compliant, but preserve the same tone, style, and language.",
        "new": "Generate completely new compliant advertising copy that achieves the same marketing goal.",
    }

    prompt = (
        f"You are fixing advertising copy for compliance.\n\n"
        f"Mode: {mode_instructions[mode]}\n\n"
        f"ORIGINAL TEXT:\n{original_text}\n\n"
        f"VIOLATIONS:\n{json.dumps(violations)}\n\n"
        f"SUGGESTION: {suggestion}\n\n"
        f"Return ONLY JSON: {{\"rewritten_text\": \"...\", \"changes_made\": [\"...\", ...]}}"
    )

    try:
        response = gemini.models.generate_content(
            model=MODEL_TEXT,
            contents=prompt,
            config=genai_types.GenerateContentConfig(response_mime_type="application/json"),
        )
        result = json.loads(response.text)
        rewritten = result.get("rewritten_text", original_text)

        output_path = os.path.join(tempfile.gettempdir(), f"rewrite_{mode}_{os.path.basename(input_path)}")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(rewritten)

        return {"output_path": output_path, "operation": f"text_{mode}", "rewritten_text": rewritten}

    except Exception as e:
        return {"error": f"Text rewrite ({mode}) failed: {e}"}


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _get_extension(media_type: str, url: str) -> str:
    """Get file extension based on media type or URL."""
    ext_map = {"video": ".mp4", "image": ".png", "audio": ".mp3", "text": ".txt"}

    # Try from URL first
    if url:
        for ext in (".mp4", ".png", ".jpg", ".jpeg", ".mp3", ".wav", ".txt"):
            if ext in url.lower():
                return ext

    return ext_map.get(media_type, ".bin")


def _cleanup_temp(*paths: str) -> None:
    """Remove temp files, ignoring errors."""
    for path in paths:
        if path and os.path.exists(path) and tempfile.gettempdir() in path:
            try:
                os.remove(path)
            except OSError:
                pass


def _execute_omni_video_edit(input_path: str, instruction: str, additional_references: Optional[list[str]] = None) -> dict:
    """Execute video-to-video editing via Gemini Omni Flash Preview REST API, supporting both video and image references."""
    import base64
    import tempfile
    import requests
    import google.auth
    import google.auth.transport.requests
    from shared.config import VERTEX_PROJECT_ID, MODEL_VIDEO

    try:
        credentials, project_id = google.auth.default()
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)
        token = credentials.token
        proj_id = VERTEX_PROJECT_ID or project_id
        if not token or not proj_id:
            return {"error": "Failed to authenticate with Vertex AI"}

        # Build multi-modal inputs
        inputs = []

        # 1. Primary Video
        with open(input_path, "rb") as f:
            video_bytes = f.read()
        video_b64 = base64.b64encode(video_bytes).decode("utf-8")
        inputs.append({"type": "video", "data": video_b64, "mime_type": "video/mp4"})

        # 2. Optional additional image/video references
        if additional_references:
            for ref_path in additional_references:
                if ref_path and os.path.exists(ref_path):
                    with open(ref_path, "rb") as f:
                        ref_bytes = f.read()
                    ref_b64 = base64.b64encode(ref_bytes).decode("utf-8")
                    ext = os.path.splitext(ref_path)[1].lower()
                    if ext in (".png", ".jpg", ".jpeg"):
                        mime = f"image/{ext[1:] if ext != '.jpg' else 'jpeg'}"
                        inputs.append({"type": "image", "data": ref_b64, "mime_type": mime})
                        logger.info("[Executor] Appended image reference: %s", ref_path)
                    elif ext in (".mp4", ".mov", ".avi"):
                        inputs.append({"type": "video", "data": ref_b64, "mime_type": "video/mp4"})
                        logger.info("[Executor] Appended video reference: %s", ref_path)

        # 3. Instruction
        inputs.append({"type": "text", "text": instruction})

        request_body = {
            "model": MODEL_VIDEO or "gemini-omni-flash-preview",
            "input": inputs
        }

        url = f"https://aiplatform.googleapis.com/v1beta1/projects/{proj_id}/locations/global/interactions"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        }

        logger.info("[Executor] Sending video edit request to Omni interactions endpoint...")
        response = requests.post(url, json=request_body, headers=headers)
        if response.status_code != 200:
            return {"error": f"Interactions API returned status {response.status_code}: {response.text}"}

        res_json = response.json()

        # Parse the video from steps
        steps = res_json.get("steps", [])
        for step in steps:
            content_list = step.get("content", [])
            for content in content_list:
                if content.get("type") == "video" and "data" in content:
                    out_bytes = base64.b64decode(content["data"])
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
                    tmp.write(out_bytes)
                    tmp.close()
                    logger.info("[Executor] Omni video edit successful. Saved to %s", tmp.name)
                    return {"output_path": tmp.name, "operation": "omni_video_edit"}

        return {"error": "No video was returned by the Omni model"}

    except Exception as e:
        logger.error("[Executor] Omni video edit crashed: %s", e)
        return {"error": f"Omni video edit failed: {e}"}

def _execute_veo_regenerate(instruction: str, compliance_result: dict) -> dict:
    """Regenerate a full video using Gemini Omni (MODEL_VIDEO) as the engine."""
    from google.genai import types as genai_types
    from shared.clients import gemini
    from shared.config import MODEL_VIDEO
    import uuid
    import tempfile

    suggestion = compliance_result.get("suggestion", "")
    original_text = compliance_result.get("text_input", "") or compliance_result.get("original_text", "")

    prompt = (
        f"Generate a brand new compliant commercial video ad. "
        f"Original requirements: {original_text}. "
        f"Remediation guidelines: {instruction or suggestion}. "
        f"Output video should be safe, compliant, and fit the target market."
    )

    try:
        logger.info("[Executor] Submitting full video regeneration request: model=%s", MODEL_VIDEO)
        response = gemini.models.generate_content(
            model=MODEL_VIDEO,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                temperature=1,
                top_p=0.95,
                max_output_tokens=32768,
                response_modalities=["VIDEO", "AUDIO"],
                safety_settings=[
                    genai_types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
                    genai_types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
                    genai_types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
                    genai_types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
                ],
            ),
        )

        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if (
                    hasattr(part, "inline_data")
                    and part.inline_data
                    and part.inline_data.data
                    and "video" in (part.inline_data.mime_type or "")
                ):
                    out_bytes = part.inline_data.data
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
                    tmp.write(out_bytes)
                    tmp.close()
                    logger.info("[Executor] Veo video regeneration successful. Saved to %s", tmp.name)
                    return {"output_path": tmp.name, "operation": "veo_regenerate"}

        return {"error": "Gemini Omni returned no video data for regeneration"}

    except Exception as e:
        logger.error("[Executor] Veo video regeneration failed: %s", e)
        return {"error": f"Veo video regeneration failed: {e}"}
