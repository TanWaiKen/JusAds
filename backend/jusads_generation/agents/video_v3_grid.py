"""
video_v3_grid.py
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Video Agent V3 â€” Character Grid Pipeline with staged human approval.

Multi-stage pipeline (each stage returns results for user review):

  Stage 1: plan_script()
    â†’ Director plans scenes, character, transitions
    â†’ Returns: script plan (scenes + character summary)
    â†’ User reviews the plan, can edit subtitles/scenes

  Stage 2: generate_assets()
    â†’ Character Sheet (Imagen 4) + Scene Grid (Imagen 4) + Grid Slice (PIL)
    â†’ Returns: character_sheet_url, grid_url, frame_urls[]
    â†’ User reviews the visuals, confirms character looks right

  Stage 3: execute_production()
    â†’ Veo I2V (first+last frame) + AI Editor + Assembler (FFmpeg + CapCut)
    â†’ Returns: final_video_url, capcut_draft info
    â†’ User gets instant .mp4 + editable CapCut project

Each stage is called separately via the orchestrator/route.
Pipeline state is persisted between stages so user can leave and come back.

Uses Veo first+last frame: frame[0]â†’frame[1], frame[1]â†’frame[2], etc.
for smooth inter-scene character-consistent motion.
"""

import json
import logging
import math
import os
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator, Optional

from shared.clients import gemini, s3, supabase
from shared.config import MODEL_TEXT
from shared.s3_client import upload_file_public
from config import S3_BUCKET_NAME

logger = logging.getLogger(__name__)


# â”€â”€â”€ Prompt Templates â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "docs" / "prompts"


def _load_prompt(filename: str) -> str:
    """Load a prompt template from docs/prompts/."""
    path = _PROMPTS_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    logger.warning("[V3Grid] Prompt not found: %s", path)
    return ""


CHARACTER_SHEET_PROMPT = _load_prompt("character_setting.md")
SCENE_GRID_PROMPT = _load_prompt("scene_grid.md")

# â”€â”€â”€ Constants â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

_IMAGE_MODEL = "imagen-4.0-generate-001"
_VEO_MODEL = "veo-3.1-generate-001"
_SCENE_CLIP_SECONDS = 6
_VEO_POLL_INTERVAL = 15
_VEO_MAX_WAIT = 300


def _resolve_scene_count(video_duration_sec: float) -> int:
    """N+1 frames for N clips. 15s at 6s/clip â†’ 2 clips â†’ 3 frames."""
    video_duration_sec = min(video_duration_sec, 15.0)  # Cap at 15s to save costs
    clip_count = max(2, min(3, int(video_duration_sec / _SCENE_CLIP_SECONDS)))
    return clip_count + 1  # N+1 frames needed


def _grid_dimensions(frame_count: int) -> tuple[int, int]:
    """Calculate grid layout (cols x rows)."""
    cols = math.ceil(math.sqrt(frame_count))
    rows = math.ceil(frame_count / cols)
    return cols, rows


def _sse(data: dict) -> str:
    """Format SSE data line."""
    return f"data: {json.dumps(data)}\n\n"


def _persist_ad(
    project_id: str, task_id: str, media_type: str,
    s3_url: str, prompt_used: str, label: str = "",
) -> Optional[str]:
    """Save intermediate result to generated_ads (survives failures)."""
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


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# STAGE 1: Script Planning (Director)
# Returns the plan for user review. User can edit before proceeding.
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

_DIRECTOR_PROMPT = """You are a professional short-form video ad Director.
Plan a {clip_count}-scene video ad ({duration}s total, {clip_seconds}s per scene).

Brief: "{brief}"
Target audience: {ethnicity} in Malaysia
Platform: TikTok/Reels (vertical 9:16)

For EACH scene provide:
- "scene_index": number (1-based)
- "visual_description": what happens visually (setting, action, lighting)
- "camera_angle": shot type + movement (e.g. "CU slow push in", "WS static")
- "character_action": what the character does (pose, expression, gesture)
- "character_requirements": clothing/appearance for THIS scene
- "subtitle": on-screen text (max 8 words, punchy)
- "voiceover": spoken line (max 15 words)
- "transition_to_next": how this flows to next ("character turns", "zoom in", "cut")

STRUCTURE: Scene 1-2 = HOOK (attention grabber). Middle = PRODUCT. Final = CTA.

- "character_summary": overall character appearance (for character sheet generation, described as a real human model, photorealistic, with clothing details)
- "product_integration": how product appears across scenes
- "visual_style": ONE consistent photography/visual style for ALL scenes. It MUST be a photorealistic real human style. Always DEFAULT to "photorealistic commercial photography, cinematic lighting, real human model, shot on Sony A7IV". Under no circumstances generate character descriptions that imply cartoon, anime, 3D render, illustration, drawings, or sketches. Ads perform best with REAL HUMAN models â€” not illustrations.

Return JSON: {{"character_summary": "...", "product_integration": "...", "visual_style": "...", "scenes": [...]}}"""


