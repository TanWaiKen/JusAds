"""
video_v3_grid.py
────────────────
Video Agent V3 — Character Grid Pipeline with per-node tracking.

Flow (each step emits a canvas node for the user to see progress):

  Node 1: Character Sheet    → Generate character turnaround reference
  Node 2: Scene Grid         → Generate NxM storyboard grid (dynamic count)
  Node 3: Grid Slicer        → PIL slices grid into individual frames
  Node 4-N: Scene Clips      → Veo I2V per frame (first→last frame animation)
  Node N+1: AI Editor        → Gemini plans edits (transitions, speed, text)
  Node N+2: Assembler        → FFmpeg renders .mp4 + CapCut draft created

Each node is recorded in pipeline_state so the user can:
- See which step is running/completed/failed
- Come back later and see the full pipeline with outputs
- Retry from any failed node

Uses prompt templates from:
  - docs/prompts/character_setting.md (character turnaround)
  - docs/prompts/scene_grid.md (dynamic scene grid)
"""

import json
import logging
import math
import os
import tempfile
import uuid
from pathlib import Path
from typing import AsyncGenerator, Optional

from shared.clients import gemini, s3
from shared.s3_client import upload_file_public
from config import S3_BUCKET_NAME

logger = logging.getLogger(__name__)

# ─── Prompt Templates ─────────────────────────────────────────────────────────

_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "docs" / "prompts"

def _load_prompt(filename: str) -> str:
    """Load a prompt template from docs/prompts/."""
    path = _PROMPTS_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    logger.warning("[V3Grid] Prompt template not found: %s", path)
    return ""

CHARACTER_SHEET_PROMPT = _load_prompt("character_setting.md")
SCENE_GRID_PROMPT = _load_prompt("scene_grid.md")


# ─── Constants ────────────────────────────────────────────────────────────────

_IMAGE_MODEL = "imagen-4.0-generate-001"
_VEO_MODEL = "veo-3.1-lite-generate-001"
_SCENE_CLIP_SECONDS = 5


def _resolve_scene_count(video_duration_sec: float) -> int:
    """Decide scene count based on target video duration.

    ~4-5s per scene is optimal for short-form ads.
    30s → 6-8 scenes, 15s → 3-4 scenes, 60s → 12 scenes.
    """
    count = max(3, min(12, int(video_duration_sec / 4.5)))
    return count


def _grid_dimensions(scene_count: int) -> tuple[int, int]:
    """Calculate grid layout (cols x rows) for the scene count.

    Tries to keep it roughly square. E.g., 6→3x2, 8→4x2, 9→3x3, 12→4x3.
    """
    cols = math.ceil(math.sqrt(scene_count))
    rows = math.ceil(scene_count / cols)
    return cols, rows


# ─── SSE helpers (match existing orchestrator pattern) ────────────────────────


def _sse(data: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data)}\n\n"


def _node_event(node_id: str, status: str, label: str, output: Optional[str] = None, error: Optional[str] = None, props: Optional[dict] = None) -> dict:
    """Build a node dict for the pipeline_state."""
    return {
        "id": node_id,
        "type": "process",
        "label": label,
        "status": status,  # "running" | "done" | "failed"
        "output": output,
        "error": error,
        "props": props or {},
    }


# ─── Main Pipeline ────────────────────────────────────────────────────────────


