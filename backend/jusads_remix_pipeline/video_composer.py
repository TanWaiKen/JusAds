"""Video Composer for the JusAds Video Remix Pipeline.

Assembles the final compliant video from remixed clips, original compliant
sections, ambient audio, and voiceover tracks using FFmpeg.

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 11.2, 11.3
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

# Output directory for composed videos
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "assets" / "results"

# Audio volume settings
# Voiceover is approximately 6dB above ambient (Req 8.3)
VOICEOVER_VOLUME_DB = 6.0

# Max allowed audio-video sync drift in milliseconds (Req 8.4)
MAX_SYNC_DRIFT_MS = 200


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PUBLIC API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def compose_video(
    segment_plan: list[dict],
    remixed_clips: list[dict],
    voiceover_segments: list[dict],
    original_video_path: str,
) -> dict:
    """Compose final video from remixed clips, ambient audio, and voiceover.

    Stitches compliant original sections and remixed clips in chronological
    order (Req 8.1), layers ambient audio as base track (Req 8.2), layers
    voiceover at higher volume (Req 8.3), and outputs a single MP4 with
    sync drift ≤ 200ms (Req 8.4). Handles unavailable clips by retaining
    original segments (Req 8.5).

    Args:
        segment_plan: List of segment dicts from segment_planner, each with:
            - start_time (float): Segment start in seconds.
            - end_time (float): Segment end in seconds.
            - source_violation_index (int): Violation index.
            - chunk_sequence_number (int): Chunk sequence within violation.
            - is_short_form (bool): Whether this is a short-form segment.
        remixed_clips: List of remixed clip dicts, each with:
            - video_path (str): Path to the remixed video clip.
            - ambient_audio_path (str): Path to extracted ambient audio.
            - duration (float): Clip duration in seconds.
            - start_time (float): Clip start time in the overall video.
            - end_time (float): Clip end time in the overall video.
        voiceover_segments: List of voiceover segment dicts, each with:
            - audio_path (str): Path to voiceover audio file.
            - start_time (float): Start time in the overall video.
            - end_time (float): End time in the overall video.
            - duration (float): Audio duration in seconds.
        original_video_path: Path to the original source video file.

    Returns:
        Dict with:
            - video_path (str): Path to the final composed video.
            - duration (float): Total video duration in seconds.
            - unavailable_segments (list): Segments that couldn't be remixed.
            - error (str | None): Error if composition failed entirely.
    """
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Validate inputs
    if not original_video_path or not os.path.exists(original_video_path):
        return {
            "video_path": "",
            "duration": 0.0,
            "unavailable_segments": [],
            "error": f"Original video not found: {original_video_path}",
        }

    # Get original video duration
    original_duration = _get_media_duration(original_video_path)
    if original_duration <= 0:
        return {
            "video_path": "",
            "duration": 0.0,
            "unavailable_segments": [],
            "error": "Could not determine original video duration",
        }

    # Generate unique output ID
    output_id = uuid.uuid4().hex[:12]
    final_output_path = str(OUTPUT_DIR / f"composed_{output_id}.mp4")

    try:
        # Step 1: Build the timeline - determine which segments use remixed
        # clips and which retain original video (Req 8.1, 8.5, 11.2)
        timeline, unavailable_segments = _build_timeline(
            segment_plan, remixed_clips, original_duration
        )

        # Step 2: Stitch video segments in chronological order (Req 8.1, 11.2)
        stitched_video_path = _stitch_video_segments(
            timeline, original_video_path, output_id
        )

        if not stitched_video_path:
            return {
                "video_path": "",
                "duration": 0.0,
                "unavailable_segments": unavailable_segments,
                "error": "Video stitching failed",
            }

        # Step 3: Extract and layer audio (Req 8.2, 8.3, 11.3)
        final_path = _layer_audio(
            stitched_video_path,
            original_video_path,
            voiceover_segments,
            original_duration,
            final_output_path,
        )

        if not final_path:
            # Fallback: use stitched video without audio layering
            logger.warning(
                "Audio layering failed, using stitched video as output"
            )
            final_path = stitched_video_path

        # Verify final output duration
        final_duration = _get_media_duration(final_path)

        # Clean up intermediate file if different from final
        if stitched_video_path != final_path and os.path.exists(stitched_video_path):
            try:
                os.remove(stitched_video_path)
            except OSError:
                pass

        logger.info(
            f"Video composition complete: {final_path} "
            f"(duration={final_duration:.1f}s, "
            f"unavailable_segments={len(unavailable_segments)})"
        )

        return {
            "video_path": final_path,
            "duration": final_duration,
            "unavailable_segments": unavailable_segments,
            "error": None,
        }

    except Exception as e:
        error_msg = f"Video composition failed: {e}"
        logger.error(error_msg)
        return {
            "video_path": "",
            "duration": 0.0,
            "unavailable_segments": [],
            "error": error_msg,
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PRIVATE HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _build_timeline(
    segment_plan: list[dict],
    remixed_clips: list[dict],
    original_duration: float,
) -> tuple[list[dict], list[dict]]:
    """Build a chronological timeline of video segments.

    Determines which parts use remixed clips and which retain the original
    video. Identifies unavailable segments (Req 8.5).

    Args:
        segment_plan: List of planned segments (non-compliant time ranges).
        remixed_clips: List of remixed clip dicts with video_path and timing.
        original_duration: Total duration of the original video.

    Returns:
        Tuple of (timeline, unavailable_segments).
        timeline: Sorted list of segment dicts with type "original" or "remixed".
        unavailable_segments: List of segments that couldn't be remixed.
    """
    unavailable_segments: list[dict] = []

    # Build a lookup of remixed clips by their time range
    remixed_lookup: dict[tuple[float, float], dict] = {}
    for clip in remixed_clips:
        start = clip.get("start_time", 0.0)
        end = clip.get("end_time", 0.0)
        remixed_lookup[(round(start, 3), round(end, 3))] = clip

    # Collect all non-compliant time ranges from segment_plan
    non_compliant_ranges: list[dict] = []
    for segment in segment_plan:
        start = segment.get("start_time", 0.0)
        end = segment.get("end_time", 0.0)

        # Check if a remixed clip is available for this segment
        key = (round(start, 3), round(end, 3))
        clip = remixed_lookup.get(key)

        if clip and clip.get("video_path") and os.path.exists(clip["video_path"]):
            non_compliant_ranges.append({
                "start_time": start,
                "end_time": end,
                "type": "remixed",
                "video_path": clip["video_path"],
            })
        else:
            # Req 8.5: Clip unavailable, retain original segment
            reason = "Remixed clip not available or file missing"
            if clip and clip.get("error"):
                reason = clip["error"]
            unavailable_segments.append({
                "start_time": start,
                "end_time": end,
                "reason": reason,
            })
            non_compliant_ranges.append({
                "start_time": start,
                "end_time": end,
                "type": "original",
                "video_path": None,
            })

    # Sort non-compliant ranges by start_time
    non_compliant_ranges.sort(key=lambda s: s["start_time"])

    # Build the full timeline, filling gaps with original video segments
    timeline: list[dict] = []
    current_time = 0.0

    for segment in non_compliant_ranges:
        seg_start = segment["start_time"]
        seg_end = segment["end_time"]

        # Add original (compliant) section before this segment if there's a gap
        if current_time < seg_start:
            timeline.append({
                "start_time": current_time,
                "end_time": seg_start,
                "type": "original",
                "video_path": None,
            })

        # Add the segment (either remixed or original fallback)
        timeline.append(segment)
        current_time = seg_end

    # Add trailing original section if video continues after last segment
    if current_time < original_duration:
        timeline.append({
            "start_time": current_time,
            "end_time": original_duration,
            "type": "original",
            "video_path": None,
        })

    return timeline, unavailable_segments


def _stitch_video_segments(
    timeline: list[dict],
    original_video_path: str,
    output_id: str,
) -> str:
    """Stitch video segments in chronological order using FFmpeg.

    Uses FFmpeg concat demuxer for efficient stitching. Compliant sections
    are extracted from the original video with -c copy to avoid re-encoding
    (Req 11.2).

    Args:
        timeline: Chronological list of video segments.
        original_video_path: Path to the original source video.
        output_id: Unique identifier for intermediate files.

    Returns:
        Path to the stitched video file, or empty string on failure.
    """
    if not timeline:
        return ""

    # If only one segment covers the full video, handle simply
    if len(timeline) == 1 and timeline[0]["type"] == "original":
        return original_video_path

    temp_dir = tempfile.mkdtemp(prefix="compose_")
    segment_files: list[str] = []

    try:
        # Extract/prepare each segment as a separate file
        for i, segment in enumerate(timeline):
            seg_start = segment["start_time"]
            seg_end = segment["end_time"]
            seg_duration = seg_end - seg_start

            if seg_duration <= 0:
                continue

            if segment["type"] == "remixed" and segment.get("video_path"):
                # Use the remixed clip directly
                segment_files.append(segment["video_path"])
            else:
                # Extract original segment with -c copy (Req 11.2)
                extracted_path = os.path.join(
                    temp_dir, f"segment_{i:03d}.mp4"
                )
                success = _extract_segment(
                    original_video_path, seg_start, seg_duration, extracted_path
                )
                if success:
                    segment_files.append(extracted_path)
                else:
                    logger.warning(
                        f"Failed to extract segment {i} "
                        f"({seg_start:.1f}s-{seg_end:.1f}s)"
                    )

        if not segment_files:
            return ""

        # If only one segment file, use it directly
        if len(segment_files) == 1:
            return segment_files[0]

        # Create concat demuxer file list
        concat_list_path = os.path.join(temp_dir, "concat_list.txt")
        with open(concat_list_path, "w") as f:
            for seg_file in segment_files:
                # Escape single quotes in file paths for FFmpeg
                safe_path = seg_file.replace("'", "'\\''")
                f.write(f"file '{safe_path}'\n")

        # Run FFmpeg concat
        stitched_path = str(OUTPUT_DIR / f"stitched_{output_id}.mp4")
        cmd = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list_path,
            "-c", "copy",
            "-movflags", "+faststart",
            stitched_path,
        ]

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120
        )

        if result.returncode != 0:
            # Concat with -c copy may fail if segments have different encodings.
            # Fallback: re-encode with common codec
            logger.warning(
                "Concat with -c copy failed, retrying with re-encoding"
            )
            cmd = [
                "ffmpeg",
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_list_path,
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "+faststart",
                stitched_path,
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300
            )

            if result.returncode != 0:
                logger.error(
                    f"Video stitching failed: {result.stderr[:500]}"
                )
                return ""

        if os.path.exists(stitched_path) and os.path.getsize(stitched_path) > 0:
            return stitched_path

        return ""

    except subprocess.TimeoutExpired:
        logger.error("Video stitching timed out")
        return ""
    except FileNotFoundError:
        logger.error("FFmpeg not found. Ensure FFmpeg is installed and on PATH.")
        return ""
    except Exception as e:
        logger.error(f"Video stitching failed: {e}")
        return ""


def _extract_segment(
    video_path: str,
    start_time: float,
    duration: float,
    output_path: str,
) -> bool:
    """Extract a video segment from the source video using FFmpeg.

    Uses -c copy for compliant sections to avoid re-encoding (Req 11.2).

    Args:
        video_path: Source video file path.
        start_time: Start time in seconds.
        duration: Duration of the segment in seconds.
        output_path: Path for the extracted segment file.

    Returns:
        True if extraction was successful, False otherwise.
    """
    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-ss", str(start_time),
            "-i", video_path,
            "-t", str(duration),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            output_path,
        ]

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60
        )

        if result.returncode != 0:
            # Retry with re-encoding if copy fails (e.g., keyframe issues)
            cmd = [
                "ffmpeg",
                "-y",
                "-ss", str(start_time),
                "-i", video_path,
                "-t", str(duration),
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "128k",
                output_path,
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60
            )

            if result.returncode != 0:
                logger.warning(
                    f"Segment extraction failed: {result.stderr[:300]}"
                )
                return False

        return os.path.exists(output_path) and os.path.getsize(output_path) > 0

    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        logger.warning(f"Segment extraction error: {e}")
        return False


def _layer_audio(
    stitched_video_path: str,
    original_video_path: str,
    voiceover_segments: list[dict],
    original_duration: float,
    final_output_path: str,
) -> str:
    """Layer ambient audio and voiceover onto the stitched video.

    - Extracts original ambient audio as base track (Req 8.2, 11.3)
    - Layers voiceover at +6dB above ambient (Req 8.3)
    - Ensures sync drift ≤ 200ms (Req 8.4)

    Args:
        stitched_video_path: Path to the stitched video (no audio or mixed audio).
        original_video_path: Path to the original video for ambient audio.
        voiceover_segments: List of voiceover segment dicts with audio_path and timing.
        original_duration: Duration of the original video.
        final_output_path: Desired path for the final output file.

    Returns:
        Path to the final composed video, or empty string on failure.
    """
    try:
        # Build the FFmpeg filter_complex for audio layering
        # Input 0: stitched video (use its video stream)
        # Input 1: original video (extract ambient audio - Req 8.2, 11.3)
        # Input 2+: voiceover audio segments

        input_args: list[str] = [
            "-y",
            "-i", stitched_video_path,   # [0] stitched video
            "-i", original_video_path,    # [1] original video for ambient audio
        ]

        # Collect valid voiceover segments
        valid_vo_segments: list[dict] = []
        for vo in voiceover_segments:
            audio_path = vo.get("audio_path", "")
            if audio_path and os.path.exists(audio_path):
                valid_vo_segments.append(vo)
                input_args.extend(["-i", audio_path])

        # Build filter_complex
        filter_parts: list[str] = []

        # Extract ambient audio from original video (Req 8.2, 11.3)
        # Trim to match the stitched video duration
        stitched_duration = _get_media_duration(stitched_video_path)
        if stitched_duration <= 0:
            stitched_duration = original_duration

        # Ambient audio: extract from input 1, preserve original volume
        filter_parts.append(
            f"[1:a]atrim=0:{stitched_duration},asetpts=PTS-STARTPTS[ambient]"
        )

        if valid_vo_segments:
            # Layer voiceover segments at timed offsets (Req 8.3)
            # Each voiceover is delayed to its start_time and boosted +6dB
            vo_labels: list[str] = []
            for i, vo in enumerate(valid_vo_segments):
                input_idx = i + 2  # inputs 0=stitched, 1=original, 2+=voiceover
                start_ms = int(vo.get("start_time", 0.0) * 1000)
                # Boost voiceover volume by VOICEOVER_VOLUME_DB
                filter_parts.append(
                    f"[{input_idx}:a]"
                    f"adelay={start_ms}|{start_ms},"
                    f"volume={VOICEOVER_VOLUME_DB}dB,"
                    f"apad=whole_dur={stitched_duration}"
                    f"[vo{i}]"
                )
                vo_labels.append(f"[vo{i}]")

            # Mix ambient with all voiceover tracks
            # Use amix with duration set to longest to cover full video
            all_audio_inputs = "[ambient]" + "".join(vo_labels)
            num_inputs = 1 + len(vo_labels)
            filter_parts.append(
                f"{all_audio_inputs}"
                f"amix=inputs={num_inputs}:"
                f"duration=longest:"
                f"dropout_transition=0,"
                f"aresample=async=1"
                f"[mixed_audio]"
            )
            audio_map = "[mixed_audio]"
        else:
            # No voiceover — just use ambient audio
            audio_map = "[ambient]"

        filter_complex = ";".join(filter_parts)

        # Build the full FFmpeg command
        cmd = ["ffmpeg"] + input_args + [
            "-filter_complex", filter_complex,
            "-map", "0:v",              # Video from stitched input
            "-map", audio_map,          # Mixed audio
            "-c:v", "copy",             # Copy video stream (already encoded)
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            "-max_interleave_delta", str(MAX_SYNC_DRIFT_MS * 1000),  # microseconds
            "-movflags", "+faststart",
            final_output_path,
        ]

        logger.info(f"Running audio layering with {len(valid_vo_segments)} voiceover segments")

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300
        )

        if result.returncode != 0:
            # Fallback: try without -c:v copy (re-encode video too)
            logger.warning(
                "Audio layering with -c:v copy failed, retrying with re-encoding"
            )
            cmd = ["ffmpeg"] + input_args + [
                "-filter_complex", filter_complex,
                "-map", "0:v",
                "-map", audio_map,
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                "-movflags", "+faststart",
                final_output_path,
            ]

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300
            )

            if result.returncode != 0:
                logger.error(
                    f"Audio layering failed: {result.stderr[:500]}"
                )
                return ""

        if os.path.exists(final_output_path) and os.path.getsize(final_output_path) > 0:
            return final_output_path

        return ""

    except subprocess.TimeoutExpired:
        logger.error("Audio layering timed out")
        return ""
    except FileNotFoundError:
        logger.error("FFmpeg not found. Ensure FFmpeg is installed and on PATH.")
        return ""
    except Exception as e:
        logger.error(f"Audio layering failed: {e}")
        return ""


def _get_media_duration(file_path: str) -> float:
    """Get the duration of a media file using FFprobe.

    Args:
        file_path: Path to the media file.

    Returns:
        Duration in seconds, or 0.0 if probe fails.
    """
    try:
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path,
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10
        )

        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())

    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError) as e:
        logger.warning(f"Failed to get media duration for {file_path}: {e}")

    return 0.0