async def plan_script(
    brief: str,
    video_duration_sec: float = 15.0,
    target_ethnicity: str = "all",
    product_description: str = "",
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
            "frame_count": N,
            "grid_layout": "3x2",
            "clip_count": N-1,
            "duration_sec": 30,
        }
    """
    plan_id = uuid.uuid4().hex[:8]
    frame_count = _resolve_scene_count(video_duration_sec)
    clip_count = frame_count - 1
    cols, rows = _grid_dimensions(frame_count)

    prompt = _DIRECTOR_PROMPT.format(
        clip_count=clip_count,
        duration=int(video_duration_sec),
        clip_seconds=_SCENE_CLIP_SECONDS,
        brief=brief,
        ethnicity=target_ethnicity,
    )
    if product_description:
        prompt += f"\n\nProduct: {product_description}"

    try:
        from google.genai import types as genai_types
        response = gemini.models.generate_content(
            model=MODEL_TEXT,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3,
            ),
        )
        result = json.loads(response.text)
        if "scenes" in result and isinstance(result["scenes"], list):
            logger.info("[V3Grid] Director planned %d scenes", len(result["scenes"]))
            return {
                "plan_id": plan_id,
                "character_summary": result.get("character_summary", brief),
                "product_integration": result.get("product_integration", product_description or brief),
                "visual_style": result.get("visual_style", "cinematic warm-toned photography"),
                "scenes": result["scenes"],
                "frame_count": frame_count,
                "grid_layout": f"{cols}x{rows}",
                "clip_count": clip_count,
                "duration_sec": video_duration_sec,
            }
    except Exception as e:
        logger.error("[V3Grid] Director planning failed: %s", e)

    # Fallback
    return {
        "plan_id": plan_id,
        "character_summary": brief,
        "product_integration": product_description or brief,
        "visual_style": "cinematic warm-toned photography, consistent lighting",
        "scenes": [
            {"scene_index": i+1, "visual_description": brief, "camera_angle": "MS static",
             "character_action": "presenting", "character_requirements": "",
             "subtitle": f"Scene {i+1}", "voiceover": "", "transition_to_next": "crossfade"}
            for i in range(clip_count)
        ],
        "frame_count": frame_count,
        "grid_layout": f"{cols}x{rows}",
        "clip_count": clip_count,
        "duration_sec": video_duration_sec,
    }


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# STAGE 2: Generate Assets (Character Sheet + Scene Grid + Slice)
# Returns images for user review before expensive Veo step.
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


async def generate_assets(
    plan: dict,
    project_id: str,
    task_id: str,
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

    yield _sse({"node": "character_sheet", "status": "in-progress", "data": {"message": "Generating character reference sheet..."}})

    # â”€â”€ Character Sheet â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    char_sheet_url = None
    try:
        char_prompt = CHARACTER_SHEET_PROMPT.replace(
            "[INSERT CHARACTER APPEARANCE DESCRIPTION HERE]", char_summary,
        )
        char_prompt += f"\n\nVISUAL STYLE (mandatory): {visual_style}. All panels must use this exact style."
        char_prompt += "\n\nIMPORTANT: Generate PHOTOREALISTIC humans. This is for a REAL advertising campaign â€” NOT anime, NOT illustration, NOT cartoon. Use professional photography style with natural skin, real clothing textures, and cinematic lighting. The character must look like a real person suitable for a commercial advertisement."
        from google.genai import types as genai_types
        response = gemini.models.generate_images(
            model=_IMAGE_MODEL,
            prompt=char_prompt,
            config=genai_types.GenerateImagesConfig(
                number_of_images=1, aspect_ratio="16:9", person_generation="ALLOW_ALL",
            ),
        )
        if response.generated_images:
            path = os.path.join(tempfile.gettempdir(), f"char_{plan_id}.png")
            with open(path, "wb") as f:
                f.write(response.generated_images[0].image.image_bytes)
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

    # â”€â”€ Scene Grid (uses character sheet as reference image) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    yield _sse({"node": "scene_grid", "status": "in-progress", "data": {"message": f"Generating {cols}x{rows} scene grid using character reference..."}})

    grid_url = None
    grid_path = None
    try:
        scene_descriptions = "\n".join(
            f"Panel {i+1}: {s.get('camera_angle', 'MS')} â€” {s.get('visual_description', '')[:60]}"
            for i, s in enumerate(scenes)
        )
        scene_descriptions += f"\nPanel {len(scenes)+1}: Final CTA pose"

        grid_prompt = SCENE_GRID_PROMPT.replace("[num]", str(frame_count))
        grid_prompt = grid_prompt.replace(
            "[Insert Product Integration Details Here]",
            f"Product: {product_integration}\n\nPanels:\n{scene_descriptions}",
        )
        grid_prompt += f"\n\nCharacter (MUST match the uploaded reference): {char_summary}"
        grid_prompt += f"\n\nVISUAL STYLE (mandatory): {visual_style}. Every panel must match this exact style."
        grid_prompt += f"\n\nREFERENCE IMAGE: The uploaded image is the character sheet. Each panel must show the EXACT same character with the SAME face, body, clothing, and style. Do NOT create different characters."

        from google.genai import types as genai_types

        # Generate scene grid with Imagen 4 (character consistency via strong prompt)
        response = gemini.models.generate_images(
            model=_IMAGE_MODEL,
            prompt=grid_prompt,
            config=genai_types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="1:1",  # Square grid for consistent cell sizing
                person_generation="ALLOW_ALL",
            ),
        )
        if response.generated_images:
            grid_path = os.path.join(tempfile.gettempdir(), f"grid_{plan_id}.png")
            with open(grid_path, "wb") as f:
                f.write(response.generated_images[0].image.image_bytes)
            s3_key = f"generated_ads/{project_id}/{task_id}/v3/{plan_id}/scene_grid.png"
            grid_url = upload_file_public(grid_path, s3_key)
            _persist_ad(project_id, task_id, "image", grid_url, f"Scene Grid ({cols}x{rows})", "Scene Grid")
    except Exception as e:
        logger.error("[V3Grid] Scene grid failed: %s", e)

    yield _sse({"node": "scene_grid", "status": "completed" if grid_url else "failed", "data": {"url": grid_url}})

    if not grid_path or not grid_url:
        yield _sse({"error": "Scene grid generation failed â€” cannot proceed"})
        return

    # â”€â”€ Grid Slice â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# STAGE 3: Execute Production (Veo + Edit + Assemble)
# Only runs after user approves the assets from Stage 2.
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


async def execute_production(
    assets: dict,
    project_id: str,
    task_id: str,
    brief: str = "",
) -> AsyncGenerator[str, None]:
    """Stage 3: Generate video clips from frames and assemble final video.

    Takes the approved assets from Stage 2 (frame_urls) and:
    1. Downloads frames locally
    2. Runs Veo I2V with first+last frame pairs
    3. AI Editor plans edits
    4. Assembler produces FFmpeg .mp4 + CapCut draft

    Yields SSE events for progress.
    """
    plan_id = assets.get("plan_id", uuid.uuid4().hex[:8])
    frame_urls = assets.get("frame_urls", [])
    scenes = assets.get("scenes", [])
    clip_count = len(frame_urls) - 1

    if clip_count < 1:
        yield _sse({"error": "Need at least 2 frames to produce video clips"})
        return

    # â”€â”€ Download frames locally â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    yield _sse({"node": "download_frames", "status": "in-progress", "data": {"message": "Downloading frames..."}})

    import urllib.request
    local_frames = []
    for i, url in enumerate(frame_urls):
        try:
            path = os.path.join(tempfile.gettempdir(), f"dl_frame_{plan_id}_{i:02d}.png")
            urllib.request.urlretrieve(url, path)
            local_frames.append(path)
        except Exception as e:
            logger.warning("[V3Grid] Frame %d download failed: %s", i, e)

    if len(local_frames) < 2:
        yield _sse({"error": "Failed to download enough frames"})
        return

    yield _sse({"node": "download_frames", "status": "completed", "data": {"count": len(local_frames)}})

    # â”€â”€ Veo I2V (first + last frame pairs) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    scene_clips: list[str] = []
    actual_clips = len(local_frames) - 1

    for i in range(actual_clips):
        yield _sse({"node": f"veo_clip_{i}", "status": "in-progress", "data": {
            "message": f"Veo: frame[{i}] â†’ frame[{i+1}] (clip {i+1}/{actual_clips})...",
            "clip_index": i,
        }})

        try:
            clip_url = await _generate_veo_clip(
                first_frame=local_frames[i],
                last_frame=local_frames[i + 1],
                prompt=scenes[i].get("visual_description", brief) if i < len(scenes) else brief,
                scene_index=i,
                plan_id=plan_id,
                project_id=project_id,
                task_id=task_id,
            )
            if clip_url:
                scene_clips.append(clip_url)
                _persist_ad(project_id, task_id, "video", clip_url, f"Scene {i+1} clip", f"Clip {i+1}")
                yield _sse({"node": f"veo_clip_{i}", "status": "completed", "data": {"url": clip_url}})
            else:
                yield _sse({"node": f"veo_clip_{i}", "status": "failed", "data": {"error": "Veo returned no video"}})
        except Exception as e:
            logger.error("[V3Grid] Clip %d failed: %s", i, e)
            yield _sse({"node": f"veo_clip_{i}", "status": "failed", "data": {"error": str(e)}})

    if not scene_clips:
        yield _sse({"error": "No video clips generated â€” Veo failed for all frame pairs"})
        return

    # â”€â”€ AI Editor + Assembly â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
                scenes=scenes[:len(local_clips)],
                draft_name=f"v3_{plan_id}",
            )

            mp4_path = result.get("mp4_path")
            final_url = None
            if mp4_path and os.path.exists(mp4_path):
                s3_key = f"generated_ads/{project_id}/{task_id}/v3/{plan_id}/final_video.mp4"
                final_url = upload_file_public(mp4_path, s3_key)
                _persist_ad(project_id, task_id, "video", final_url, f"Final V3 Video Ad: {brief[:80]}", "Final Video")

            yield _sse({"node": "assembler", "status": "completed", "data": {
                "mp4_url": final_url,
                "capcut_draft": result.get("capcut_draft"),
                "clips_produced": len(scene_clips),
            }})
        else:
            yield _sse({"node": "assembler", "status": "failed", "data": {"error": "No clips to assemble"}})

    except Exception as e:
        logger.error("[V3Grid] Assembly failed: %s", e)
        yield _sse({"node": "assembler", "status": "failed", "data": {"error": str(e)}})


# â”€â”€â”€ Helper Functions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def _slice_grid(grid_path: str, cols: int, rows: int, total_frames: int, plan_id: str) -> list[str]:
    """Slice grid image into individual frames (leftâ†’right, topâ†’bottom)."""
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

    logger.info("[V3Grid] Sliced %dx%d grid â†’ %d frames (%dx%d each)", cols, rows, len(frames), cell_w, cell_h)
    return frames


async def _generate_veo_clip(
    first_frame: str,
    last_frame: str,
    prompt: str,
    scene_index: int,
    plan_id: str,
    project_id: str,
    task_id: str,
) -> Optional[str]:
    """Generate a video clip using Veo first+last frame mode.

    Returns S3 URL of the clip, or None on failure.
    """
    from google.genai import types as genai_types

    if not gemini:
        return None

    try:
        with open(first_frame, "rb") as f:
            first_bytes = f.read()
        with open(last_frame, "rb") as f:
            last_bytes = f.read()

        operation = gemini.models.generate_videos(
            model=_VEO_MODEL,
            prompt=prompt[:500],
            image=genai_types.Image(image_bytes=first_bytes, mime_type="image/png"),
            config=genai_types.GenerateVideosConfig(
                aspect_ratio="9:16",
                number_of_videos=1,
                duration_seconds=_SCENE_CLIP_SECONDS,
                person_generation="ALLOW_ALL",
                last_frame=genai_types.Image(image_bytes=last_bytes, mime_type="image/png"),
            ),
        )

        # Poll for completion
        elapsed = 0
        while not operation.done and elapsed < _VEO_MAX_WAIT:
            time.sleep(_VEO_POLL_INTERVAL)
            elapsed += _VEO_POLL_INTERVAL
            operation = gemini.operations.get(operation)

        if not operation.done:
            logger.error("[V3Grid] Clip %d: Veo timed out", scene_index)
            return None

        result = operation.result
        if not result or not result.generated_videos:
            return None

        video = result.generated_videos[0].video
        if not video:
            return None

        # Save locally then upload
        clip_path = os.path.join(tempfile.gettempdir(), f"clip_{plan_id}_{scene_index:02d}.mp4")
        if video.video_bytes:
            with open(clip_path, "wb") as f:
                f.write(video.video_bytes)
        elif video.uri:
            import urllib.request
            urllib.request.urlretrieve(video.uri, clip_path)
        else:
            return None

        s3_key = f"generated_ads/{project_id}/{task_id}/v3/{plan_id}/clip_{scene_index:02d}.mp4"
        return upload_file_public(clip_path, s3_key)

    except Exception as e:
        logger.error("[V3Grid] Veo clip %d failed: %s", scene_index, e)
        return None


# â”€â”€â”€ Legacy compatibility: single-call pipeline (used by orchestrator) â”€â”€â”€â”€â”€â”€â”€â”€


async def run_grid_pipeline(
    brief: str,
    project_id: str,
    task_id: str,
    character_description: str = "",
    product_description: str = "",
    reference_image_url: Optional[str] = None,
    video_duration_sec: float = 15.0,
    width: int = 1080,
    height: int = 1920,
    target_ethnicity: str = "all",
) -> AsyncGenerator[str, None]:
    """Orchestrator-compatible entry point. Runs Stage 1 + Stage 2 inline.

    Stage 3 (Veo) is triggered separately when user clicks Continue.
    This function plans the script + generates assets, then emits a v3_plan
    event for the frontend to show (like V2's video_plan).
    """
    # Stage 1: Plan
    yield _sse({"node": "director", "status": "in-progress", "data": {"message": "Director planning script..."}})

    plan = await plan_script(
        brief=brief,
        video_duration_sec=video_duration_sec,
        target_ethnicity=target_ethnicity,
        product_description=product_description or character_description,
    )

    yield _sse({"node": "director", "status": "completed", "data": {
        "scene_count": len(plan["scenes"]),
        "character_summary": plan["character_summary"][:100],
    }})

    # Stage 2: Generate assets (capture URLs for pipeline_state)
    async for event in generate_assets(plan, project_id, task_id):
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
    v3_nodes = [
        {"id": f"node-director-{plan['plan_id']}", "type": "orchestrator", "x": 100, "y": 200,
         "label": "Director", "status": "done", "output": f"{len(plan['scenes'])} scenes planned", "error": None, "props": {}},
        {"id": f"node-char-{plan['plan_id']}", "type": "image", "x": 350, "y": 100,
         "label": "Character Sheet", "status": "done", "output": plan.get("_char_url", ""), "error": None, "props": {}},
        {"id": f"node-grid-{plan['plan_id']}", "type": "image", "x": 600, "y": 200,
         "label": f"Scene Grid ({plan.get('grid_layout', '2x2')})", "status": "done", "output": plan.get("_grid_url", ""), "error": None, "props": {}},
        {"id": f"node-slicer-{plan['plan_id']}", "type": "input", "x": 850, "y": 200,
         "label": "Grid Slicer", "status": "done", "output": f"{plan.get('frame_count', 3)} frames", "error": None,
         "props": {"frame_urls": plan.get("_frame_urls", [])}},
    ]
    v3_edges = [
        {"id": "e-dir-char", "from": f"node-director-{plan['plan_id']}", "to": f"node-char-{plan['plan_id']}"},
        {"id": "e-dir-grid", "from": f"node-director-{plan['plan_id']}", "to": f"node-grid-{plan['plan_id']}"},
        {"id": "e-char-grid", "from": f"node-char-{plan['plan_id']}", "to": f"node-grid-{plan['plan_id']}"},
        {"id": "e-grid-slicer", "from": f"node-grid-{plan['plan_id']}", "to": f"node-slicer-{plan['plan_id']}"},
    ]

    # Include video_plan in pipeline_state so it survives page refresh (B3 fix)
    v3_video_plan = {**plan, "pipeline_version": "v3_grid"}
    yield _sse({"pipeline_state": {
        "nodes": v3_nodes,
        "edges": v3_edges,
        "viewport": {"panX": 0, "panY": 0, "zoom": 1},
        "video_plan": v3_video_plan,
    }})

    yield _sse({"node": "v3_pipeline", "status": "completed", "data": {
        "message": "Assets ready â€” review and click Continue to generate video clips.",
        "plan_id": plan["plan_id"],
    }})