async def run_grid_pipeline(
    brief: str,
    project_id: str,
    task_id: str,
    character_description: str = "",
    product_description: str = "",
    reference_image_url: Optional[str] = None,
    video_duration_sec: float = 30.0,
    width: int = 1080,
    height: int = 1920,
    target_ethnicity: str = "all",
) -> AsyncGenerator[str, None]:
    """Run the full Character Grid Video Pipeline, yielding SSE events per node.

    Each step emits:
      - A status event (node running/completed/failed)
      - The updated pipeline_state with all nodes so far

    The frontend renders each node on the canvas in real-time.

    Args:
        brief: The user's video ad brief.
        project_id: Owning project.
        task_id: Owning task.
        character_description: Description of the character to generate.
        product_description: Product to integrate.
        reference_image_url: Optional reference image for character consistency.
        video_duration_sec: Target video length (determines scene count).
        width/height: Output dimensions.
        target_ethnicity: For localization.

    Yields:
        SSE data lines with node status + pipeline_state updates.
    """
    plan_id = uuid.uuid4().hex[:8]
    scene_count = _resolve_scene_count(video_duration_sec)
    cols, rows = _grid_dimensions(scene_count)

    # Pipeline state tracking
    nodes: list[dict] = []
    edges: list[dict] = []
    scene_frames: list[str] = []  # paths to sliced frames
    scene_clips: list[str] = []  # paths to Veo-generated clips

    logger.info(
        "[V3Grid] Starting pipeline: %d scenes (%dx%d grid), duration=%.0fs",
        scene_count, cols, rows, video_duration_sec,
    )

    # ══════════════════════════════════════════════════════════════════════════
    # NODE 1: Character Sheet Generation
    # ══════════════════════════════════════════════════════════════════════════
    node_char = f"node-character-{plan_id}"
    nodes.append(_node_event(node_char, "running", "Character Sheet"))
    yield _sse({"node": "character_sheet", "status": "in-progress", "data": {"message": "Generating character reference sheet..."}})
    yield _sse({"pipeline_state": {"nodes": nodes, "edges": edges}})

    char_sheet_url = None
    try:
        char_prompt = CHARACTER_SHEET_PROMPT.replace(
            "[INSERT CHARACTER APPEARANCE DESCRIPTION HERE]",
            character_description or brief,
        )

        from google.genai import types as genai_types
        response = gemini.models.generate_images(
            model=_IMAGE_MODEL,
            prompt=char_prompt,
            config=genai_types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="16:9",  # Landscape for turnaround sheet
                person_generation="ALLOW_ALL",
            ),
        )

        if response.generated_images:
            # Save and upload
            char_path = os.path.join(tempfile.gettempdir(), f"char_sheet_{plan_id}.png")
            with open(char_path, "wb") as f:
                f.write(response.generated_images[0].image.image_bytes)

            s3_key = f"generated_ads/{project_id}/{task_id}/v3_grid/{plan_id}/character_sheet.png"
            char_sheet_url = upload_file_public(char_path, s3_key)
            logger.info("[V3Grid] Character sheet uploaded: %s", char_sheet_url)

        nodes[-1] = _node_event(node_char, "done", "Character Sheet", output=char_sheet_url)
    except Exception as e:
        logger.error("[V3Grid] Character sheet failed: %s", e)
        nodes[-1] = _node_event(node_char, "failed", "Character Sheet", error=str(e))

    yield _sse({"node": "character_sheet", "status": "completed" if char_sheet_url else "failed"})
    yield _sse({"pipeline_state": {"nodes": nodes, "edges": edges}})


    # ══════════════════════════════════════════════════════════════════════════
    # NODE 2: Scene Grid Generation
    # ══════════════════════════════════════════════════════════════════════════
    node_grid = f"node-grid-{plan_id}"
    nodes.append(_node_event(node_grid, "running", f"Scene Grid ({cols}x{rows})"))
    edges.append({"id": f"edge-char-grid-{plan_id}", "from": node_char, "to": node_grid})
    yield _sse({"node": "scene_grid", "status": "in-progress", "data": {"message": f"Generating {cols}x{rows} storyboard grid..."}})
    yield _sse({"pipeline_state": {"nodes": nodes, "edges": edges}})

    grid_image_url = None
    grid_image_path = None
    try:
        grid_prompt = SCENE_GRID_PROMPT.replace("[num]", str(scene_count))
        grid_prompt = grid_prompt.replace(
            "[Insert Product Integration Details Here]",
            product_description or f"Product context: {brief}",
        )
        # Add reference to character sheet for consistency
        if char_sheet_url:
            grid_prompt += f"\n\nMaintain strict character consistency with the reference character sheet. Same character, same clothing, same style."

        from google.genai import types as genai_types
        response = gemini.models.generate_images(
            model=_IMAGE_MODEL,
            prompt=grid_prompt,
            config=genai_types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="16:9" if cols > rows else "1:1",
                person_generation="ALLOW_ALL",
            ),
        )

        if response.generated_images:
            grid_image_path = os.path.join(tempfile.gettempdir(), f"scene_grid_{plan_id}.png")
            with open(grid_image_path, "wb") as f:
                f.write(response.generated_images[0].image.image_bytes)

            s3_key = f"generated_ads/{project_id}/{task_id}/v3_grid/{plan_id}/scene_grid.png"
            grid_image_url = upload_file_public(grid_image_path, s3_key)
            logger.info("[V3Grid] Scene grid uploaded: %s", grid_image_url)

        nodes[-1] = _node_event(node_grid, "done", f"Scene Grid ({cols}x{rows})", output=grid_image_url)
    except Exception as e:
        logger.error("[V3Grid] Scene grid generation failed: %s", e)
        nodes[-1] = _node_event(node_grid, "failed", f"Scene Grid ({cols}x{rows})", error=str(e))
        yield _sse({"node": "scene_grid", "status": "failed", "data": {"error": str(e)}})
        yield _sse({"pipeline_state": {"nodes": nodes, "edges": edges}})
        return  # Can't continue without the grid

    yield _sse({"node": "scene_grid", "status": "completed", "data": {"grid_url": grid_image_url}})
    yield _sse({"pipeline_state": {"nodes": nodes, "edges": edges}})

    # ══════════════════════════════════════════════════════════════════════════
    # NODE 3: Grid Slicer (PIL splits grid into individual frames)
    # ══════════════════════════════════════════════════════════════════════════
    node_slicer = f"node-slicer-{plan_id}"
    nodes.append(_node_event(node_slicer, "running", "Grid Slicer"))
    edges.append({"id": f"edge-grid-slicer-{plan_id}", "from": node_grid, "to": node_slicer})
    yield _sse({"node": "grid_slicer", "status": "in-progress", "data": {"message": f"Slicing grid into {scene_count} frames..."}})
    yield _sse({"pipeline_state": {"nodes": nodes, "edges": edges}})

    try:
        scene_frames = _slice_grid(grid_image_path, cols, rows, scene_count, plan_id)

        # Upload each frame to S3
        frame_urls = []
        for i, frame_path in enumerate(scene_frames):
            s3_key = f"generated_ads/{project_id}/{task_id}/v3_grid/{plan_id}/frame_{i:02d}.png"
            url = upload_file_public(frame_path, s3_key)
            frame_urls.append(url)

        nodes[-1] = _node_event(
            node_slicer, "done", "Grid Slicer",
            output=json.dumps(frame_urls[:3]),  # Show first 3 as preview
            props={"frame_count": len(scene_frames), "frame_urls": frame_urls},
        )
        logger.info("[V3Grid] Sliced grid into %d frames", len(scene_frames))
    except Exception as e:
        logger.error("[V3Grid] Grid slicing failed: %s", e)
        nodes[-1] = _node_event(node_slicer, "failed", "Grid Slicer", error=str(e))
        yield _sse({"node": "grid_slicer", "status": "failed"})
        yield _sse({"pipeline_state": {"nodes": nodes, "edges": edges}})
        return

    yield _sse({"node": "grid_slicer", "status": "completed", "data": {"frame_count": len(scene_frames)}})
    yield _sse({"pipeline_state": {"nodes": nodes, "edges": edges}})


    # ══════════════════════════════════════════════════════════════════════════
    # NODES 4-N: Veo I2V per frame (each frame → video clip)
    # ══════════════════════════════════════════════════════════════════════════
    yield _sse({"node": "veo_clips", "status": "in-progress", "data": {"message": f"Generating {len(scene_frames)} video clips via Veo..."}})

    for i, frame_path in enumerate(scene_frames):
        node_clip = f"node-clip-{i}-{plan_id}"
        nodes.append(_node_event(node_clip, "running", f"Clip {i+1}/{len(scene_frames)}"))
        edges.append({"id": f"edge-slicer-clip-{i}-{plan_id}", "from": node_slicer, "to": node_clip})
        yield _sse({"node": f"clip_{i}", "status": "in-progress", "data": {"scene_index": i, "message": f"Animating frame {i+1}..."}})
        yield _sse({"pipeline_state": {"nodes": nodes, "edges": edges}})

        clip_path = None
        try:
            clip_path = await _generate_clip_veo(frame_path, i, plan_id, project_id, task_id)
            if clip_path:
                scene_clips.append(clip_path)
                nodes[-1] = _node_event(node_clip, "done", f"Clip {i+1}", output=clip_path)
            else:
                nodes[-1] = _node_event(node_clip, "failed", f"Clip {i+1}", error="Veo returned no video")
        except Exception as e:
            logger.error("[V3Grid] Clip %d generation failed: %s", i, e)
            nodes[-1] = _node_event(node_clip, "failed", f"Clip {i+1}", error=str(e))

        yield _sse({"node": f"clip_{i}", "status": "completed" if clip_path else "failed"})
        yield _sse({"pipeline_state": {"nodes": nodes, "edges": edges}})

    if not scene_clips:
        yield _sse({"error": "No video clips were generated — Veo failed for all frames"})
        return

    # ══════════════════════════════════════════════════════════════════════════
    # NODE N+1: AI Editor (Gemini plans edits)
    # ══════════════════════════════════════════════════════════════════════════
    node_editor = f"node-editor-{plan_id}"
    last_clip_node = f"node-clip-{len(scene_frames)-1}-{plan_id}"
    nodes.append(_node_event(node_editor, "running", "AI Editor"))
    edges.append({"id": f"edge-clips-editor-{plan_id}", "from": last_clip_node, "to": node_editor})
    yield _sse({"node": "ai_editor", "status": "in-progress", "data": {"message": "AI planning edits..."}})
    yield _sse({"pipeline_state": {"nodes": nodes, "edges": edges}})

    try:
        from .video_assembler import plan_edits

        # Build scene metadata for the AI editor
        scenes_meta = [
            {"subtitle": f"Scene {i+1}", "duration": _SCENE_CLIP_SECONDS, "description": brief}
            for i in range(len(scene_clips))
        ]
        edit_plan = await plan_edits(scenes_meta)
        nodes[-1] = _node_event(node_editor, "done", "AI Editor", output=json.dumps(edit_plan[:2]))
    except Exception as e:
        logger.error("[V3Grid] AI edit planning failed: %s", e)
        edit_plan = [{"transition_in": "crossfade", "transition_duration": 0.5, "speed_factor": 1.0, "text_overlay": "", "text_position": "bottom", "text_timing": "immediate"}] * len(scene_clips)
        nodes[-1] = _node_event(node_editor, "done", "AI Editor (fallback)", props={"fallback": True})

    yield _sse({"node": "ai_editor", "status": "completed"})
    yield _sse({"pipeline_state": {"nodes": nodes, "edges": edges}})

    # ══════════════════════════════════════════════════════════════════════════
    # NODE N+2: Assembler (FFmpeg .mp4 + CapCut draft)
    # ══════════════════════════════════════════════════════════════════════════
    node_assembler = f"node-assembler-{plan_id}"
    nodes.append(_node_event(node_assembler, "running", "Video Assembler"))
    edges.append({"id": f"edge-editor-assembler-{plan_id}", "from": node_editor, "to": node_assembler})
    yield _sse({"node": "assembler", "status": "in-progress", "data": {"message": "Assembling final video..."}})
    yield _sse({"pipeline_state": {"nodes": nodes, "edges": edges}})

    try:
        from .video_assembler import assemble_dual_output

        result = await assemble_dual_output(
            scene_clips=scene_clips,
            scenes=scenes_meta,
            draft_name=f"v3_grid_{plan_id}",
            width=width,
            height=height,
        )

        mp4_path = result.get("mp4_path")
        capcut_draft = result.get("capcut_draft")

        # Upload final .mp4 to S3
        final_url = None
        if mp4_path and os.path.exists(mp4_path):
            s3_key = f"generated_ads/{project_id}/{task_id}/v3_grid/{plan_id}/final_video.mp4"
            final_url = upload_file_public(mp4_path, s3_key)

        nodes[-1] = _node_event(
            node_assembler, "done", "Video Assembler",
            output=final_url,
            props={
                "mp4_url": final_url,
                "capcut_draft": capcut_draft.get("draft_name") if capcut_draft else None,
                "has_capcut_draft": bool(capcut_draft),
            },
        )

        yield _sse({"node": "assembler", "status": "completed", "data": {
            "mp4_url": final_url,
            "capcut_draft": capcut_draft,
        }})

    except Exception as e:
        logger.error("[V3Grid] Assembly failed: %s", e)
        nodes[-1] = _node_event(node_assembler, "failed", "Video Assembler", error=str(e))
        yield _sse({"node": "assembler", "status": "failed", "data": {"error": str(e)}})

    # Final pipeline state
    yield _sse({"pipeline_state": {"nodes": nodes, "edges": edges}})
    logger.info("[V3Grid] Pipeline complete: %d nodes, %d clips, mp4=%s", len(nodes), len(scene_clips), bool(final_url))


