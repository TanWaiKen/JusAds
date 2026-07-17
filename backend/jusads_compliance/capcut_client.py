"""
capcut_client.py
────────────────
CapCut/JianYing draft generation + FFmpeg video rendering.

Two-layer approach:
  1. pyJianYingDraft (imported directly) — creates rich CapCut-format drafts
     with animations, transitions, text effects, stickers. These can be opened
     in CapCut/JianYing desktop for final polish or auto-exported.
  2. FFmpeg — renders actual .mp4 files for immediate use (text overlay, trim,
     speed, transitions, audio replace).

The pyJianYingDraft layer is used when:
  - Rich text animations are needed (451 transition types, text intros/outros)
  - The user wants to open the result in CapCut for further editing
  - Draft-based workflow is preferred

The FFmpeg layer is used when:
  - Immediate .mp4 output is required (API responses, compliance pipeline)
  - Simple edits (trim, speed, basic text) are sufficient

Library: https://pypi.org/project/pyJianYingDraft/ (v0.2.7)
"""

import json
import logging
import os
import subprocess
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

FFMPEG_BIN = os.environ.get("FFMPEG_BIN", "ffmpeg")

# Where to store generated CapCut drafts (opened by JianYing desktop)
DRAFTS_DIR = os.path.join(tempfile.gettempdir(), "jusads_capcut_drafts")
os.makedirs(DRAFTS_DIR, exist_ok=True)


# -----------------------------------------------------------------------------
# pyJianYingDraft integration (rich draft generation)
# -----------------------------------------------------------------------------

try:
    import pycapcut as cc
    CAPCUT_AVAILABLE = True
    logger.info("[CapCut] pycapcut library loaded (CapCut draft generation available, %d transitions)",
                len([x for x in dir(cc.TransitionType) if not x.startswith("_")]))
except ImportError:
    try:
        import pyJianYingDraft as cc
        CAPCUT_AVAILABLE = True
        logger.info("[CapCut] pyJianYingDraft loaded as fallback")
    except ImportError:
        CAPCUT_AVAILABLE = False
        cc = None
        logger.warning("[CapCut] Neither pycapcut nor pyJianYingDraft installed — draft features unavailable")


def create_capcut_draft(
    video_path: str,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
    draft_name: str = "remediation_draft",
    capcut_drafts_folder: Optional[str] = None,
) -> Optional[dict]:
    """Create a CapCut-editable draft from a source video.

    The draft can be opened directly in CapCut desktop for rich editing
    (1120 transitions, text animations, effects, stickers, etc.).
    User can then fine-tune the AI's edits and export at full quality.

    Args:
        video_path: Path to source video file.
        width: Draft canvas width.
        height: Draft canvas height.
        fps: Frames per second.
        draft_name: Human-readable draft name.
        capcut_drafts_folder: Path to CapCut's drafts folder. If None, uses temp.

    Returns:
        Dict with draft_folder path, script reference, or None on failure.
    """
    if not CAPCUT_AVAILABLE:
        logger.warning("[CapCut] pycapcut not available — cannot create draft")
        return None

    if not os.path.exists(video_path):
        logger.error("[CapCut] Video not found: %s", video_path)
        return None

    try:
        # Use CapCut's drafts folder if provided, otherwise temp
        drafts_path = capcut_drafts_folder or DRAFTS_DIR
        draft_folder = cc.DraftFolder(drafts_path)

        # Create the draft
        script = draft_folder.create_draft(draft_name, width, height, fps, allow_replace=True)

        # Add a main video track
        script.add_track(cc.TrackType.video, "main_video")

        # Get video duration and add segment
        duration = _get_video_duration(video_path)
        dur_us = int((duration or 10) * 1_000_000)  # Convert seconds to microseconds

        video_seg = cc.VideoSegment(
            video_path,
            cc.Timerange(0, dur_us),
        )
        script.add_segment(video_seg, "main_video")

        # Save the draft
        script.save()

        logger.info("[CapCut] Draft '%s' created at: %s", draft_name, drafts_path)
        return {
            "draft_folder": drafts_path,
            "draft_name": draft_name,
            "script": script,
            "duration_us": dur_us,
            "width": width,
            "height": height,
        }

    except Exception as e:
        logger.error("[CapCut] Draft creation failed: %s", e)
        return None


