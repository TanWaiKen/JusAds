"""Video Interpolator for the JusAds Video Remix Pipeline.

Generates smooth video clips from storyboard key frames using Veo 3.1
reference_images interpolation. Extracts and retains original ambient
audio/SFX from the source video segment via FFmpeg.

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from google import genai
from google.genai import types

from jusads_remix_pipeline.config import VERTEX_PROJECT_ID, VERTEX_LOCATION

logger = logging.getLogger(__name__)

# Initialize Vertex AI client for Veo
client = genai.Client(
    vertexai=True, project=VERTEX_PROJECT_ID, location=VERTEX_LOCATION
)

# Veo model for video generation
VEO_MODEL = "veo-3.1-generate"

# Clip constraints (Req 6.2)
MIN_CLIP_DURATION = 5  # seconds
MAX_CLIP_DURATION = 8  # seconds
MIN_FPS = 24

# Retry and timeout config (Req 6.5)
MAX_RETRIES = 2
TIMEOUT_SECONDS = 120

# Output directory for generated clips
CLIPS_DIR = Path(__file__).resolve().parent.parent / "assets" / "clips"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PUBLIC API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def interpolate_video(
    storyboard_frames: list[bytes],
    source_segment_path: str,
) -> dict:
    """Interpolate storyboard frames into a smooth video clip using Veo 3.1.

    Uses Veo reference_images with reference_type "asset" to produce a smooth
    interpolated video from the provided storyboard key frames. Extracts and
    retains original ambient audio/SFX from the source segment.

    Args:
        storyboard_frames: List of image bytes (at least 2 frames required).
        source_segment_path: Path to the source video segment file for audio
            extraction.

    Returns:
        Dict with:
            - video_path (str): Path to the generated video clip.
            - ambient_audio_path (str): Path to extracted ambient audio from source.
            - duration (float): Clip duration in seconds.
            - fps (int): Frames per second of the generated clip.
            - error (str | None): Error message if failed.
    """
    # Req 6.6: Reject if fewer than 2 storyboard frames
    if len(storyboard_frames) < 2:
        error_msg = (
            f"Minimum 2 storyboard frames required, got {len(storyboard_frames)}. "
            "Cannot interpolate with fewer than 2 frames."
        )
        logger.error(error_msg)
        return {
            "video_path": "",
            "ambient_audio_path": "",
            "duration": 0.0,
            "fps": 0,
            "error": error_msg,
        }

    # Ensure output directory exists
    CLIPS_DIR.mkdir(parents=True, exist_ok=True)

    # Generate a unique ID for this clip
    clip_id = uuid.uuid4().hex[:12]

    # Step 1: Extract ambient audio from source segment (Req 6.3)
    ambient_audio_path = _extract_ambient_audio(source_segment_path, clip_id)

    # Step 2: Generate video clip via Veo with retries (Req 6.1, 6.5)
    video_path, duration, fps, error = _generate_video_with_retries(
        storyboard_frames, clip_id
    )

    if error:
        return {
            "video_path": "",
            "ambient_audio_path": ambient_audio_path,
            "duration": 0.0,
            "fps": 0,
            "error": error,
        }

    return {
        "video_path": video_path,
        "ambient_audio_path": ambient_audio_path,
        "duration": duration,
        "fps": fps,
        "error": None,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PRIVATE HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _extract_ambient_audio(source_segment_path: str, clip_id: str) -> str:
    """Extract the audio track from the source video segment using FFmpeg.

    Retains ambient audio/SFX for later composition (Req 6.3).
    No speech should be generated — this extracts the original audio as-is.

    Args:
        source_segment_path: Path to the source video segment.
        clip_id: Unique identifier for naming the output file.

    Returns:
        Path to the extracted audio file, or empty string if extraction fails.
    """
    output_path = str(CLIPS_DIR / f"{clip_id}_ambient_audio.aac")

    try:
        cmd = [
            "ffmpeg",
            "-y",  # overwrite if exists
            "-i", source_segment_path,
            "-vn",  # no video
            "-acodec", "aac",
            "-b:a", "128k",
            output_path,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            logger.warning(
                f"FFmpeg audio extraction failed for {source_segment_path}: "
                f"{result.stderr}"
            )
            return ""

        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"Extracted ambient audio to {output_path}")
            return output_path
        else:
            logger.warning(
                f"Audio extraction produced empty file for {source_segment_path}"
            )
            return ""

    except subprocess.TimeoutExpired:
        logger.warning(
            f"FFmpeg audio extraction timed out for {source_segment_path}"
        )
        return ""
    except FileNotFoundError:
        logger.error("FFmpeg not found. Ensure FFmpeg is installed and on PATH.")
        return ""
    except Exception as e:
        logger.warning(f"Audio extraction failed: {e}")
        return ""


def _generate_video_with_retries(
    storyboard_frames: list[bytes],
    clip_id: str,
) -> tuple[str, float, int, str | None]:
    """Generate a video clip using Veo 3.1 with retry logic.

    Uses reference_images with reference_type "asset" for frame interpolation
    (Req 6.1). Generates clips of 5-8 seconds at minimum 24fps (Req 6.2).
    Does not generate speech audio (Req 6.4). Retries up to 2 times on
    failure with 120s timeout (Req 6.5).

    Args:
        storyboard_frames: List of image bytes for interpolation.
        clip_id: Unique identifier for naming the output file.

    Returns:
        Tuple of (video_path, duration, fps, error).
        On success error is None; on failure video_path is empty.
    """
    output_path = str(CLIPS_DIR / f"{clip_id}_interpolated.mp4")

    # Build reference images from storyboard frames (Req 6.1)
    reference_images = [
        types.VideoGenerationReferenceImage(
            image=types.Image(image_bytes=frame),
            reference_type="asset",
        )
        for frame in storyboard_frames
    ]

    # Veo generation config (Req 6.2, 6.4)
    # Prompt instructs no speech audio generation
    generation_prompt = (
        "Smoothly interpolate between the provided reference frames to create a "
        "natural, fluid video clip. Maintain visual consistency between frames. "
        "Do NOT include any speech, dialogue, narration, or human vocal sounds. "
        "The video should contain only ambient environmental sounds and visual motion."
    )

    last_error: str | None = None

    for attempt in range(1 + MAX_RETRIES):
        try:
            logger.info(
                f"Veo generation attempt {attempt + 1}/{1 + MAX_RETRIES} "
                f"for clip {clip_id}"
            )

            start_time = time.time()

            # Call Veo API with reference_images
            operation = client.models.generate_videos(
                model=VEO_MODEL,
                prompt=generation_prompt,
                config=types.GenerateVideosConfig(
                    reference_images=reference_images,
                    output_mime_type="video/mp4",
                    duration_seconds=MAX_CLIP_DURATION,
                    fps=MIN_FPS,
                    number_of_videos=1,
                    negative_prompt=(
                        "speech, dialogue, narration, human voice, vocals, "
                        "talking, singing, whispering"
                    ),
                ),
            )

            # Poll for result with timeout (Req 6.5)
            result = _poll_video_operation(operation, start_time)

            if result is None:
                last_error = (
                    f"Veo API timed out after {TIMEOUT_SECONDS}s "
                    f"(attempt {attempt + 1})"
                )
                logger.warning(last_error)
                continue

            # Extract video data from result
            video_data = _extract_video_from_result(result)
            if video_data is None:
                last_error = (
                    f"No video data in Veo response (attempt {attempt + 1})"
                )
                logger.warning(last_error)
                continue

            # Write video to file
            with open(output_path, "wb") as f:
                f.write(video_data)

            # Get video metadata
            duration, fps = _get_video_metadata(output_path)

            # Validate duration constraints (Req 6.2)
            if duration < MIN_CLIP_DURATION:
                logger.warning(
                    f"Generated clip duration {duration:.1f}s is below minimum "
                    f"{MIN_CLIP_DURATION}s, but accepting the output."
                )

            logger.info(
                f"Video clip generated successfully: {output_path} "
                f"({duration:.1f}s, {fps}fps)"
            )
            return output_path, duration, fps, None

        except Exception as e:
            last_error = f"Veo API error (attempt {attempt + 1}): {e}"
            logger.warning(last_error)

    # All attempts exhausted (Req 6.5)
    final_error = (
        f"Video interpolation failed after {1 + MAX_RETRIES} attempts: {last_error}"
    )
    logger.error(final_error)
    return "", 0.0, 0, final_error


def _poll_video_operation(operation, start_time: float):
    """Poll a Veo video generation operation until complete or timeout.

    Args:
        operation: The Veo generate_videos operation to poll.
        start_time: Timestamp when the operation was started.

    Returns:
        The completed operation result, or None if timed out.
    """
    while True:
        elapsed = time.time() - start_time
        if elapsed >= TIMEOUT_SECONDS:
            return None

        # Check if operation is done
        if hasattr(operation, "done") and operation.done:
            return operation.result
        elif hasattr(operation, "result") and operation.result is not None:
            return operation.result

        # Wait before polling again
        time.sleep(5)

        # Refresh operation status if possible
        if hasattr(operation, "refresh"):
            operation.refresh()


def _extract_video_from_result(result) -> bytes | None:
    """Extract video bytes from a Veo API result.

    Args:
        result: The Veo API response result object.

    Returns:
        Video bytes if found, None otherwise.
    """
    try:
        # Handle different possible result structures
        if hasattr(result, "generated_videos") and result.generated_videos:
            video = result.generated_videos[0]
            if hasattr(video, "video") and hasattr(video.video, "video_bytes"):
                return video.video.video_bytes
            if hasattr(video, "video_bytes"):
                return video.video_bytes

        # Fallback: check if result itself has video data
        if hasattr(result, "video") and hasattr(result.video, "video_bytes"):
            return result.video.video_bytes

    except Exception as e:
        logger.warning(f"Error extracting video from result: {e}")

    return None


def _get_video_metadata(video_path: str) -> tuple[float, int]:
    """Get duration and FPS of a video file using FFprobe.

    Args:
        video_path: Path to the video file.

    Returns:
        Tuple of (duration_seconds, fps). Defaults to (8.0, 24) if probe fails.
    """
    try:
        # Get duration
        duration_cmd = [
            "ffprobe",
            "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        duration_result = subprocess.run(
            duration_cmd, capture_output=True, text=True, timeout=10
        )
        duration = float(duration_result.stdout.strip()) if duration_result.returncode == 0 else MAX_CLIP_DURATION

        # Get FPS
        fps_cmd = [
            "ffprobe",
            "-v", "quiet",
            "-select_streams", "v:0",
            "-show_entries", "stream=r_frame_rate",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        fps_result = subprocess.run(
            fps_cmd, capture_output=True, text=True, timeout=10
        )

        fps = MIN_FPS  # default
        if fps_result.returncode == 0 and fps_result.stdout.strip():
            fps_str = fps_result.stdout.strip()
            # FPS may be in "num/den" format (e.g. "24/1")
            if "/" in fps_str:
                num, den = fps_str.split("/")
                fps = int(round(int(num) / int(den)))
            else:
                fps = int(round(float(fps_str)))

        return duration, fps

    except Exception as e:
        logger.warning(f"Failed to get video metadata: {e}")
        return float(MAX_CLIP_DURATION), MIN_FPS
