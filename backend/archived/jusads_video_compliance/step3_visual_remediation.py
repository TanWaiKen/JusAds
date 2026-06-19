"""
Step 3: Visual Remediation
============================
For each visual violation:
  1. Extract start/end frames from video (FFmpeg)
  2. Regenerate frames to be compliant (Gemini Flash Image)
  3. Generate replacement clip (Veo 3.1 Lite)
  4. Speed adjust if needed
"""

import logging
import os
import time

from jusads_video_compliance.visual_remediator import (
    extract_frame,
    regenerate_frame,
    generate_replacement_clip,
    speed_adjust_clip,
    build_compliance_prompt,
    VEO_MIN_DURATION_SECONDS,
)

logger = logging.getLogger(__name__)

# Delay between Gemini API calls to avoid 429 rate limits
API_DELAY_SECONDS = 5


async def remediate_visual(video_path: str, violations: list[dict], output_dir: str) -> list[dict]:
    """
    Remediate all visual violations.

    Args:
        video_path: Path to the source video.
        violations: List of visual violation dicts from Step 2.
        output_dir: Directory to save output files.

    Returns:
        List of result dicts with: success, original_start, original_end,
        original_frames, edited_frames, clip_path, error.
    """
    results = []

    for i, v in enumerate(violations):
        print(f"  [{i+1}/{len(violations)}] Fixing visual: {v['description'][:50]}...")
        result = await _fix_one_visual(video_path, v, output_dir, i)
        results.append(result)

        # Delay between violations to avoid rate limits
        if i < len(violations) - 1:
            time.sleep(API_DELAY_SECONDS)

    return results


async def _fix_one_visual(video_path: str, violation: dict, output_dir: str, index: int) -> dict:
    """Fix a single visual violation."""
    import uuid

    start = violation["start"]
    end = violation["end"]
    segment_duration = end - start
    frame_id = uuid.uuid4().hex[:8]

    # 1. Extract frames
    frame_start = os.path.join(output_dir, f"original_start_{frame_id}.png")
    frame_end = os.path.join(output_dir, f"original_end_{frame_id}.png")

    if not extract_frame(video_path, start, frame_start):
        return _fail(start, end, "Failed to extract start frame")

    if not extract_frame(video_path, end, frame_end):
        return _fail(start, end, "Failed to extract end frame")

    # 2. Regenerate frames (with delay between calls)
    prompt = build_compliance_prompt(violation["category"], violation["description"])

    try:
        edited_start = await regenerate_frame(frame_start, prompt)
    except RuntimeError as e:
        return _fail(start, end, f"Frame regen failed: {e}")

    time.sleep(API_DELAY_SECONDS)

    try:
        edited_end = await regenerate_frame(frame_end, prompt)
    except RuntimeError as e:
        return _fail(start, end, f"Frame regen failed: {e}")

    # 3. Generate replacement clip with Veo
    veo_duration = max(VEO_MIN_DURATION_SECONDS, segment_duration)

    try:
        clip_path = await generate_replacement_clip(edited_start, edited_end, veo_duration)
    except RuntimeError as e:
        return _fail(start, end, f"Veo clip failed: {e}")

    # 4. Speed adjust if segment < 4 seconds
    final_clip = clip_path
    if segment_duration < VEO_MIN_DURATION_SECONDS:
        adjusted_path = os.path.join(output_dir, f"adjusted_{frame_id}.mp4")
        try:
            final_clip = speed_adjust_clip(clip_path, segment_duration, adjusted_path)
        except (ValueError, RuntimeError) as e:
            return _fail(start, end, f"Speed adjust failed: {e}")

    return {
        "success": True,
        "original_start": start,
        "original_end": end,
        "original_frames": [frame_start, frame_end],
        "edited_frames": [edited_start, edited_end],
        "clip_path": final_clip,
        "error": None,
    }


def _fail(start: float, end: float, error: str) -> dict:
    """Return a failure result."""
    logger.error(error)
    return {
        "success": False,
        "original_start": start,
        "original_end": end,
        "original_frames": [],
        "edited_frames": [],
        "clip_path": "",
        "error": error,
    }