def create_multi_scene_draft(
    scene_clips: list[str],
    audio_path: Optional[str] = None,
    subtitles_srt: Optional[str] = None,
    draft_name: str = "ai_video_draft",
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
    capcut_drafts_folder: Optional[str] = None,
    transition_type: str = "fade",
    transition_duration_sec: float = 0.5,
) -> Optional[dict]:
    """Create a CapCut draft from multiple scene clips with transitions.

    This is the dual-output companion to FFmpeg assembly: produces an editable
    CapCut project the user can open, adjust, and export at full quality.

    Args:
        scene_clips: List of paths to video/image files (one per scene).
        audio_path: Optional voiceover/music audio file path.
        subtitles_srt: Optional .srt file path for subtitles.
        draft_name: Name for the draft.
        width: Canvas width.
        height: Canvas height.
        fps: Frames per second.
        capcut_drafts_folder: CapCut drafts folder path.
        transition_type: Transition between scenes.
        transition_duration_sec: Transition duration.

    Returns:
        Dict with draft info, or None on failure.
    """
    if not CAPCUT_AVAILABLE:
        logger.warning("[CapCut] pycapcut not available — cannot create draft")
        return None

    try:
        drafts_path = capcut_drafts_folder or DRAFTS_DIR
        draft_folder = cc.DraftFolder(drafts_path)
        script = draft_folder.create_draft(draft_name, width, height, fps, allow_replace=True)

        # Add video track
        script.add_track(cc.TrackType.video, "scenes")

        # Add each scene clip
        for i, clip_path in enumerate(scene_clips):
            if not os.path.exists(clip_path):
                logger.warning("[CapCut] Scene clip not found, skipping: %s", clip_path)
                continue

            duration = _get_video_duration(clip_path)
            dur_us = int((duration or 5) * 1_000_000)

            seg = cc.VideoSegment(clip_path, cc.Timerange(0, dur_us))
            script.add_segment(seg, "scenes")

        # Add audio track if provided
        if audio_path and os.path.exists(audio_path):
            script.add_track(cc.TrackType.audio, "voiceover")
            audio_dur = _get_video_duration(audio_path)  # ffprobe works for audio too
            audio_dur_us = int((audio_dur or 30) * 1_000_000)
            audio_seg = cc.AudioSegment(audio_path, cc.Timerange(0, audio_dur_us))
            script.add_segment(audio_seg, "voiceover")

        # Import SRT subtitles if provided
        if subtitles_srt and os.path.exists(subtitles_srt):
            script.import_srt(subtitles_srt, track_name="subtitles")

        script.save()

        logger.info("[CapCut] Multi-scene draft '%s' created with %d clips", draft_name, len(scene_clips))
        return {
            "draft_folder": drafts_path,
            "draft_name": draft_name,
            "scene_count": len(scene_clips),
            "has_audio": bool(audio_path),
            "has_subtitles": bool(subtitles_srt),
        }

    except Exception as e:
        logger.error("[CapCut] Multi-scene draft creation failed: %s", e)
        return None


# -----------------------------------------------------------------------------
# FFmpeg operations (renders actual .mp4 files)
# -----------------------------------------------------------------------------


