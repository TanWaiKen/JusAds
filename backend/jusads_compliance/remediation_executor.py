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
import base64
import mimetypes
import os
import subprocess
import tempfile
import urllib.request
import uuid
from typing import Optional

from shared.clients import supabase, gemini
from shared.s3_client import upload_file_public, build_s3_key
from shared.config import MODEL_TEXT
from jusads_compliance.tool_router import RoutingDecision, ToolSelection

logger = logging.getLogger(__name__)


def _get_media_duration(path: str) -> float:
    """Read video duration for Omni's 10-second edit limit."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=10,
        )
        return float(result.stdout.strip()) if result.returncode == 0 else 0.0
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return 0.0


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
        # Local execution uses the same concrete inpainting implementation.
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
    """Inpaint an image with the configured Gemini image model."""
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
                from jusads_compliance.remix_tools import _native_image_bytes
                native_prompt = (
                    f"Edit the first reference image. {prompt} "
                    "The second reference image is a binary mask: modify only white areas and preserve black areas. "
                    "Return one compliant advertising image with no explanatory text."
                )
                with open(output_path, "wb") as output_file:
                    output_file.write(_native_image_bytes(native_prompt, [(image_bytes, "image/png"), (mask_bytes, "image/png")]))
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
    """Edit a <=10s source clip through Vertex Agent Platform Interactions.

    Omni is accessed through the Vertex OAuth endpoint, not the Gemini Developer
    API.  The source and URI-delivered result are temporary GCS objects; only
    the caller's final asset is persisted to S3.
    """
    from google.auth import default
    from google.auth.transport.requests import Request
    import requests
    from shared.config import MODEL_VIDEO, VERTEX_GCS_BUCKET, VERTEX_PROJECT_ID

    duration = _get_media_duration(input_path)
    if not duration:
        return {"error": "Could not determine source video duration for Omni edit."}
    if duration > 10.05:
        return {"error": "Gemini Omni accepts clips up to 10 seconds; extract an affected timeline window first."}
    if not VERTEX_PROJECT_ID or not VERTEX_GCS_BUCKET:
        return {"error": "VERTEX_PROJECT_ID and VERTEX_GCS_BUCKET must be configured for Omni editing."}

    request_id = uuid.uuid4().hex
    input_object = f"jusads-compliance/omni-temp/{request_id}/source.mp4"
    output_prefix = f"jusads-compliance/omni-temp/{request_id}/output/"
    input_uri = f"gs://{VERTEX_GCS_BUCKET}/{input_object}"
    output_uri = f"gs://{VERTEX_GCS_BUCKET}/{output_prefix}"
    mime_type = mimetypes.guess_type(input_path)[0] or "video/mp4"
    headers: Optional[dict[str, str]] = None

    try:
        credentials, _ = default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        credentials.refresh(Request())
        headers = {"Authorization": f"Bearer {credentials.token}"}

        upload_url = (
            f"https://storage.googleapis.com/upload/storage/v1/b/{VERTEX_GCS_BUCKET}/o"
            f"?uploadType=media&name={input_object}"
        )
        with open(input_path, "rb") as source:
            upload_response = requests.post(
                upload_url,
                headers={**headers, "Content-Type": mime_type},
                data=source,
                timeout=120,
            )
        upload_response.raise_for_status()

        # The video itself is the reference.  The prompt explicitly constrains
        # Omni to edit it rather than create a different advertisement.
        payload = {
            "model": MODEL_VIDEO,
            "input": [
                {"type": "text", "text": (
                    "Edit the supplied reference video; do not create a new or unrelated video. "
                    "Preserve product, framing, camera movement, timing, and audio unless the "
                    f"instruction requires a change. {instruction}"
                )},
                {"type": "video", "uri": input_uri, "mime_type": mime_type},
            ],
            "response_format": [{
                "type": "video",
                "delivery": "uri",
                "gcs_uri": output_uri,
                "duration": f"{max(3, min(10, round(duration)))}s",
            }],
        }
        interaction_url = (
            "https://aiplatform.googleapis.com/v1beta1/"
            f"projects/{VERTEX_PROJECT_ID}/locations/global/interactions"
        )
        logger.info("[Executor] Submitting %ss reference edit to Gemini Omni.", round(duration, 2))
        interaction_response = requests.post(
            interaction_url,
            headers={**headers, "Content-Type": "application/json; charset=utf-8"},
            json=payload,
            timeout=300,
        )
        if not interaction_response.ok:
            # Keep the provider's schema/validation detail visible to the SSE
            # caller; a bare HTTP 400 is not actionable for a user or developer.
            return {
                "error": (
                    f"Vertex Omni request failed ({interaction_response.status_code}): "
                    f"{interaction_response.text[:2000]}"
                )
            }
        interaction = interaction_response.json()

        output_video = next(
            (
                content for step in interaction.get("steps", [])
                for content in step.get("content", [])
                if content.get("type") == "video"
            ),
            None,
        )
        if not output_video:
            return {"error": "Gemini Omni completed without a video output.", "interaction_id": interaction.get("id")}

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        try:
            if output_video.get("data"):
                tmp.write(base64.b64decode(output_video["data"]))
            elif output_video.get("uri", "").startswith("gs://"):
                _, _, path = output_video["uri"].partition("gs://")
                bucket, _, object_name = path.partition("/")
                download = requests.get(
                    f"https://storage.googleapis.com/storage/v1/b/{bucket}/o/{requests.utils.quote(object_name, safe='')}?alt=media",
                    headers=headers,
                    timeout=180,
                )
                download.raise_for_status()
                tmp.write(download.content)
            else:
                return {"error": "Gemini Omni returned an unsupported output location.", "interaction_id": interaction.get("id")}
        finally:
            tmp.close()
        return {
            "output_path": tmp.name,
            "operation": "omni_video_edit",
            "interaction_id": interaction.get("id"),
            "source_uri": input_uri,
        }
    except Exception as e:
        logger.error("[Executor] Omni video edit failed: %s", e)
        return {"error": f"Omni video edit failed: {e}"}
    finally:
        # The caller persists only the final S3 asset.  The Vertex input and
        # response objects are short-lived transport files and must not become
        # an unbounded second media store.
        if headers:
            try:
                import requests
                from urllib.parse import quote

                objects = [input_object]
                listed = requests.get(
                    f"https://storage.googleapis.com/storage/v1/b/{VERTEX_GCS_BUCKET}/o",
                    headers=headers,
                    params={"prefix": output_prefix},
                    timeout=30,
                )
                if listed.ok:
                    objects.extend(item["name"] for item in listed.json().get("items", []))
                for object_name in objects:
                    requests.delete(
                        f"https://storage.googleapis.com/storage/v1/b/{VERTEX_GCS_BUCKET}/o/{quote(object_name, safe='')}",
                        headers=headers,
                        timeout=30,
                    )
            except Exception as cleanup_error:
                logger.warning("[Executor] Could not clean temporary Omni GCS objects: %s", cleanup_error)

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