# ─── Helper functions ─────────────────────────────────────────────────────────


def _slice_grid(grid_path: str, cols: int, rows: int, total_scenes: int, plan_id: str) -> list[str]:
    """Slice a grid image into individual scene frames using PIL.

    Args:
        grid_path: Path to the grid image.
        cols: Number of columns in the grid.
        rows: Number of rows in the grid.
        total_scenes: Total number of scenes to extract.
        plan_id: Unique pipeline run ID for file naming.

    Returns:
        List of paths to sliced frame images.
    """
    from PIL import Image

    img = Image.open(grid_path)
    img_width, img_height = img.size

    cell_width = img_width // cols
    cell_height = img_height // rows

    frames = []
    count = 0
    for row in range(rows):
        for col in range(cols):
            if count >= total_scenes:
                break
            left = col * cell_width
            top = row * cell_height
            right = left + cell_width
            bottom = top + cell_height

            cell = img.crop((left, top, right, bottom))

            frame_path = os.path.join(tempfile.gettempdir(), f"frame_{plan_id}_{count:02d}.png")
            cell.save(frame_path, "PNG")
            frames.append(frame_path)
            count += 1

    logger.info("[V3Grid] Sliced %dx%d grid into %d frames (%dx%d each)",
                cols, rows, len(frames), cell_width, cell_height)
    return frames


