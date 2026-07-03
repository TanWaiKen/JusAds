"""
video_v3_grid.py
────────────────
Video Agent V3 — Character Grid Pipeline with per-node tracking.

Flow (each step emits a canvas node):

  Node 0: Director/Script Planner → Gemini plans scene-by-scene script
           (what each scene shows, voiceover, camera angle, character actions)
  Node 1: Character Sheet → Imagen generates turnaround reference from director's
           character requirements
  Node 2: Scene Grid → Dynamic NxM storyboard grid using character sheet +
           director's per-scene prompts (Gemini Flash Lite Image)
  Node 3: Grid Slicer → PIL splits grid into individual frames
  Node 4-N: Veo I2V → First-frame + Last-frame per pair (scene[0]→scene[1],
            scene[1]→scene[2], etc.) for smooth inter-scene motion
  Node N+1: AI Editor → Gemini plans transitions/speed/text
  Node N+2: Assembler → FFmpeg .mp4 + CapCut draft (dual output)

Veo usage: First-and-last-frame mode for character-consistent motion:
  - Clip 1: frame[0] as first_frame, frame[1] as last_frame
  - Clip 2: frame[1] as first_frame, frame[2] as last_frame
  - etc.
This ensures smooth transitions with consistent character between shots.

Uses prompt templates from:
  - docs/prompts/character_setting.md (character turnaround)
  - docs/prompts/scene_grid.md (dynamic scene grid)
"""

import json
import logging
import math
import os
import tempfile
import time
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

_IMAGE_MODEL = "gemini-2.0-flash-lite"  # For character sheet + scene grid (image gen)
_IMAGE_MODEL_FALLBACK = "imagen-4.0-generate-001"
_VEO_MODEL = "veo-3.1-generate-001"  # Full Veo (supports first+last frame)
_SCENE_CLIP_SECONDS = 6  # Each clip is 6s (Veo supports 4/6/8)
_VEO_POLL_INTERVAL = 15
_VEO_MAX_WAIT = 300


def _resolve_scene_count(video_duration_sec: float) -> int:
    """Decide scene count based on target video duration.

    Each clip uses first→last frame pairs, so we need N+1 frames for N clips.
    30s video at 6s/clip → 5 clips → 6 frames needed.
    """
    clip_count = max(3, min(10, int(video_duration_sec / _SCENE_CLIP_SECONDS)))
    frame_count = clip_count + 1  # N clips need N+1 keyframes
    return frame_count


def _grid_dimensions(frame_count: int) -> tuple[int, int]:
    """Calculate grid layout (cols x rows) for the frame count."""
    cols = math.ceil(math.sqrt(frame_count))
    rows = math.ceil(frame_count / cols)
    return cols, rows


# ─── SSE helpers ──────────────────────────────────────────────────────────────


def _sse(data: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data)}\n\n"


def _node_dict(
    node_id: str, status: str, label: str,
    node_type: str = "process",
    x: int = 0, y: int = 0,
    output: Optional[str] = None,
    error: Optional[str] = None,
    props: Optional[dict] = None,
) -> dict:
    """Build a node dict for pipeline_state."""
    return {
        "id": node_id,
        "type": node_type,
        "label": label,
        "x": x, "y": y,
        "status": status,
        "output": output,
        "error": error,
        "props": props or {},
    }


# ─── Node 0: Director / Script Planner ────────────────────────────────────────