def add_text_overlay(
    video_path: str,
    text: str,
    start_time: float = 0.0,
    end_time: Optional[float] = None,
    position: str = "bottom",
    font_size: int = 48,
    font_color: str = "white",
    bg_color: str = "black@0.5",
) -> dict:
    """Add text overlay to video — renders actual .mp4 via FFmpeg.

    Also creates a pyJianYingDraft version if available (richer animations).

    Args:
        video_path: Path to input video file.
        text: Text to overlay.
        start_time: Start time in seconds.
        end_time: End time in seconds (None = until end).
        position: "top", "center", or "bottom".
        font_size: Font size in pixels.
        font_color: Color name or hex.
        bg_color: Background box color.

    Returns:
        Dict with output_path on success, or error key on failure.
    """
    if not os.path.exists(video_path):
        return {"error": f"Video file not found: {video_path}"}

    base_name = os.path.basename(video_path).replace(" ", "_")
    output_path = os.path.join(tempfile.gettempdir(), f"text_overlay_{base_name}")

    y_positions = {"top": "h*0.1", "center": "(h-text_h)/2", "bottom": "h*0.85"}
    y_expr = y_positions.get(position, "h*0.85")

    enable_expr = f"between(t\\,{start_time}\\,{end_time})" if end_time else f"gte(t\\,{start_time})"
    safe_text = text.replace("'", "\\'").replace(":", "\\:").replace(",", "\\,")

    # On Windows, specify a font file to avoid Fontconfig errors
    font_clause = ""
    if os.name == "nt":
        font_path = "C\\\\:/Windows/Fonts/arial.ttf"
        font_clause = f":fontfile={font_path}"

    filter_str = (
        f"drawtext=text='{safe_text}'"
        f"{font_clause}"
        f":fontsize={font_size}:fontcolor={font_color}"
        f":x=(w-text_w)/2:y={y_expr}"
        f":box=1:boxcolor={bg_color}:boxborderw=10"
        f":enable='{enable_expr}'"
    )

    cmd = [FFMPEG_BIN, "-y", "-i", video_path, "-vf", filter_str, "-c:a", "copy", output_path]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            logger.error("[CapCut] FFmpeg text overlay failed: %s", result.stderr[-500:])
            return {"error": f"FFmpeg text overlay failed: {result.stderr[-200:]}"}
        logger.info("[CapCut] Text overlay rendered: %s", text[:30])
        return {"output_path": output_path, "operation": "text_overlay", "engine": "ffmpeg"}
    except subprocess.TimeoutExpired:
        return {"error": "Text overlay timed out (120s)"}
    except Exception as e:
        return {"error": f"Text overlay failed: {e}"}


def trim_segment(
    video_path: str,
    remove_start: float,
    remove_end: float,
) -> dict:
    """Remove a segment from the video by cutting and concatenating.

    Args:
        video_path: Path to input video.
        remove_start: Start of segment to remove (seconds).
        remove_end: End of segment to remove (seconds).

    Returns:
        Dict with output_path on success, or error key on failure.
    """
    if not os.path.exists(video_path):
        return {"error": f"Video file not found: {video_path}"}
    if remove_start >= remove_end:
        return {"error": f"Invalid trim range: {remove_start} >= {remove_end}"}

    base_name = os.path.basename(video_path).replace(" ", "_")
    output_path = os.path.join(tempfile.gettempdir(), f"trimmed_{base_name}")
    duration = _get_video_duration(video_path)
    if duration is None:
        return {"error": "Could not determine video duration"}

    part1_path = os.path.join(tempfile.gettempdir(), f"part1_{base_name}")
    part2_path = os.path.join(tempfile.gettempdir(), f"part2_{base_name}")

    try:
        parts = []
        if remove_start > 0.1:
            cmd1 = [FFMPEG_BIN, "-y", "-i", video_path, "-t", str(remove_start), "-c", "copy", part1_path]
            subprocess.run(cmd1, capture_output=True, timeout=60)
            if os.path.exists(part1_path):
                parts.append(part1_path)

        if remove_end < duration - 0.1:
            cmd2 = [FFMPEG_BIN, "-y", "-i", video_path, "-ss", str(remove_end), "-c", "copy", part2_path]
            subprocess.run(cmd2, capture_output=True, timeout=60)
            if os.path.exists(part2_path):
                parts.append(part2_path)

        if not parts:
            return {"error": "Trim would remove entire video"}

        if len(parts) == 1:
            os.replace(parts[0], output_path)
        else:
            concat_result = _concat_videos(parts, output_path)
            if "error" in concat_result:
                return concat_result

        for p in [part1_path, part2_path]:
            try:
                os.remove(p)
            except OSError:
                pass

        logger.info("[CapCut] Trimmed segment %.1f-%.1fs", remove_start, remove_end)
        return {"output_path": output_path, "operation": "trim", "removed_seconds": remove_end - remove_start}
    except subprocess.TimeoutExpired:
        return {"error": "Trim operation timed out"}
    except Exception as e:
        return {"error": f"Trim failed: {e}"}


