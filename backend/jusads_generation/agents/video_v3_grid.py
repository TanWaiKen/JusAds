"""
video_v3_grid.py
────────────────
Video Agent V3 — Character Grid Pipeline with staged human approval.

Multi-stage pipeline (each stage returns results for user review):

  Stage 1: plan_script()
    → Director plans scenes, character, transitions
    → Returns: script plan (scenes + character summary)
    → User reviews the plan, can edit subtitles/scenes

  Stage 2: generate_assets()
    → Character Sheet (Imagen 4) + Scene Grid (Imagen 4) + Grid Slice (PIL)
    → Returns: character_sheet_url, grid_url, frame_urls[]
    → User reviews the visuals, confirms character looks right

  Stage 3: execute_production()
    → Gemini Omni full-clip generation + AI Editor + Assembler (FFmpeg + CapCut)
    → Returns: final_video_url, capcut_draft info
    → User gets instant .mp4 + editable CapCut project

Each stage is called separately via the orchestrator/route.
Pipeline state is persisted between stages so user can leave and come back.

Uses Gemini Omni (MODEL_VIDEO) for full video clip generation from scene
prompts with reference frames for character consistency.
for smooth inter-scene character-consistent motion.
"""

import asyncio
import base64
import json
import logging
import math
import mimetypes
import os
import tempfile
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Optional
from urllib.parse import quote

import requests
from google.auth import default as google_auth_default
from google.auth.transport.requests import Request as GoogleAuthRequest

from shared.clients import gemini, supabase
from shared.config import (
    MODEL_IMAGE_CREATIVE,
    MODEL_TEXT,
    MODEL_VIDEO,
    VERTEX_GCS_BUCKET,
    VERTEX_LOCATION,
    VERTEX_PROJECT_ID,
    get_voice,
)
from shared.elevenlabs_utils import generate_tts
from shared.prompts import VIDEO_DIRECTOR_PROMPT
from shared.prompts import _load_prompt as _load_prompt_file
from shared.s3_client import upload_file_public
from config import S3_BUCKET_NAME

logger = logging.getLogger(__name__)


# --- Prompt Templates ---------------------------------------------------------

CHARACTER_SHEET_PROMPT = _load_prompt_file("character_setting.md")
SCENE_GRID_PROMPT = _load_prompt_file("scene_grid.md")

# --- Constants ----------------------------------------------------------------

_SCENE_CLIP_SECONDS = 5
_MAX_OMNI_SEGMENT_SECONDS = 10
_MAX_PLAN_DURATION_SECONDS = 60


def _normalise_plan_duration(video_duration_sec: float) -> int:
    """Return a bounded plan duration rounded up to a five-second scene boundary."""
    bounded_duration = min(max(float(video_duration_sec), _SCENE_CLIP_SECONDS), _MAX_PLAN_DURATION_SECONDS)
    return int(math.ceil(bounded_duration / _SCENE_CLIP_SECONDS) * _SCENE_CLIP_SECONDS)


def _resolve_scene_count(video_duration_sec: float) -> int:
    """Return N+1 visual frames for five-second scenes covering the requested duration."""
    scene_count = _normalise_plan_duration(video_duration_sec) // _SCENE_CLIP_SECONDS
    return scene_count + 1


def _normalise_scenes(raw_scenes: list[dict[str, Any]], scene_count: int, brief: str) -> list[dict[str, Any]]:
    """Enforce the approved five-second scene contract on Director output."""
    scenes = [dict(scene) for scene in raw_scenes[:scene_count] if isinstance(scene, dict)]
    if not scenes:
        scenes = [{"visual_description": brief, "subtitle": "", "voiceover": "", "camera_angle": "MS static"}]

    while len(scenes) < scene_count:
        fallback = dict(scenes[-1])
        fallback["visual_description"] = fallback.get("visual_description") or brief
        fallback["subtitle"] = fallback.get("subtitle", "")
        fallback["voiceover"] = fallback.get("voiceover", "")
        scenes.append(fallback)

    for index, scene in enumerate(scenes, start=1):
        scene["scene_index"] = index
        scene["duration"] = _SCENE_CLIP_SECONDS
    return scenes