_DIRECTOR_PROMPT = """You are a professional short-form video ad Director.
Plan a {clip_count}-scene video ad ({duration}s total, {clip_seconds}s per scene).

Brief: "{brief}"
Target audience: {ethnicity} in Malaysia
Platform: TikTok/Reels (vertical {aspect_ratio})

For EACH scene, provide:
- "scene_index": scene number (1-based)
- "visual_description": what happens visually (setting, action, lighting, framing)
- "camera_angle": shot type + camera movement (e.g. "CU slow push in", "WS static", "ECU handheld")
- "character_action": what the character is specifically doing (pose, expression, gesture)
- "character_requirements": clothing/appearance needs for THIS scene (may differ slightly per scene for wardrobe changes)
- "subtitle": short on-screen text (max 8 words, punchy)
- "voiceover": spoken line for this scene (max 15 words)
- "transition_to_next": how this scene flows into the next ("character turns left", "zoom into product", "fade to black")

STRUCTURE:
- Scene 1-2: HOOK (attention grabber, pattern interrupt)
- Scene 3-{mid}: PRODUCT (show product benefit, demo)
- Final scene: CTA (call to action)

Also provide:
- "character_summary": overall character appearance description (for generating the character sheet)
- "product_integration": how the product appears across scenes

Return JSON: {{"character_summary": "...", "product_integration": "...", "scenes": [...]}}
Only valid JSON, no prose."""