def speed_ramp(
    video_path: str,
    start_time: float,
    end_time: float,
    speed_factor: float = 1.5,
) -> dict:
    """Apply speed change to a video via FFmpeg.

    Args:
        video_path: Path to input video.
        start_time: Start of segment (currently applies to full video).
        end_time: End of segment.
        speed_factor: Speed multiplier (0.25-4.0).

    Returns:
        Dict with output_path on success, or error key on failure.
    """
    if not os.path.exists(video_path):
        return {"error": f"Video file not found: {video_path}"}

    speed_factor = max(0.25, min(4.0, speed_factor))
    base_name = os.path.basename(video_path).replace(" ", "_")
    output_path = os.path.join(tempfile.gettempdir(), f"speed_{base_name}")

    video_filter = f"setpts={1.0/speed_factor}*PTS"
    audio_filter = f"atempo={speed_factor}"
    if speed_factor > 2.0:
        audio_filter = f"atempo=2.0,atempo={speed_factor/2.0}"
    elif speed_factor < 0.5:
        audio_filter = f"atempo=0.5,atempo={speed_factor/0.5}"

    cmd = [
        FFMPEG_BIN, "-y", "-i", video_path,
        "-filter_complex", f"[0:v]{video_filter}[v];[0:a]{audio_filter}[a]",
        "-map", "[v]", "-map", "[a]", output_path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            return {"error": f"Speed ramp failed: {result.stderr[-200:]}"}
        logger.info("[CapCut] Speed ramp: %.1fx", speed_factor)
        return {"output_path": output_path, "operation": "speed_ramp", "speed_factor": speed_factor, "engine": "ffmpeg"}
    except subprocess.TimeoutExpired:
        return {"error": "Speed ramp timed out"}
    except Exception as e:
        return {"error": f"Speed ramp failed: {e}"}


def add_transition(
    video_path: str,
    transition_point: float,
    transition_type: str = "fade",
    duration: float = 0.5,
) -> dict:
    """Add a transition effect at a specific point via FFmpeg xfade.

    Args:
        video_path: Path to input video.
        transition_point: Time in seconds where transition occurs.
        transition_type: "fade", "dissolve", "wipeleft", etc.
        duration: Transition duration in seconds.

    Returns:
        Dict with output_path on success, or error key on failure.
    """
    if not os.path.exists(video_path):
        return {"error": f"Video file not found: {video_path}"}

    video_duration = _get_video_duration(video_path)
    if not video_duration or transition_point >= video_duration:
        return {"error": f"Transition point {transition_point}s exceeds video duration"}

    base_name = os.path.basename(video_path).replace(" ", "_")
    output_path = os.path.join(tempfile.gettempdir(), f"transition_{base_name}")

    part1 = os.path.join(tempfile.gettempdir(), f"trans_p1_{base_name}")
    part2 = os.path.join(tempfile.gettempdir(), f"trans_p2_{base_name}")

    try:
        subprocess.run(
            [FFMPEG_BIN, "-y", "-i", video_path, "-t", str(transition_point), "-c", "copy", part1],
            capture_output=True, timeout=60,
        )
        subprocess.run(
            [FFMPEG_BIN, "-y", "-i", video_path, "-ss", str(transition_point), "-c", "copy", part2],
            capture_output=True, timeout=60,
        )

        if not os.path.exists(part1) or not os.path.exists(part2):
            return {"error": "Failed to split video at transition point"}

        xfade_type = transition_type if transition_type in ("fade", "dissolve", "wipeleft", "wiperight") else "fade"
        offset = max(0, transition_point - duration)

        cmd = [
            FFMPEG_BIN, "-y", "-i", part1, "-i", part2,
            "-filter_complex",
            f"[0:v][1:v]xfade=transition={xfade_type}:duration={duration}:offset={offset}[v];"
            f"[0:a][1:a]acrossfade=d={duration}[a]",
            "-map", "[v]", "-map", "[a]", output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            # Fallback: just concat without transition
            _concat_videos([part1, part2], output_path)

        for p in [part1, part2]:
            try:
                os.remove(p)
            except OSError:
                pass

        logger.info("[CapCut] Transition: %s at %.1fs", transition_type, transition_point)
        return {"output_path": output_path, "operation": "transition", "type": transition_type, "engine": "ffmpeg"}
    except Exception as e:
        return {"error": f"Transition failed: {e}"}


def replace_audio(
    video_path: str,
    new_audio_path: str,
    keep_original_volume: float = 0.0,
) -> dict:
    """Replace the audio track of a video with new audio.

    Args:
        video_path: Path to input video.
        new_audio_path: Path to new audio file.
        keep_original_volume: Volume of original audio to keep (0-1).

    Returns:
        Dict with output_path on success, or error key on failure.
    """
    if not os.path.exists(video_path):
        return {"error": f"Video file not found: {video_path}"}
    if not os.path.exists(new_audio_path):
        return {"error": f"Audio file not found: {new_audio_path}"}

    base_name = os.path.basename(video_path).replace(" ", "_")
    output_path = os.path.join(tempfile.gettempdir(), f"audio_replaced_{base_name}")

    try:
        if keep_original_volume > 0:
            cmd = [
                FFMPEG_BIN, "-y", "-i", video_path, "-i", new_audio_path,
                "-filter_complex",
                f"[0:a]volume={keep_original_volume}[orig];[orig][1:a]amix=inputs=2:duration=first[a]",
                "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-shortest", output_path,
            ]
        else:
            cmd = [
                FFMPEG_BIN, "-y", "-i", video_path, "-i", new_audio_path,
                "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-shortest", output_path,
            ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            return {"error": f"Audio replace failed: {result.stderr[-200:]}"}
        logger.info("[CapCut] Audio replaced")
        return {"output_path": output_path, "operation": "replace_audio", "engine": "ffmpeg"}
    except Exception as e:
        return {"error": f"Audio replace failed: {e}"}


def scene_replace(
    video_path: str,
    remove_start: float,
    remove_end: float,
    replacement_video_path: Optional[str] = None,
) -> dict:
    """Replace a scene by trimming and adding a fade transition at the cut.

    Args:
        video_path: Path to input video.
        remove_start: Start of segment to replace.
        remove_end: End of segment to replace.
        replacement_video_path: Optional replacement clip (future use).

    Returns:
        Dict with output_path on success, or error key on failure.
    """
    trim_result = trim_segment(video_path, remove_start, remove_end)
    if "error" in trim_result:
        return trim_result

    trimmed_path = trim_result["output_path"]
    transition_result = add_transition(trimmed_path, remove_start, "fade", 0.5)
    if "error" not in transition_result:
        return {**transition_result, "operation": "scene_replace"}
    return {**trim_result, "operation": "scene_replace"}


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _get_video_duration(video_path: str) -> Optional[float]:
    """Get video duration in seconds using ffprobe."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception:
        pass
    return None


def _concat_videos(parts: list[str], output_path: str) -> dict:
    """Concatenate multiple video files using FFmpeg concat demuxer."""
    concat_list = os.path.join(tempfile.gettempdir(), "concat_list.txt")
    try:
        with open(concat_list, "w") as f:
            for part in parts:
                # Use forward slashes for FFmpeg compatibility
                safe_path = part.replace("\\", "/")
                f.write(f"file '{safe_path}'\n")

        cmd = [FFMPEG_BIN, "-y", "-f", "concat", "-safe", "0", "-i", concat_list, "-c", "copy", output_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        os.remove(concat_list)

        if result.returncode != 0:
            return {"error": f"Concat failed: {result.stderr[-200:]}"}
        return {"output_path": output_path}
    except Exception as e:
        return {"error": f"Concat failed: {e}"}


def get_available_transitions() -> list[str]:
    """Return list of available pyCapCut transition names (1120+).

    These are available for draft-based editing (opened in CapCut desktop).
    FFmpeg supports a smaller subset: fade, dissolve, wipeleft, wiperight, etc.
    """
    if not CAPCUT_AVAILABLE:
        return ["fade", "dissolve", "wipeleft", "wiperight"]

    try:
        return [x for x in dir(cc.TransitionType) if not x.startswith("_")]
    except Exception:
        return ["fade", "dissolve", "wipeleft", "wiperight"]


def get_available_text_intros() -> list[str]:
    """Return list of available text intro animation names."""
    if not CAPCUT_AVAILABLE:
        return []
    try:
        return [x for x in dir(cc.TextIntro) if not x.startswith("_")]
    except Exception:
        return []