async def _generate_clip_veo(
    frame_path: str,
    scene_index: int,
    plan_id: str,
    project_id: str,
    task_id: str,
) -> Optional[str]:
    """Generate a video clip from a keyframe using Veo I2V.

    Uses the frame as the starting image and generates a short animated clip.

    Args:
        frame_path: Path to the keyframe image.
        scene_index: Index of this scene (for file naming).
        plan_id: Pipeline run ID.
        project_id: For S3 key structure.
        task_id: For S3 key structure.

    Returns:
        S3 URL of the generated clip, or None on failure.
    """
    import time
    from google.genai import types as genai_types

    if not gemini:
        logger.error("[V3Grid] Gemini client unavailable for Veo I2V")
        return None

    try:
        # Read the keyframe image
        with open(frame_path, "rb") as f:
            image_bytes = f.read()

        # Call Veo image-to-video
        operation = gemini.models.generate_videos(
            model=_VEO_MODEL,
            image=genai_types.Image(image_bytes=image_bytes),
            config=genai_types.GenerateVideoConfig(
                aspect_ratio="9:16",
                number_of_videos=1,
                duration_seconds=_SCENE_CLIP_SECONDS,
                person_generation="ALLOW_ALL",
            ),
        )

        # Poll for completion (Veo is async)
        max_wait = 300  # 5 minutes max
        poll_interval = 10
        elapsed = 0
        while not operation.done and elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval
            operation = gemini.models.get_operation(operation)
            logger.info("[V3Grid] Clip %d: polling Veo... (%ds)", scene_index, elapsed)

        if not operation.done:
            logger.error("[V3Grid] Clip %d: Veo timed out after %ds", scene_index, max_wait)
            return None

        # Extract video from response
        result = operation.result
        if not result or not result.generated_videos:
            logger.error("[V3Grid] Clip %d: Veo returned no videos", scene_index)
            return None

        video = result.generated_videos[0].video
        if not video:
            return None

        # Save locally then upload
        clip_path = os.path.join(tempfile.gettempdir(), f"clip_{plan_id}_{scene_index:02d}.mp4")
        with open(clip_path, "wb") as f:
            f.write(video.video_bytes)

        s3_key = f"generated_ads/{project_id}/{task_id}/v3_grid/{plan_id}/clip_{scene_index:02d}.mp4"
        clip_url = upload_file_public(clip_path, s3_key)
        logger.info("[V3Grid] Clip %d generated: %s", scene_index, clip_url)
        return clip_url

    except Exception as e:
        logger.error("[V3Grid] Veo I2V failed for clip %d: %s", scene_index, e)
        return None