async def _plan_script(
    brief: str,
    video_duration_sec: float,
    target_ethnicity: str,
    product_description: str,
) -> dict:
    """Node 0: Director plans the full script and character requirements.

    Returns dict with character_summary, product_integration, and scenes list.
    """
    clip_count = max(3, min(10, int(video_duration_sec / _SCENE_CLIP_SECONDS)))

    prompt = _DIRECTOR_PROMPT.format(
        clip_count=clip_count,
        duration=int(video_duration_sec),
        clip_seconds=_SCENE_CLIP_SECONDS,
        brief=brief,
        ethnicity=target_ethnicity,
        aspect_ratio="9:16",
        mid=clip_count - 1,
    )

    if product_description:
        prompt += f"\n\nProduct details: {product_description}"

    try:
        from google.genai import types as genai_types

        response = gemini.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3,
            ),
        )

        result = json.loads(response.text)
        if "scenes" in result and isinstance(result["scenes"], list):
            logger.info("[V3Grid] Director planned %d scenes", len(result["scenes"]))
            return result

    except Exception as e:
        logger.error("[V3Grid] Director planning failed: %s", e)

    # Fallback: minimal plan
    return {
        "character_summary": brief,
        "product_integration": product_description or brief,
        "scenes": [
            {
                "scene_index": i + 1,
                "visual_description": brief,
                "camera_angle": "MS static",
                "character_action": "presenting product",
                "character_requirements": "",
                "subtitle": f"Scene {i+1}",
                "voiceover": "",
                "transition_to_next": "crossfade",
            }
            for i in range(clip_count)
        ],
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

    Each step emits a node status + updated pipeline_state. The frontend renders
    each node on the canvas in real-time. When a user leaves and comes back,
    the persisted pipeline_state shows all completed nodes with their outputs.

    Yields:
        SSE data lines with node status + pipeline_state updates.
    """
    plan_id = uuid.uuid4().hex[:8]
    nodes: list[dict] = []
    edges: list[dict] = []
    scene_frames: list[str] = []
    scene_clips: list[str] = []

    def _emit_state() -> str:
        return _sse({"pipeline_state": {"nodes": nodes, "edges": edges}})

    # ══════════════════════════════════════════════════════════════════════════
    # NODE 0: Director / Script Planner
    # ══════════════════════════════════════════════════════════════════════════
    node_dir = f"node-director-{plan_id}"
    nodes.append(_node_dict(node_dir, "running", "Director", x=100, y=200))
    yield _sse({"node": "director", "status": "in-progress", "data": {"message": "Director planning script..."}})
    yield _emit_state()

    script_plan = await _plan_script(brief, video_duration_sec, target_ethnicity, product_description)
    scenes = script_plan.get("scenes", [])
    char_summary = script_plan.get("character_summary", character_description or brief)
    product_integration = script_plan.get("product_integration", product_description or brief)

    frame_count = len(scenes) + 1  # N scenes need N+1 keyframes for first/last frame pairs
    cols, rows = _grid_dimensions(frame_count)

    nodes[0] = _node_dict(
        node_dir, "done", "Director", x=100, y=200,
        output=json.dumps({"scene_count": len(scenes), "character": char_summary[:80]}),
        props={"scenes": scenes, "character_summary": char_summary},
    )
    yield _sse({"node": "director", "status": "completed", "data": {"scene_count": len(scenes), "character_summary": char_summary[:100]}})
    yield _emit_state()

    logger.info("[V3Grid] Director: %d scenes, %d frames needed (%dx%d grid)", len(scenes), frame_count, cols, rows)

    # ══════════════════════════════════════════════════════════════════════════
    # NODE 1: Character Sheet
    # ══════════════════════════════════════════════════════════════════════════
    node_char = f"node-character-{plan_id}"
    nodes.append(_node_dict(node_char, "running", "Character Sheet", x=350, y=100))
    edges.append({"id": f"e-dir-char-{plan_id}", "from": node_dir, "to": node_char})
    yield _sse({"node": "character_sheet", "status": "in-progress", "data": {"message": "Generating character reference..."}})
    yield _emit_state()

    char_sheet_url = None
    try:
        char_prompt = CHARACTER_SHEET_PROMPT.replace(
            "[INSERT CHARACTER APPEARANCE DESCRIPTION HERE]",
            char_summary,
        )
        from google.genai import types as genai_types

        response = gemini.models.generate_images(
            model=_IMAGE_MODEL_FALLBACK,  # Imagen 4 for high quality
            prompt=char_prompt,
            config=genai_types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="16:9",
                person_generation="ALLOW_ALL",
            ),
        )
        if response.generated_images:
            path = os.path.join(tempfile.gettempdir(), f"char_{plan_id}.png")
            with open(path, "wb") as f:
                f.write(response.generated_images[0].image.image_bytes)
            s3_key = f"generated_ads/{project_id}/{task_id}/v3/{plan_id}/character_sheet.png"
            char_sheet_url = upload_file_public(path, s3_key)

        nodes[-1] = _node_dict(node_char, "done", "Character Sheet", x=350, y=100, output=char_sheet_url)
    except Exception as e:
        logger.error("[V3Grid] Character sheet failed: %s", e)
        nodes[-1] = _node_dict(node_char, "failed", "Character Sheet", x=350, y=100, error=str(e))

    yield _sse({"node": "character_sheet", "status": "completed" if char_sheet_url else "failed"})
    yield _emit_state()


    # ══════════════════════════════════════════════════════════════════════════
    # NODE 2: Scene Grid (uses director's plan + character sheet)
    # ══════════════════════════════════════════════════════════════════════════
    node_grid = f"node-grid-{plan_id}"
    nodes.append(_node_dict(node_grid, "running", f"Scene Grid ({cols}x{rows})", x=600, y=200))
    edges.append({"id": f"e-char-grid-{plan_id}", "from": node_char, "to": node_grid})
    edges.append({"id": f"e-dir-grid-{plan_id}", "from": node_dir, "to": node_grid})
    yield _sse({"node": "scene_grid", "status": "in-progress", "data": {"message": f"Generating {cols}x{rows} storyboard grid ({frame_count} frames)..."}})
    yield _emit_state()

    grid_image_path = None
    grid_image_url = None
    try:
        # Build the grid prompt using director's scene descriptions
        scene_descriptions = "\n".join(
            f"Panel {i+1}: {s.get('camera_angle', 'MS')} — {s.get('visual_description', '')[:60]}"
            for i, s in enumerate(scenes)
        )
        # Add one extra panel for the final last-frame
        scene_descriptions += f"\nPanel {len(scenes)+1}: Final pose — character facing camera, CTA moment"

        grid_prompt = SCENE_GRID_PROMPT.replace("[num]", str(frame_count))
        grid_prompt = grid_prompt.replace(
            "[Insert Product Integration Details Here]",
            f"Product: {product_integration}\n\nScene layout (show each panel in order):\n{scene_descriptions}",
        )
        grid_prompt += f"\n\nCharacter: {char_summary}\nMaintain STRICT character consistency across all panels."

        from google.genai import types as genai_types
        response = gemini.models.generate_images(
            model=_IMAGE_MODEL_FALLBACK,
            prompt=grid_prompt,
            config=genai_types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="16:9" if cols >= rows else "1:1",
                person_generation="ALLOW_ALL",
            ),
        )
        if response.generated_images:
            grid_image_path = os.path.join(tempfile.gettempdir(), f"grid_{plan_id}.png")
            with open(grid_image_path, "wb") as f:
                f.write(response.generated_images[0].image.image_bytes)
            s3_key = f"generated_ads/{project_id}/{task_id}/v3/{plan_id}/scene_grid.png"
            grid_image_url = upload_file_public(grid_image_path, s3_key)

        nodes[-1] = _node_dict(node_grid, "done", f"Scene Grid ({cols}x{rows})", x=600, y=200, output=grid_image_url)
    except Exception as e:
        logger.error("[V3Grid] Scene grid failed: %s", e)
        nodes[-1] = _node_dict(node_grid, "failed", f"Scene Grid ({cols}x{rows})", x=600, y=200, error=str(e))
        yield _sse({"node": "scene_grid", "status": "failed"})
        yield _emit_state()
        return

    yield _sse({"node": "scene_grid", "status": "completed", "data": {"grid_url": grid_image_url}})
    yield _emit_state()

    # ══════════════════════════════════════════════════════════════════════════
    # NODE 3: Grid Slicer
    # ══════════════════════════════════════════════════════════════════════════
    node_slicer = f"node-slicer-{plan_id}"
    nodes.append(_node_dict(node_slicer, "running", "Grid Slicer", x=850, y=200))
    edges.append({"id": f"e-grid-slicer-{plan_id}", "from": node_grid, "to": node_slicer})
    yield _sse({"node": "grid_slicer", "status": "in-progress", "data": {"message": f"Slicing into {frame_count} frames..."}})
    yield _emit_state()

    try:
        scene_frames = _slice_grid(grid_image_path, cols, rows, frame_count, plan_id)
        # Upload frames
        frame_urls = []
        for i, fp in enumerate(scene_frames):
            s3_key = f"generated_ads/{project_id}/{task_id}/v3/{plan_id}/frame_{i:02d}.png"
            url = upload_file_public(fp, s3_key)
            frame_urls.append(url)

        nodes[-1] = _node_dict(
            node_slicer, "done", "Grid Slicer", x=850, y=200,
            output=f"{len(scene_frames)} frames",
            props={"frame_count": len(scene_frames), "frame_urls": frame_urls},
        )
    except Exception as e:
        logger.error("[V3Grid] Slicer failed: %s", e)
        nodes[-1] = _node_dict(node_slicer, "failed", "Grid Slicer", x=850, y=200, error=str(e))
        yield _sse({"node": "grid_slicer", "status": "failed"})
        yield _emit_state()
        return

    yield _sse({"node": "grid_slicer", "status": "completed", "data": {"frame_count": len(scene_frames)}})
    yield _emit_state()


    # ══════════════════════════════════════════════════════════════════════════
    # NODES 4-N: Veo I2V with First+Last Frame pairs
    # frame[0]→frame[1], frame[1]→frame[2], ... (N clips from N+1 frames)
    # ══════════════════════════════════════════════════════════════════════════
    clip_count = len(scene_frames) - 1  # N+1 frames → N clips
    yield _sse({"node": "veo_clips", "status": "in-progress", "data": {"message": f"Generating {clip_count} video clips (first→last frame)..."}})

    for i in range(clip_count):
        node_clip = f"node-clip-{i}-{plan_id}"
        nodes.append(_node_dict(node_clip, "running", f"Clip {i+1}/{clip_count}", x=1100, y=80 + i * 100))
        edges.append({"id": f"e-slicer-clip-{i}-{plan_id}", "from": node_slicer, "to": node_clip})
        yield _sse({"node": f"clip_{i}", "status": "in-progress", "data": {
            "scene_index": i,
            "message": f"Veo: frame[{i}] → frame[{i+1}] ({_SCENE_CLIP_SECONDS}s clip)...",
        }})
        yield _emit_state()

        clip_url = None
        try:
            first_frame = scene_frames[i]
            last_frame = scene_frames[i + 1]
            scene_data = scenes[i] if i < len(scenes) else {}
            scene_prompt = scene_data.get("visual_description", "") or scene_data.get("voiceover", "") or brief

            clip_url = await _generate_clip_first_last(
                first_frame_path=first_frame,
                last_frame_path=last_frame,
                prompt=scene_prompt,
                scene_index=i,
                plan_id=plan_id,
                project_id=project_id,
                task_id=task_id,
            )
            if clip_url:
                scene_clips.append(clip_url)
                nodes[-1] = _node_dict(node_clip, "done", f"Clip {i+1}", x=1100, y=80 + i * 100, output=clip_url)
            else:
                nodes[-1] = _node_dict(node_clip, "failed", f"Clip {i+1}", x=1100, y=80 + i * 100, error="Veo returned no video")
        except Exception as e:
            logger.error("[V3Grid] Clip %d failed: %s", i, e)
            nodes[-1] = _node_dict(node_clip, "failed", f"Clip {i+1}", x=1100, y=80 + i * 100, error=str(e))

        yield _sse({"node": f"clip_{i}", "status": "completed" if clip_url else "failed"})
        yield _emit_state()

    if not scene_clips:
        yield _sse({"error": "No video clips generated — Veo failed for all frame pairs"})
        return

    # ══════════════════════════════════════════════════════════════════════════
    # NODE N+1: AI Editor
    # ══════════════════════════════════════════════════════════════════════════
    node_editor = f"node-editor-{plan_id}"
    last_clip_id = f"node-clip-{clip_count-1}-{plan_id}"
    nodes.append(_node_dict(node_editor, "running", "AI Editor", x=1350, y=200))
    edges.append({"id": f"e-clips-editor-{plan_id}", "from": last_clip_id, "to": node_editor})
    yield _sse({"node": "ai_editor", "status": "in-progress", "data": {"message": "AI planning edits..."}})
    yield _emit_state()

    try:
        from .video_assembler import plan_edits
        scenes_meta = [
            {"subtitle": s.get("subtitle", ""), "duration": _SCENE_CLIP_SECONDS, "description": s.get("visual_description", "")}
            for s in scenes[:clip_count]
        ]
        edit_plan = await plan_edits(scenes_meta)
        nodes[-1] = _node_dict(node_editor, "done", "AI Editor", x=1350, y=200, props={"edit_plan": edit_plan})
    except Exception as e:
        logger.error("[V3Grid] AI Editor failed: %s — using defaults", e)
        from .video_assembler import _default_edit_plan
        edit_plan = _default_edit_plan(scenes[:clip_count])
        nodes[-1] = _node_dict(node_editor, "done", "AI Editor (fallback)", x=1350, y=200)

    yield _sse({"node": "ai_editor", "status": "completed"})
    yield _emit_state()

    # ══════════════════════════════════════════════════════════════════════════
    # NODE N+2: Assembler (FFmpeg .mp4 + CapCut draft)
    # ══════════════════════════════════════════════════════════════════════════
    node_asm = f"node-assembler-{plan_id}"
    nodes.append(_node_dict(node_asm, "running", "Video Assembler", x=1600, y=200))
    edges.append({"id": f"e-editor-asm-{plan_id}", "from": node_editor, "to": node_asm})
    yield _sse({"node": "assembler", "status": "in-progress", "data": {"message": "Assembling final video + CapCut draft..."}})
    yield _emit_state()

    final_url = None
    capcut_info = None
    try:
        from .video_assembler import assemble_dual_output

        # Download clips from S3 URLs to local paths for FFmpeg
        local_clips = await _download_clips(scene_clips, plan_id)

        result = await assemble_dual_output(
            scene_clips=local_clips,
            scenes=scenes[:clip_count],
            draft_name=f"v3_{plan_id}",
            width=width,
            height=height,
        )

        mp4_path = result.get("mp4_path")
        capcut_info = result.get("capcut_draft")

        if mp4_path and os.path.exists(mp4_path):
            s3_key = f"generated_ads/{project_id}/{task_id}/v3/{plan_id}/final_video.mp4"
            final_url = upload_file_public(mp4_path, s3_key)

        nodes[-1] = _node_dict(
            node_asm, "done", "Video Assembler", x=1600, y=200,
            output=final_url,
            props={"mp4_url": final_url, "capcut_draft": capcut_info, "has_capcut": bool(capcut_info)},
        )
    except Exception as e:
        logger.error("[V3Grid] Assembly failed: %s", e)
        nodes[-1] = _node_dict(node_asm, "failed", "Video Assembler", x=1600, y=200, error=str(e))

    yield _sse({"node": "assembler", "status": "completed" if final_url else "failed", "data": {
        "mp4_url": final_url, "capcut_draft": capcut_info,
    }})
    yield _emit_state()

    logger.info("[V3Grid] Pipeline complete: %d nodes, %d clips, final=%s", len(nodes), len(scene_clips), bool(final_url))


# ─── Helper Functions ─────────────────────────────────────────────────────────


def _slice_grid(grid_path: str, cols: int, rows: int, total_frames: int, plan_id: str) -> list[str]:
    """Slice a grid image into individual frames using PIL.

    Reads left-to-right, top-to-bottom. Extracts exactly total_frames cells.
    """
    from PIL import Image

    img = Image.open(grid_path)
    w, h = img.size
    cell_w = w // cols
    cell_h = h // rows

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


async def _generate_clip_first_last(
    first_frame_path: str,
    last_frame_path: str,
    prompt: str,
    scene_index: int,
    plan_id: str,
    project_id: str,
    task_id: str,
) -> Optional[str]:
    """Generate a video clip using Veo's first+last frame mode.

    This ensures smooth motion FROM the first frame TO the last frame,
    maintaining character consistency between keyframes.

    Returns S3 URL of the clip, or None on failure.
    """
    from google.genai import types as genai_types

    if not gemini:
        logger.error("[V3Grid] Gemini client unavailable")
        return None

    try:
        with open(first_frame_path, "rb") as f:
            first_bytes = f.read()
        with open(last_frame_path, "rb") as f:
            last_bytes = f.read()

        # Veo first+last frame mode
        operation = gemini.models.generate_videos(
            model=_VEO_MODEL,
            prompt=prompt[:500],
            image=genai_types.Image(image_bytes=first_bytes, mime_type="image/png"),
            config=genai_types.GenerateVideoConfig(
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
            operation = gemini.models.get_operation(operation)

        if not operation.done:
            logger.error("[V3Grid] Clip %d: Veo timed out (%ds)", scene_index, _VEO_MAX_WAIT)
            return None

        result = operation.result
        if not result or not result.generated_videos:
            logger.error("[V3Grid] Clip %d: no video returned", scene_index)
            return None

        video = result.generated_videos[0].video
        if not video:
            return None

        # Save and upload
        clip_path = os.path.join(tempfile.gettempdir(), f"clip_{plan_id}_{scene_index:02d}.mp4")
        with open(clip_path, "wb") as f:
            f.write(video.video_bytes)

        s3_key = f"generated_ads/{project_id}/{task_id}/v3/{plan_id}/clip_{scene_index:02d}.mp4"
        clip_url = upload_file_public(clip_path, s3_key)
        logger.info("[V3Grid] Clip %d: first→last frame (%ds) → %s", scene_index, _SCENE_CLIP_SECONDS, clip_url)
        return clip_url

    except Exception as e:
        logger.error("[V3Grid] Veo first+last frame failed for clip %d: %s", scene_index, e)
        return None


async def _download_clips(clip_urls: list[str], plan_id: str) -> list[str]:
    """Download S3 clip URLs to local temp files for FFmpeg assembly."""
    import urllib.request

    local_paths = []
    for i, url in enumerate(clip_urls):
        try:
            local_path = os.path.join(tempfile.gettempdir(), f"dl_clip_{plan_id}_{i:02d}.mp4")
            urllib.request.urlretrieve(url, local_path)
            local_paths.append(local_path)
        except Exception as e:
            logger.warning("[V3Grid] Failed to download clip %d: %s", i, e)

    return local_paths