def _group_scenes_for_omni(scenes: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Group one or two five-second scenes into provider-safe five or ten-second segments."""
    return [scenes[index:index + 2] for index in range(0, len(scenes), 2)]


def _grid_dimensions(frame_count: int) -> tuple[int, int]:
    """Calculate grid layout (cols x rows)."""
    cols = math.ceil(math.sqrt(frame_count))
    rows = math.ceil(frame_count / cols)
    return cols, rows


def _sse(data: dict) -> str:
    """Format SSE data line."""
    return f"data: {json.dumps(data)}\n\n"


def _load_reference_image_parts(reference_urls: list[str]) -> list:
    """Download user references as Gemini image parts for V3 visual stages."""
    if not reference_urls:
        return []
    import urllib.request
    from google.genai import types as genai_types

    parts: list = []
    for reference_url in reference_urls[:4]:
        try:
            with urllib.request.urlopen(reference_url, timeout=20) as response:
                image_bytes = response.read()
                mime_type = response.headers.get_content_type() or "image/jpeg"
            if image_bytes and mime_type.startswith("image/"):
                parts.append(genai_types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
        except Exception as exc:
            logger.warning("[V3Grid] Could not load reference %s: %s", reference_url[:80], exc)
    return parts


def _generate_reference_anchored_image(
    prompt: str,
    *,
    aspect_ratio: str,
    reference_parts: list,
    filename: str,
) -> Optional[str]:
    """Generate a V3 visual with user references as multimodal input."""
    try:
        from google.genai import types as genai_types

        contents: list = []
        if reference_parts:
            contents.append(
                "The following uploaded images are mandatory visual references. "
                "Preserve the depicted character identity, product appearance, wardrobe, "
                "and brand details whenever relevant. Do not substitute a different person or product."
            )
            contents.extend(reference_parts)
        contents.append(prompt)
        response = gemini.models.generate_content(
            model=MODEL_IMAGE_CREATIVE,
            contents=contents,
            config=genai_types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
                image_config=genai_types.ImageConfig(
                    aspect_ratio=aspect_ratio,
                    output_mime_type="image/png",
                ),
            ),
        )
        for part in response.candidates[0].content.parts if response.candidates else []:
            if getattr(part, "inline_data", None) and part.inline_data.data:
                output_path = os.path.join(tempfile.gettempdir(), filename)
                with open(output_path, "wb") as output:
                    output.write(part.inline_data.data)
                return output_path
    except Exception as exc:
        logger.error("[V3Grid] Native image generation failed: %s", exc)
    return None


def _persist_ad(
    project_id: str,
    task_id: str,
    media_type: str,
    s3_url: str,
    prompt_used: str,
    label: str = "",
    asset_role: str = "output",
) -> Optional[str]:
    """Persist a V3 artifact while separating user-facing outputs from internal media."""
    if not supabase or not s3_url:
        return None
    try:
        ad_id = str(uuid.uuid4())
        supabase.table("generated_ads").insert({
            "id": ad_id,
            "project_id": project_id,
            "task_id": task_id,
            "media_type": media_type,
            "platform": "tiktok",
            "status": "completed",
            "asset_role": asset_role,
            "s3_media_key": s3_url,
            "metadata": {"s3_url": s3_url, "label": label, "pipeline": "v3_grid"},
            "prompt_used": prompt_used[:500],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
        logger.info("[V3Grid] Persisted: %s (%s)", label, ad_id[:8])
        return ad_id
    except Exception as e:
        logger.warning("[V3Grid] Persist failed for '%s': %s", label, e)
        return None


# ==============================================================================
# STAGE 1: Script Planning (Director)
# Returns the plan for user review. User can edit before proceeding.
# ==============================================================================

_DIRECTOR_PROMPT = VIDEO_DIRECTOR_PROMPT


async def plan_script(
    brief: str,
    video_duration_sec: float = 15.0,
    target_ethnicity: str = "all",
    product_description: str = "",
    market: str = "malaysia",
) -> dict:
    """Stage 1: Director plans the full script.

    Returns a plan dict that the frontend shows for user review.
    The user can edit subtitles, reorder scenes, or approve as-is.

    Returns:
        {
            "plan_id": "...",
            "character_summary": "...",
            "product_integration": "...",
            "scenes": [...],
            "frame_count": N + 1,
            "grid_layout": "3x2",
            "clip_count": N,
            "duration_sec": N * 5,
        }
    """
    plan_id = uuid.uuid4().hex[:8]
    planned_duration = _normalise_plan_duration(video_duration_sec)
    scene_count = planned_duration // _SCENE_CLIP_SECONDS
    frame_count = _resolve_scene_count(planned_duration)
    cols, rows = _grid_dimensions(frame_count)

    prompt = _DIRECTOR_PROMPT.format(
        clip_count=scene_count,
        duration=planned_duration,
        clip_seconds=_SCENE_CLIP_SECONDS,
        brief=brief,
        ethnicity=target_ethnicity,
        market=market,
    )
    if product_description:
        prompt += f"\n\nProduct: {product_description}"

    try:
        from google.genai import types as genai_types
        # Attempt to use MODEL_TEXT with a thinking budget for higher quality reasoning
        try:
            config = genai_types.GenerateContentConfig(
                response_mime_type="application/json",
                thinking_config=genai_types.ThinkingConfig(thinking_budget=2048),
            )
            response = gemini.models.generate_content(
                model=MODEL_TEXT,
                contents=prompt,
                config=config,
            )
        except Exception as exc_thinking:
            logger.warning("[V3Grid] Planning with thinking model failed: %s. Falling back to default model.", exc_thinking)
            config = genai_types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3,
            )
            response = gemini.models.generate_content(
                model=MODEL_TEXT,
                contents=prompt,
                config=config,
            )

        result = json.loads(response.text)
        if "scenes" in result and isinstance(result["scenes"], list):
            scenes = _normalise_scenes(result["scenes"], scene_count, brief)
            logger.info("[V3Grid] Director planned %d fixed-%ss scenes", len(scenes), _SCENE_CLIP_SECONDS)
            return {
                "plan_id": plan_id,
                "character_summary": result.get("character_summary", brief),
                "skip_character_creation": bool(result.get("skip_character_creation", False)),
                "product_integration": result.get("product_integration", product_description or brief),
                "visual_style": result.get("visual_style", "cinematic warm-toned photography"),
                "scenes": scenes,
                "frame_count": frame_count,
                "grid_layout": f"{cols}x{rows}",
                "clip_count": scene_count,
                "duration_sec": planned_duration,
                "market": market,
            }
    except Exception as e:
        logger.error("[V3Grid] Director planning failed: %s", e)

    # Fallback
    fallback_scenes = _normalise_scenes(
        [
            {"scene_index": i + 1, "visual_description": brief, "camera_angle": "MS static",
             "character_action": "presenting", "character_requirements": "",
             "subtitle": f"Scene {i + 1}", "voiceover": "", "transition_to_next": "crossfade"}
            for i in range(scene_count)
        ],
        scene_count,
        brief,
    )
    return {
        "plan_id": plan_id,
        "character_summary": brief,
        "skip_character_creation": False,
        "product_integration": product_description or brief,
        "visual_style": "cinematic warm-toned photography, consistent lighting",
        "scenes": fallback_scenes,
        "frame_count": frame_count,
        "grid_layout": f"{cols}x{rows}",
        "clip_count": scene_count,
        "duration_sec": planned_duration,
        "market": market,
    }


# ==============================================================================
# STAGE 2: Generate Assets (Character Sheet + Scene Grid + Slice)
# Returns images for user review before expensive video generation step.
# ==============================================================================


async def generate_assets(
    plan: dict,
    project_id: str,
    task_id: str,
    reference_image_urls: Optional[list[str]] = None,
) -> AsyncGenerator[str, None]:
    """Stage 2: Generate character sheet + scene grid + slice into frames.

    Takes the approved plan from Stage 1 and generates the visual assets.
    Streams SSE events for real-time progress. Results are persisted as
    generated_ads so they appear in the Output Gallery.

    Yields SSE events. Final event contains the asset URLs.
    """
    plan_id = plan.get("plan_id", uuid.uuid4().hex[:8])
    char_summary = plan.get("character_summary", "")
    product_integration = plan.get("product_integration", "")
    visual_style = plan.get("visual_style", "cinematic warm-toned photography, consistent lighting")
    scenes = plan.get("scenes", [])
    frame_count = plan.get("frame_count", len(scenes) + 1)
    cols, rows = _grid_dimensions(frame_count)
    reference_image_urls = reference_image_urls or []
    reference_parts = _load_reference_image_parts(reference_image_urls)
    if reference_image_urls:
        yield _sse({"node": "references", "status": "completed", "data": {
            "urls": reference_image_urls,
            "loaded_count": len(reference_parts),
        }})

    skip_char = bool(plan.get("skip_character_creation", False))

    if not skip_char:
        yield _sse({"node": "character_sheet", "status": "in-progress", "data": {"message": "Generating character reference sheet..."}})

        # -- Character Sheet ---------------------------------------------------
        char_sheet_url = None
        path = None
        try:
            char_prompt = CHARACTER_SHEET_PROMPT.replace(
                "[INSERT CHARACTER APPEARANCE DESCRIPTION HERE]", char_summary,
            )
            char_prompt += f"\n\nVISUAL STYLE (mandatory): {visual_style}. All panels must use this exact style."
            char_prompt += "\n\nIMPORTANT: Generate PHOTOREALISTIC humans. This is for a REAL advertising campaign — NOT anime, NOT illustration, NOT cartoon. Use professional photography style with natural skin, real clothing textures, and cinematic lighting. The character must look like a real person suitable for a commercial advertisement."
            path = _generate_reference_anchored_image(
                char_prompt,
                aspect_ratio="16:9",
                reference_parts=reference_parts,
                filename=f"char_{plan_id}.png",
            )
            if path:
                s3_key = f"generated_ads/{project_id}/{task_id}/v3/{plan_id}/character_sheet.png"
                char_sheet_url = upload_file_public(path, s3_key)
                _persist_ad(project_id, task_id, "image", char_sheet_url, f"Character Sheet: {char_summary[:80]}", "Character Sheet")

                # Also store at project level for reuse across tasks
                project_char_key = f"generated_ads/{project_id}/character_sheet_latest.png"
                try:
                    upload_file_public(path, project_char_key)
                    logger.info("[V3Grid] Character sheet also saved at project level for reuse")
                except Exception:
                    pass
        except Exception as e:
            logger.error("[V3Grid] Character sheet failed: %s", e)

        yield _sse({"node": "character_sheet", "status": "completed" if char_sheet_url else "failed", "data": {"url": char_sheet_url}})
    else:
        char_sheet_url = None
        path = None
        logger.info("[V3Grid] Skipping character sheet generation based on plan")
        yield _sse({"node": "character_sheet", "status": "completed", "data": {"url": None, "message": "Skipped (No character needed)"}})

    # -- Scene Grid (uses character sheet as reference image if generated) -------------
    yield _sse({"node": "scene_grid", "status": "in-progress", "data": {"message": f"Generating {cols}x{rows} scene grid..."}})

    grid_url = None
    grid_path = None
    try:
        scene_descriptions = "\n".join(
            f"Panel {i+1}: {s.get('camera_angle', 'MS')} — {s.get('visual_description', '')[:60]}"
            for i, s in enumerate(scenes)
        )
        scene_descriptions += f"\nPanel {len(scenes)+1}: Final CTA pose"

        grid_prompt = SCENE_GRID_PROMPT.replace("[num]", str(frame_count))
        grid_prompt = grid_prompt.replace(
            "[Insert Product Integration Details Here]",
            f"Product: {product_integration}\n\nPanels:\n{scene_descriptions}",
        )
        if not skip_char:
            grid_prompt += f"\n\nCharacter (MUST match the uploaded reference): {char_summary}"
            grid_prompt += f"\n\nREFERENCE IMAGE: The uploaded image is the character sheet. Each panel must show the EXACT same character with the SAME face, body, clothing, and style. Do NOT create different characters."
        
        grid_prompt += f"\n\nVISUAL STYLE (mandatory): {visual_style}. Every panel must match this exact style."

        grid_reference_parts = list(reference_parts)
        if path and os.path.exists(path):
            from google.genai import types as genai_types
            with open(path, "rb") as character_file:
                grid_reference_parts.append(
                    genai_types.Part.from_bytes(data=character_file.read(), mime_type="image/png")
                )
        grid_path = _generate_reference_anchored_image(
            grid_prompt,
            aspect_ratio="1:1",
            reference_parts=grid_reference_parts,
            filename=f"grid_{plan_id}.png",
        )
        if grid_path:
            s3_key = f"generated_ads/{project_id}/{task_id}/v3/{plan_id}/scene_grid.png"
            grid_url = upload_file_public(grid_path, s3_key)
            _persist_ad(project_id, task_id, "image", grid_url, f"Scene Grid ({cols}x{rows})", "Scene Grid")
    except Exception as e:
        logger.error("[V3Grid] Scene grid failed: %s", e)

    yield _sse({"node": "scene_grid", "status": "completed" if grid_url else "failed", "data": {"url": grid_url}})

    if not grid_path or not grid_url:
        yield _sse({"error": "Scene grid generation failed — cannot proceed"})
        return

    # -- Grid Slice --------------------------------------------------------
    yield _sse({"node": "grid_slicer", "status": "in-progress", "data": {"message": f"Slicing into {frame_count} frames..."}})

    try:
        frame_paths = _slice_grid(grid_path, cols, rows, frame_count, plan_id)
        frame_urls = []
        for i, fp in enumerate(frame_paths):
            s3_key = f"generated_ads/{project_id}/{task_id}/v3/{plan_id}/frame_{i:02d}.png"
            url = upload_file_public(fp, s3_key)
            frame_urls.append(url)
    except Exception as e:
        logger.error("[V3Grid] Grid slice failed: %s", e)
        yield _sse({"node": "grid_slicer", "status": "failed", "data": {"error": str(e)}})
        return

    yield _sse({"node": "grid_slicer", "status": "completed", "data": {"frame_count": len(frame_urls), "frame_urls": frame_urls}})

    # Return the final asset package for user review
    yield _sse({"v3_assets": {
        "plan_id": plan_id,
        "character_sheet_url": char_sheet_url,
        "grid_url": grid_url,
        "frame_urls": frame_urls,
        "frame_count": len(frame_urls),
        "clip_count": len(frame_urls) - 1,
        "scenes": scenes,
    }})


# ==============================================================================
# STAGE 3: Execute Production (Gemini Omni + Edit + Assemble)
# Only runs after user approves the assets from Stage 2.
# ==============================================================================


def _build_omni_segment_prompt(
    scenes: list[dict[str, Any]],
    *,
    aspect_ratio: str,
    segment_duration: int,
    is_final_segment: bool,
) -> str:
    """Build a time-coded Omni prompt for one provider-safe V3 video segment."""
    timeline: list[str] = []
    elapsed_seconds = 0
    for position, scene in enumerate(scenes):
        scene_duration = int(scene.get("duration", _SCENE_CLIP_SECONDS))
        end_seconds = elapsed_seconds + scene_duration
        description = scene.get("visual_description") or scene.get("description") or "Continue the approved commercial story."
        camera = scene.get("camera_angle") or scene.get("camera_movement") or "cinematic camera movement"
        action = scene.get("character_action") or scene.get("character_requirements") or ""
        subtitle = scene.get("subtitle") or ""
        timeline.append(
            f"[{elapsed_seconds}-{end_seconds}s] {description} Camera: {camera}. Action: {action}. "
            f"On-screen text: {subtitle or 'none'}."
        )
        elapsed_seconds = end_seconds

    final_constraint = ""
    if is_final_segment:
        final_constraint = (
            " In the final 1-2 seconds, show the exact supplied product package and approved brand logo "
            "clearly but naturally. Preserve package text and do not invent claims, certifications, prices, or features."
        )

    return (
        f"Create one continuous {segment_duration}-second {aspect_ratio} commercial-video segment. "
        "The input images are ordered: the first is <FIRST_FRAME>; remaining images are <IMAGE_REF_N> continuity, "
        "brand, product, and ending-frame references. Begin from <FIRST_FRAME>, maintain the exact supplied product "
        "and brand identity, and use the following timed direction: "
        + " ".join(timeline)
        + " Keep people, wardrobe, setting, lighting, and product appearance consistent. "
        "Use natural motion, no scene beyond the listed timing, and no unrequested text or spoken dialogue."
        + final_constraint
    )


async def execute_production(
    assets: dict,
    project_id: str,
    task_id: str,
    brief: str = "",
) -> AsyncGenerator[str, None]:
    """Render approved fixed-five-second scenes through Interactions and assemble their segments."""
    plan_id = assets.get("plan_id", uuid.uuid4().hex[:8])
    raw_scenes = [scene for scene in assets.get("scenes", []) if isinstance(scene, dict)]
    if not raw_scenes:
        yield _sse({"error": "No approved V3 scenes found — regenerate the storyboard first"})
        return

    scenes = _normalise_scenes(raw_scenes, len(raw_scenes), brief)
    scene_segments = _group_scenes_for_omni(scenes)
    frame_urls = [url for url in assets.get("frame_urls", []) if isinstance(url, str) and url]
    reference_image_urls = [url for url in assets.get("reference_image_urls", []) if isinstance(url, str) and url][:4]
    local_frames: list[str] = []
    local_references: list[str] = []
    scene_clips: list[str] = []
    segment_metadata: list[dict[str, Any]] = []
    aspect_ratio = assets.get("aspect_ratio", "9:16")

    # The sliced frames are cleaner production references than the annotated
    # full grid: each Omni segment receives its first, middle, and final frame.
    yield _sse({"node": "download_frames", "status": "in-progress", "data": {
        "message": "Downloading scene references for Gemini Omni...",
    }})
    for index, frame_url in enumerate(frame_urls):
        try:
            path = os.path.join(tempfile.gettempdir(), f"dl_frame_{plan_id}_{index:02d}.png")
            urllib.request.urlretrieve(frame_url, path)
            local_frames.append(path)
        except Exception as exc:
            logger.warning("[V3Grid] Frame download failed for scene %d: %s", index + 1, exc)
    if len(local_frames) < len(scenes) + 1:
        yield _sse({"node": "download_frames", "status": "failed", "data": {
            "error": "The approved scene frames are incomplete. Regenerate the Scene Grid before rendering.",
        }})
        return
    yield _sse({"node": "download_frames", "status": "completed", "data": {"count": len(local_frames)}})

    if reference_image_urls:
        yield _sse({"node": "download_references", "status": "in-progress", "data": {
            "message": "Downloading approved product and brand references...",
        }})
        for index, reference_url in enumerate(reference_image_urls):
            try:
                suffix = Path(reference_url.split("?", 1)[0]).suffix or ".png"
                path = os.path.join(tempfile.gettempdir(), f"dl_ref_{plan_id}_{index:02d}{suffix}")
                urllib.request.urlretrieve(reference_url, path)
                local_references.append(path)
            except Exception as exc:
                logger.warning("[V3Grid] Reference download failed: %s", exc)
        yield _sse({"node": "download_references", "status": "completed", "data": {"count": len(local_references)}})

    yield _sse({"node": "omni_video", "status": "in-progress", "data": {
        "message": f"Rendering {len(scene_segments)} Gemini Omni segment(s), up to 10 seconds each...",
        "segments": len(scene_segments),
    }})

    scene_offset = 0
    for segment_index, segment_scenes in enumerate(scene_segments):
        segment_duration = sum(int(scene["duration"]) for scene in segment_scenes)
        if segment_duration > _MAX_OMNI_SEGMENT_SECONDS:
            yield _sse({"node": "omni_video", "status": "failed", "data": {
                "error": f"Segment {segment_index + 1} exceeds the {_MAX_OMNI_SEGMENT_SECONDS}-second Omni limit.",
            }})
            return

        segment_frames = local_frames[scene_offset:scene_offset + len(segment_scenes) + 1]
        prompt = _build_omni_segment_prompt(
            segment_scenes,
            aspect_ratio=aspect_ratio,
            segment_duration=segment_duration,
            is_final_segment=(
                segment_index == len(scene_segments) - 1
                and bool(assets.get("final_product_reveal", False))
            ),
        )
        yield _sse({"node": "omni_video", "status": "in-progress", "data": {
            "message": f"Submitting segment {segment_index + 1} of {len(scene_segments)} ({segment_duration}s)...",
            "segment_index": segment_index + 1,
            "duration_sec": segment_duration,
        }})
        render_result = await _generate_omni_video_clip(
            prompt=prompt,
            reference_paths=[segment_frames[0], *local_references, *segment_frames[1:]],
            scene_index=segment_index,
            plan_id=plan_id,
            project_id=project_id,
            task_id=task_id,
            aspect_ratio=aspect_ratio,
            duration_sec=segment_duration,
        )
        if not render_result or not render_result.get("url"):
            yield _sse({"node": "omni_video", "status": "failed", "data": {
                "error": (render_result or {}).get(
                    "error", f"Gemini Omni did not return a video for segment {segment_index + 1}."
                ),
                "segment_index": segment_index + 1,
                "interaction_id": (render_result or {}).get("interaction_id", ""),
            }})
            return

        scene_clips.append(render_result["url"])
        segment_metadata.append({
            "scene_index": segment_index + 1,
            "duration": segment_duration,
            "description": " ".join(
                str(scene.get("visual_description") or scene.get("description") or "")
                for scene in segment_scenes
            ),
            "subtitle": segment_scenes[-1].get("subtitle", ""),
            "voiceover": " ".join(
                str(scene.get("voiceover") or scene.get("script") or "")
                for scene in segment_scenes
            ).strip(),
        })
        _persist_ad(
            project_id,
            task_id,
            "video",
            render_result["url"],
            prompt,
            f"Omni segment {segment_index + 1} ({segment_duration}s)",
            asset_role="intermediate",
        )
        yield _sse({"node": "omni_video", "status": "completed", "data": {
            "url": render_result["url"],
            "segment_index": segment_index + 1,
            "duration_sec": segment_duration,
            "interaction_id": render_result["interaction_id"],
        }})
        scene_offset += len(segment_scenes)

    if not scene_clips:
        yield _sse({"error": "Video generation failed — Gemini Omni could not produce any segments"})
        return

    # -- Generate ElevenLabs voiceover narration if selected -----------------
    vo_path = None
    voiceover_type = assets.get("voiceover_type", "elevenlabs")
    
    if voiceover_type == "elevenlabs":
        try:
            # Extract voiceover from scenes
            vo_lines = []
            for scene in scenes:
                line = scene.get("voiceover") or scene.get("script") or ""
                if line:
                    vo_lines.append(line)
            
            combined_vo_text = " ".join(vo_lines).strip()
            if combined_vo_text:
                yield _sse({"node": "elevenlabs_vo", "status": "in-progress", "data": {"message": "Generating ElevenLabs premium voiceover..."}})
                temp_vo_path = os.path.join(tempfile.gettempdir(), f"vo_{plan_id}.mp3")
                
                # Resolve voice using assets config
                market = assets.get("market", "malaysia")
                ethnicity = assets.get("target_ethnicity", "all")
                gender = assets.get("gender", "female")
                
                voice_entry = get_voice(market, ethnicity, gender)
                voice_id = voice_entry["voice_id"]
                lang_code = voice_entry.get("lang", "ms")
                
                logger.info("[V3Grid] Calling ElevenLabs for TTS. Voice ID: %s, Lang: %s", voice_id, lang_code)
                ok = generate_tts(combined_vo_text, temp_vo_path, voice_id=voice_id, language_code=lang_code)
                if ok and os.path.exists(temp_vo_path):
                    vo_path = temp_vo_path
                    logger.info("[V3Grid] ElevenLabs voiceover generated successfully at %s", vo_path)
                    yield _sse({"node": "elevenlabs_vo", "status": "completed", "data": {"message": "Voiceover generated successfully."}})
                else:
                    logger.warning("[V3Grid] ElevenLabs TTS generation failed or returned empty.")
                    yield _sse({"node": "elevenlabs_vo", "status": "failed", "data": {"error": "TTS generation failed."}})
        except Exception as e:
            logger.error("[V3Grid] ElevenLabs TTS setup or run failed: %s", e)
            yield _sse({"node": "elevenlabs_vo", "status": "failed", "data": {"error": str(e)}})
    else:
        logger.info("[V3Grid] Bypassing ElevenLabs TTS — using native Gemini Omni audio only.")

    # -- AI Editor + Assembly ----------------------------------------------
    yield _sse({"node": "assembler", "status": "in-progress", "data": {"message": "AI editing + assembling final video..."}})

    try:
        from .video_assembler import assemble_dual_output

        # Download clips locally for FFmpeg
        local_clips = []
        for i, url in enumerate(scene_clips):
            try:
                path = os.path.join(tempfile.gettempdir(), f"dl_clip_{plan_id}_{i:02d}.mp4")
                urllib.request.urlretrieve(url, path)
                local_clips.append(path)
            except Exception:
                pass

        if local_clips:
            result = await assemble_dual_output(
                scene_clips=local_clips,
                scenes=segment_metadata[:len(local_clips)],
                audio_path=vo_path,
                draft_name=f"v3_{plan_id}",
            )

            mp4_path = result.get("mp4_path")
            final_url = None
            final_ad_id = None
            if mp4_path and os.path.exists(mp4_path):
                s3_key = f"generated_ads/{project_id}/{task_id}/v3/{plan_id}/final_video.mp4"
                final_url = upload_file_public(mp4_path, s3_key)
                final_ad_id = _persist_ad(
                    project_id,
                    task_id,
                    "video",
                    final_url,
                    f"Final V3 Video Ad: {brief[:80]}",
                    "Final Video",
                )

            if not final_url:
                yield _sse({"node": "assembler", "status": "failed", "data": {
                    "error": "The V3 assembler did not produce a final MP4.",
                }})
                return

            yield _sse({"node": "assembler", "status": "completed", "data": {
                "mp4_url": final_url,
                "final_ad_id": final_ad_id,
                "capcut_draft": result.get("capcut_draft"),
                "clips_produced": len(scene_clips),
            }})
        else:
            yield _sse({"node": "assembler", "status": "failed", "data": {"error": "No clips to assemble"}})

    except Exception as e:
        logger.error("[V3Grid] Assembly failed: %s", e)
        yield _sse({"node": "assembler", "status": "failed", "data": {"error": str(e)}})


# --- Helper Functions ---------------------------------------------------------


def _slice_grid(grid_path: str, cols: int, rows: int, total_frames: int, plan_id: str) -> list[str]:
    """Slice grid image into individual frames (left→right, top→bottom)."""
    from PIL import Image

    img = Image.open(grid_path)
    w, h = img.size
    cell_w, cell_h = w // cols, h // rows

    frames = []
    count = 0
    for row in range(rows):
        for col in range(cols):
            if count >= total_frames:
                break
            cell = img.crop((col * cell_w, row * cell_h, (col + 1) * cell_w, (row + 1) * cell_h))
            path = os.path.join(tempfile.gettempdir(), f"frame_{plan_id}_{count:02d}.png")
            cell.save(path, "PNG")
            frames.append(path)
            count += 1

    logger.info("[V3Grid] Sliced %dx%d grid → %d frames (%dx%d each)", cols, rows, len(frames), cell_w, cell_h)
    return frames


async def _generate_omni_video_clip(
    prompt: str,
    reference_paths: list[str],
    scene_index: int,
    plan_id: str,
    project_id: str,
    task_id: str,
    aspect_ratio: str,
    duration_sec: int,
) -> dict[str, str]:
    """Render one fixed five- or ten-second V3 segment with Vertex Interactions.

    Omni creates one moving segment from source/reference images and a timed
    prompt. It is never invoked through ``generate_content`` and does not render
    individual video frames. URI delivery keeps large video bytes out of the
    interaction response and the temporary GCS output is removed after download.
    """
    if duration_sec not in {_SCENE_CLIP_SECONDS, _MAX_OMNI_SEGMENT_SECONDS}:
        return {"error": "V3 Omni segments must be exactly 5 or 10 seconds.", "interaction_id": ""}
    if not VERTEX_PROJECT_ID or not VERTEX_GCS_BUCKET:
        return {"error": "VERTEX_PROJECT_ID and VERTEX_GCS_BUCKET are required for Gemini Omni.", "interaction_id": ""}

    def extract_video_content(interaction: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Return the first video content block from an Interactions response."""
        return next(
            (
                content for step in interaction.get("steps", [])
                for content in step.get("content", [])
                if content.get("type") == "video"
            ),
            None,
        )

    def blocking_omni_call() -> dict[str, str]:
        """Submit and poll one Vertex Interactions request, then upload its clip."""
        headers: Optional[dict[str, str]] = None
        request_id = uuid.uuid4().hex
        output_prefix = f"jusads-generation/omni-temp/{request_id}/output/"
        output_uri = f"gs://{VERTEX_GCS_BUCKET}/{output_prefix}"
        interaction_id = ""
        try:
            inputs: list[dict[str, str]] = []
            for path in reference_paths:
                if not os.path.exists(path):
                    continue
                with open(path, "rb") as reference_file:
                    image_data = base64.b64encode(reference_file.read()).decode("ascii")
                inputs.append({
                    "type": "image",
                    "data": image_data,
                    "mime_type": mimetypes.guess_type(path)[0] or "image/png",
                })
            if not inputs:
                return {"error": f"Omni segment {scene_index + 1} has no usable visual references.", "interaction_id": ""}

            credentials, _ = google_auth_default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
            credentials.refresh(GoogleAuthRequest())
            headers = {"Authorization": f"Bearer {credentials.token}"}
            interaction_url = (
                "https://aiplatform.googleapis.com/v1beta1/"
                f"projects/{VERTEX_PROJECT_ID}/locations/{VERTEX_LOCATION}/interactions"
            )
            payload = {
                "model": MODEL_VIDEO,
                "input": [*inputs, {"type": "text", "text": prompt}],
                "response_format": [{
                    "type": "video",
                    "delivery": "uri",
                    "gcs_uri": output_uri,
                    "duration": f"{duration_sec}s",
                    "aspect_ratio": aspect_ratio,
                }],
            }
            logger.info("[V3Grid] Submitting %ss Omni segment %d through Interactions.", duration_sec, scene_index + 1)
            response = requests.post(
                interaction_url,
                headers={**headers, "Content-Type": "application/json; charset=utf-8"},
                json=payload,
                timeout=300,
            )
            if not response.ok:
                return {
                    "error": f"Vertex Omni request failed ({response.status_code}): {response.text[:2000]}",
                    "interaction_id": "",
                }
            interaction = response.json()
            interaction_id = str(interaction.get("id", ""))

            # The API can return pending work. Poll the interaction while it is
            # running so the worker never mistakes an accepted request for failure.
            deadline = time.monotonic() + 300
            while interaction.get("status") in {"pending", "processing", "in_progress"}:
                if time.monotonic() >= deadline:
                    return {"error": "Gemini Omni interaction timed out while processing.", "interaction_id": interaction_id}
                time.sleep(5)
                poll_response = requests.get(
                    f"{interaction_url}/{quote(interaction_id, safe='')}",
                    headers=headers,
                    timeout=30,
                )
                if not poll_response.ok:
                    return {
                        "error": f"Vertex Omni polling failed ({poll_response.status_code}): {poll_response.text[:2000]}",
                        "interaction_id": interaction_id,
                    }
                interaction = poll_response.json()

            video_content = extract_video_content(interaction)
            if not video_content:
                return {
                    "error": f"Gemini Omni interaction completed without video (status={interaction.get('status', 'unknown')}).",
                    "interaction_id": interaction_id,
                }

            clip_path = os.path.join(tempfile.gettempdir(), f"clip_{plan_id}_{scene_index:02d}.mp4")
            if video_content.get("data"):
                video_bytes = base64.b64decode(video_content["data"])
            elif video_content.get("uri", "").startswith("gs://"):
                _, _, gcs_path = video_content["uri"].partition("gs://")
                bucket, _, object_name = gcs_path.partition("/")
                download = requests.get(
                    f"https://storage.googleapis.com/storage/v1/b/{bucket}/o/{quote(object_name, safe='')}?alt=media",
                    headers=headers,
                    timeout=180,
                )
                download.raise_for_status()
                video_bytes = download.content
            else:
                return {"error": "Gemini Omni returned an unsupported video location.", "interaction_id": interaction_id}

            with open(clip_path, "wb") as clip_file:
                clip_file.write(video_bytes)
            s3_key = f"generated_ads/{project_id}/{task_id}/v3/{plan_id}/clip_{scene_index:02d}.mp4"
            return {"url": upload_file_public(clip_path, s3_key), "interaction_id": interaction_id}
        except Exception as exc:
            error_message = f"Gemini Omni Interactions failed: {exc}"
            logger.error("[V3Grid] %s (segment=%d, interaction=%s)", error_message, scene_index + 1, interaction_id)
            return {"error": error_message, "interaction_id": interaction_id}
        finally:
            if headers:
                try:
                    listed = requests.get(
                        f"https://storage.googleapis.com/storage/v1/b/{VERTEX_GCS_BUCKET}/o",
                        headers=headers,
                        params={"prefix": output_prefix},
                        timeout=30,
                    )
                    for item in listed.json().get("items", []) if listed.ok else []:
                        requests.delete(
                            f"https://storage.googleapis.com/storage/v1/b/{VERTEX_GCS_BUCKET}/o/{quote(item['name'], safe='')}",
                            headers=headers,
                            timeout=30,
                        )
                except Exception as cleanup_error:
                    logger.warning("[V3Grid] Temporary Omni GCS cleanup failed: %s", cleanup_error)

    return await asyncio.to_thread(blocking_omni_call)


async def run_grid_pipeline(
    brief: str,
    project_id: str,
    task_id: str,
    character_description: str = "",
    product_description: str = "",
    reference_image_url: Optional[str] = None,
    reference_image_urls: Optional[list[str]] = None,
    video_duration_sec: float = 15.0,
    width: int = 1080,
    height: int = 1920,
    target_ethnicity: str = "all",
    market: str = "malaysia",
    gender: str = "female",
) -> AsyncGenerator[str, None]:
    """Orchestrator-compatible entry point. Runs Stage 1 + Stage 2 inline.

    Stage 3 (Omni video) is triggered separately when user clicks Continue.
    This function plans the script + generates assets, then emits a v3_plan
    event for the frontend to show (like V2's video_plan).
    """
    # Stage 1: Plan
    yield _sse({"node": "director", "status": "in-progress", "data": {"message": "Director planning script..."}})

    reference_image_urls = list(reference_image_urls or [])
    if reference_image_url and reference_image_url not in reference_image_urls:
        reference_image_urls.insert(0, reference_image_url)

    plan = await plan_script(
        brief=brief,
        video_duration_sec=video_duration_sec,
        target_ethnicity=target_ethnicity,
        product_description=product_description or character_description,
        market=market,
    )
    plan["gender"] = gender
    plan["reference_image_urls"] = reference_image_urls

    yield _sse({"node": "director", "status": "completed", "data": {
        "scene_count": len(plan["scenes"]),
        "character_summary": plan["character_summary"][:100],
    }})

    # Stage 2: Generate assets (capture URLs for pipeline_state)
    async for event in generate_assets(
        plan,
        project_id,
        task_id,
        reference_image_urls=reference_image_urls,
    ):
        yield event
        # Capture asset URLs from the v3_assets event
        try:
            if "v3_assets" in event:
                data = json.loads(event.replace("data: ", "").strip())
                assets_data = data.get("v3_assets", {})
                plan["_char_url"] = assets_data.get("character_sheet_url", "")
                plan["_grid_url"] = assets_data.get("grid_url", "")
                plan["_frame_urls"] = assets_data.get("frame_urls", [])
                plan["frame_urls"] = assets_data.get("frame_urls", [])
        except Exception:
            pass

    # Emit the plan for frontend "Continue" button (same pattern as V2)
    # Add keyframe_url to each scene so the storyboard shows thumbnails
    frame_urls = plan.get("_frame_urls", [])
    enriched_scenes = []
    for i, scene in enumerate(plan.get("scenes", [])):
        enriched = dict(scene)
        enriched["keyframe_url"] = frame_urls[i] if i < len(frame_urls) else ""
        enriched["index"] = i
        enriched_scenes.append(enriched)

    yield _sse({"video_plan": {
        **plan,
        "scenes": enriched_scenes,
        "frame_urls": frame_urls,
        "pipeline_version": "v3_grid",
    }})

    # Emit a proper pipeline_state so the canvas shows V3 nodes (not generic V1 nodes)
    # Also include video_plan inside pipeline_state so it persists across refresh (B3).
    director_script = "\n\n".join(
        "Scene {index} — {duration}\nVisual: {visual}\nVoice-over: {voiceover}\nOn-screen text: {subtitle}".format(
            index=index + 1,
            duration=scene.get("duration", f"~{_SCENE_CLIP_SECONDS}s"),
            visual=scene.get("visual_description", ""),
            voiceover=scene.get("voiceover", ""),
            subtitle=scene.get("subtitle", ""),
        )
        for index, scene in enumerate(plan.get("scenes", []))
    )

    skip_char = bool(plan.get("skip_character_creation", False))

    v3_nodes = []
    if reference_image_urls:
        v3_nodes.append(
            {"id": f"node-references-{plan['plan_id']}", "type": "input", "x": 40, "y": 70,
             "label": f"References ({len(reference_image_urls)})", "status": "done",
             "output": f"{len(reference_image_urls)} visual reference(s)", "error": None,
             "props": {"reference_urls": reference_image_urls}}
        )
    v3_nodes.extend([
        {"id": f"node-director-{plan['plan_id']}", "type": "orchestrator", "x": 180, "y": 200,
         "label": "Director — Script & Storyboard", "status": "done", "output": f"{len(plan['scenes'])} scenes planned", "error": None,
         "props": {"prompt_used": director_script}},
    ])

    if not skip_char:
        v3_nodes.extend([
            {"id": f"node-char-{plan['plan_id']}", "type": "image", "x": 350, "y": 100,
             "label": "Character Sheet", "status": "done", "output": plan.get("_char_url", ""), "error": None, "props": {}},
            {"id": f"node-grid-{plan['plan_id']}", "type": "image", "x": 600, "y": 200,
             "label": f"Scene Grid ({plan.get('grid_layout', '2x2')})", "status": "done", "output": plan.get("_grid_url", ""), "error": None, "props": {}},
        ])
    else:
        v3_nodes.extend([
            {"id": f"node-grid-{plan['plan_id']}", "type": "image", "x": 600, "y": 200,
             "label": f"Scene Grid ({plan.get('grid_layout', '2x2')})", "status": "done", "output": plan.get("_grid_url", ""), "error": None, "props": {}},
        ])

    v3_nodes.append(
        {"id": f"node-slicer-{plan['plan_id']}", "type": "input", "x": 930, "y": 200,
         "label": "Grid Slicer", "status": "done", "output": f"{plan.get('frame_count', 3)} frames", "error": None,
         "props": {"frame_urls": plan.get("_frame_urls", [])}},
    )

    v3_edges = []
    if not skip_char:
        v3_edges.extend([
            {"id": "e-dir-char", "from": f"node-director-{plan['plan_id']}", "to": f"node-char-{plan['plan_id']}"},
            {"id": "e-dir-grid", "from": f"node-director-{plan['plan_id']}", "to": f"node-grid-{plan['plan_id']}"},
            {"id": "e-char-grid", "from": f"node-char-{plan['plan_id']}", "to": f"node-grid-{plan['plan_id']}"},
        ])
    else:
        v3_edges.extend([
            {"id": "e-dir-grid", "from": f"node-director-{plan['plan_id']}", "to": f"node-grid-{plan['plan_id']}"},
        ])

    v3_edges.extend([
        {"id": "e-grid-slicer", "from": f"node-grid-{plan['plan_id']}", "to": f"node-slicer-{plan['plan_id']}"},
    ])

    if reference_image_urls:
        reference_node = f"node-references-{plan['plan_id']}"
        v3_edges.extend([
            {"id": "e-ref-director", "from": reference_node, "to": f"node-director-{plan['plan_id']}"},
            {"id": "e-ref-grid", "from": reference_node, "to": f"node-grid-{plan['plan_id']}"},
        ])
        if not skip_char:
            v3_edges.append(
                {"id": "e-ref-char", "from": reference_node, "to": f"node-char-{plan['plan_id']}"}
            )

    # Include video_plan in pipeline_state so it survives page refresh (B3 fix)
    v3_video_plan = {**plan, "pipeline_version": "v3_grid"}
    yield _sse({"pipeline_state": {
        "nodes": v3_nodes,
        "edges": v3_edges,
        "viewport": {"panX": 0, "panY": 0, "zoom": 1},
        "video_plan": v3_video_plan,
    }})

    yield _sse({"node": "v3_pipeline", "status": "completed", "data": {
        "message": "Assets ready — review and click Continue to generate video clips.",
        "plan_id": plan["plan_id"],
    }})

