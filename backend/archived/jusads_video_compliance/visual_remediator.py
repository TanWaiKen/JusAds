"""Visual Remediator — Fixes visual violations using Gemini Flash Image and Google Veo.

Provides frame regeneration via Gemini Flash Image (Vertex AI) and
replacement clip generation via Google Veo (Vertex AI) video generation.

Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.8, 2.9
"""

from __future__ import annotations

import base64
import logging
import os
import subprocess
import time
import uuid

from google import genai
from google.genai import types

from config import (
    VERTEX_PROJECT_ID,
    VERTEX_LOCATION,
)

logger = logging.getLogger(__name__)

# Veo minimum duration in seconds
VEO_MIN_DURATION_SECONDS = 4.0


# Simple result container (replaces models.py dataclass)
class VisualRemediationResult:
    """Result of a visual remediation attempt."""
    def __init__(self, original_start, original_end, replacement_clip_path, veo_generation_duration, speed_factor, success, error=None):
        self.original_start = original_start
        self.original_end = original_end
        self.replacement_clip_path = replacement_clip_path
        self.veo_generation_duration = veo_generation_duration
        self.speed_factor = speed_factor
        self.success = success
        self.error = error


def _get_video_duration(video_path: str) -> float:
    """Get the duration of a video file using ffprobe.

    Args:
        video_path: Path to the video file.

    Returns:
        Duration in seconds, or 0.0 if the duration cannot be determined.
    """
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0 or not result.stdout.strip():
            return 0.0
        return float(result.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError, OSError):
        return 0.0


def _build_atempo_chain(speed_factor: float) -> str:
    """Build an FFmpeg atempo filter chain for the given speed factor.

    The atempo filter only accepts values between 0.5 and 100.0, so
    extreme speed factors must be chained.

    Args:
        speed_factor: The desired playback speed multiplier.

    Returns:
        A comma-separated atempo filter chain string.
    """
    filters = []

    remaining = speed_factor
    while remaining > 100.0:
        filters.append("atempo=100.0")
        remaining /= 100.0
    while remaining < 0.5:
        filters.append("atempo=0.5")
        remaining /= 0.5

    filters.append(f"atempo={remaining}")
    return ",".join(filters)


def extract_frame(video_path: str, timestamp_sec: float, output_path: str) -> bool:
    """Extract a single frame from video at given timestamp using FFmpeg.

    Args:
        video_path: Path to the source video file.
        timestamp_sec: Timestamp in seconds to extract the frame at.
        output_path: Path where the extracted PNG frame will be saved.

    Returns:
        True if extraction succeeded, False otherwise.

    Validates: Requirement 2.1
    """
    # Validate timestamp is non-negative
    if timestamp_sec < 0:
        logger.error(f"Invalid negative timestamp: {timestamp_sec}")
        return False

    try:
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        cmd = [
            "ffmpeg",
            "-y",
            "-ss", str(timestamp_sec),
            "-i", video_path,
            "-frames:v", "1",
            "-q:v", "2",
            output_path,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            logger.error(
                f"FFmpeg frame extraction failed (exit code {result.returncode}): "
                f"{result.stderr}"
            )
            return False

        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            logger.error(
                f"FFmpeg completed but output file not created or empty: {output_path}"
            )
            # Clean up empty file if it exists
            if os.path.exists(output_path):
                os.remove(output_path)
            return False

        return True

    except subprocess.TimeoutExpired:
        logger.error(f"FFmpeg frame extraction timed out at {timestamp_sec}s")
        return False
    except Exception as e:
        logger.error(f"Frame extraction error: {e}")
        return False


def speed_adjust_clip(
    clip_path: str,
    target_duration: float,
    output_path: str,
) -> str:
    """Speed up or slow down a clip to fit target duration using FFmpeg.

    Args:
        clip_path: Path to the input video clip.
        target_duration: Desired output duration in seconds. Must be > 0.
        output_path: Path where the speed-adjusted clip will be saved.

    Returns:
        Path to the output file.

    Raises:
        ValueError: If target_duration is <= 0 or clip duration cannot be determined.
        RuntimeError: If FFmpeg speed adjustment fails.

    Validates: Requirement 2.5
    """
    if target_duration <= 0:
        raise ValueError(
            f"target_duration must be > 0, got {target_duration}"
        )

    # Get the current clip duration
    current_duration = _get_video_duration(clip_path)
    if current_duration <= 0:
        raise ValueError(
            f"Could not determine duration of clip: {clip_path}"
        )

    # Calculate speed factor (how much faster to play)
    speed_factor = current_duration / target_duration

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # Build filter chains for video and audio
    video_filter = f"setpts={1/speed_factor}*PTS"
    audio_filter = _build_atempo_chain(speed_factor)

    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-i", clip_path,
            "-filter:v", video_filter,
            "-filter:a", audio_filter,
            output_path,
        ]

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60
        )

        # If audio filter fails (e.g., no audio stream), retry without audio
        if result.returncode != 0:
            cmd_no_audio = [
                "ffmpeg",
                "-y",
                "-i", clip_path,
                "-filter:v", video_filter,
                "-an",
                output_path,
            ]
            result = subprocess.run(
                cmd_no_audio, capture_output=True, text=True, timeout=60
            )

        if result.returncode != 0:
            raise RuntimeError(
                f"FFmpeg speed adjustment failed: {result.stderr}"
            )

        return output_path

    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Speed adjustment failed: {e}") from e


async def regenerate_frame(
    original_frame_path: str,
    compliance_prompt: str,
) -> str:
    """Regenerate a frame using Gemini Flash Image to be compliant.

    Sends the original frame image and a compliance-specific prompt to
    Gemini Flash Image (gemini-3.1-flash-image) via Vertex AI. The model
    returns a regenerated image that addresses the compliance violation.

    Args:
        original_frame_path: Path to the original frame PNG/JPEG file.
        compliance_prompt: A prompt describing how to make the frame compliant.

    Returns:
        Path to the regenerated image file.

    Raises:
        RuntimeError: If the Gemini API call fails.

    Validates: Requirements 2.2, 2.8
    """
    if not VERTEX_PROJECT_ID:
        raise RuntimeError(
            "VERTEX_PROJECT_ID environment variable is not set"
        )

    if not os.path.exists(original_frame_path):
        raise RuntimeError(
            f"Original frame not found: {original_frame_path}"
        )

    # Read the original frame
    with open(original_frame_path, "rb") as f:
        image_bytes = f.read()

    # Determine MIME type from extension
    ext = os.path.splitext(original_frame_path)[1].lower()
    mime_type = "image/png" if ext == ".png" else "image/jpeg"

    try:
        # Initialize Gemini client via Vertex AI
        client = genai.Client(
            vertexai=True,
            project=VERTEX_PROJECT_ID,
            location=VERTEX_LOCATION,
        )

        # Build the content with image + text prompt
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    types.Part.from_text(
                        text=f"Edit this image to make it compliant. {compliance_prompt}. "
                             f"Keep the same composition, lighting, and style. "
                             f"Output only the edited image."
                    ),
                ],
            )
        ]

        # Configure for image generation output
        generate_config = types.GenerateContentConfig(
            temperature=1,
            top_p=0.95,
            max_output_tokens=32768,
            response_modalities=["TEXT", "IMAGE"],
            safety_settings=[
                types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
                types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
                types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
                types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
            ],
            image_config=types.ImageConfig(
                image_size="1K",
                output_mime_type="image/png",
            ),
            thinking_config=types.ThinkingConfig(
                thinking_level="MINIMAL",
            ),
        )

        # Call Gemini Flash Image using streaming
        logger.info(f"Calling Gemini Flash Image for frame regeneration...")
        image_output_bytes = None
        for chunk in client.models.generate_content_stream(
            model="gemini-3.1-flash-image",
            contents=contents,
            config=generate_config,
        ):
            if not chunk.candidates:
                continue
            candidate = chunk.candidates[0]
            if not candidate.content or not candidate.content.parts:
                continue
            for part in candidate.content.parts:
                if part.inline_data and part.inline_data.data:
                    image_output_bytes = part.inline_data.data
                    break

        if not image_output_bytes:
            raise RuntimeError(
                "Gemini Flash Image response did not contain an image"
            )

    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(
            f"Gemini Flash Image frame regeneration failed: {e}"
        ) from e

    # Save the regenerated image
    output_dir = os.path.dirname(original_frame_path)
    output_filename = f"edited_{uuid.uuid4().hex[:8]}.png"
    output_path = os.path.join(output_dir, output_filename)

    with open(output_path, "wb") as f:
        f.write(image_output_bytes)

    logger.info(f"Regenerated frame saved to {output_path}")
    return output_path


async def generate_replacement_clip(
    start_image_path: str,
    end_image_path: str,
    duration_seconds: float,
) -> str:
    """Generate a video clip from two images using Google Veo.

    Uses Google Veo (via Vertex AI) to generate a video that transitions
    from the start image to the end image over the specified duration.
    Enforces a minimum duration of 4.0 seconds (Veo API constraint).

    Args:
        start_image_path: Path to the start reference image (PNG/JPEG).
        end_image_path: Path to the end reference image (PNG/JPEG).
        duration_seconds: Desired clip duration in seconds. Will be clamped
            to at least 4.0 seconds (Veo minimum).

    Returns:
        Path to the generated MP4 clip.

    Raises:
        RuntimeError: If the Google Veo API call fails.

    Validates: Requirements 2.3, 2.4, 2.8
    """
    if not VERTEX_PROJECT_ID:
        raise RuntimeError(
            "VERTEX_PROJECT_ID environment variable is not set"
        )

    if not os.path.exists(start_image_path):
        raise RuntimeError(
            f"Start image not found: {start_image_path}"
        )
    if not os.path.exists(end_image_path):
        raise RuntimeError(
            f"End image not found: {end_image_path}"
        )

    # Enforce Veo minimum duration of 4.0 seconds
    veo_duration = max(VEO_MIN_DURATION_SECONDS, duration_seconds)

    # Round to nearest integer for Veo API (accepts integer seconds)
    veo_duration_int = int(round(veo_duration))
    # Ensure at least 4 seconds after rounding
    veo_duration_int = max(4, veo_duration_int)

    try:
        # Initialize the Vertex AI client for Veo (requires us-central1)
        veo_client = genai.Client(
            vertexai=True,
            project=VERTEX_PROJECT_ID,
            location="us-central1",
        )

        # Read the reference images
        with open(start_image_path, "rb") as f:
            start_image_bytes = f.read()
        with open(end_image_path, "rb") as f:
            end_image_bytes = f.read()

        # Determine MIME types
        start_ext = os.path.splitext(start_image_path)[1].lower()
        end_ext = os.path.splitext(end_image_path)[1].lower()
        start_mime = "image/png" if start_ext == ".png" else "image/jpeg"
        end_mime = "image/png" if end_ext == ".png" else "image/jpeg"

        # Create the image references for Veo
        start_image = types.Image(
            image_bytes=start_image_bytes,
            mime_type=start_mime,
        )
        last_frame_image = types.Image(
            image_bytes=end_image_bytes,
            mime_type=end_mime,
        )

        # Configure Veo generation:
        # - image (first frame) goes in GenerateVideosSource
        # - last_frame goes in GenerateVideosConfig
        source = types.GenerateVideosSource(
            image=start_image,
            prompt=(
                "Smooth cinematic transition maintaining visual consistency, "
                "natural motion, and scene continuity."
            ),
        )

        config = types.GenerateVideosConfig(
            aspect_ratio="16:9",
            number_of_videos=1,
            duration_seconds=veo_duration_int,
            person_generation="allow_all",
            generate_audio=False,
            resolution="720p",
            last_frame=last_frame_image,
        )

        # Submit the video generation request
        logger.info(
            f"Submitting Veo generation request: "
            f"duration={veo_duration_int}s, "
            f"start_image={start_image_path}, "
            f"end_image={end_image_path}"
        )

        operation = veo_client.models.generate_videos(
            model="veo-3.1-lite-generate-001",
            source=source,
            config=config,
        )

        # Poll for completion
        while not operation.done:
            logger.info("Video has not been generated yet. Check again in 10 seconds...")
            time.sleep(10)
            operation = veo_client.operations.get(operation)

        response = operation.result
        if not response:
            raise RuntimeError("Error occurred while generating video.")

        generated_videos = response.generated_videos
        if not generated_videos:
            raise RuntimeError("No videos were generated.")

        generated_video = generated_videos[0]
        if not generated_video.video or not generated_video.video.video_bytes:
            raise RuntimeError("Veo generated video has no video bytes")

        # Save the generated clip
        output_dir = os.path.dirname(start_image_path)
        output_filename = f"veo_clip_{uuid.uuid4().hex[:8]}.mp4"
        output_path = os.path.join(output_dir, output_filename)

        with open(output_path, "wb") as f:
            f.write(generated_video.video.video_bytes)

        logger.info(
            f"Veo generated clip saved to {output_path} "
            f"(requested {veo_duration_int}s)"
        )
        return output_path

    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(
            f"Google Veo clip generation failed: {e}"
        ) from e


def build_compliance_prompt(category: str, description: str) -> str:
    """Build a compliance-specific prompt for Nano Banana frame regeneration.

    Constructs a prompt that instructs the image generation model to produce
    a compliant version of the frame, addressing the specific violation.

    Args:
        category: The violation category (e.g., "Sexual/Explicit").
        description: Human-readable description of the violation.

    Returns:
        A prompt string for the Nano Banana API.
    """
    return (
        f"Regenerate this image to be culturally and regulatory compliant. "
        f"Remove or replace content that violates the '{category}' guideline. "
        f"Specifically address: {description}. "
        f"Maintain the overall composition, lighting, and style while ensuring "
        f"the output is appropriate for all audiences."
    )


async def remediate_visual_segment(
    video_path: str,
    violation,
    output_dir: str,
) -> VisualRemediationResult:
    """Fix a single visual violation segment.

    Orchestrates the full visual remediation flow:
    1. Validate segment duration > 0
    2. Extract boundary frames at violation start and end timestamps
    3. Build compliance prompt from violation category/description
    4. Regenerate frames with Nano Banana
    5. Generate replacement clip with Veo (min 4 seconds)
    6. Speed adjust if segment < 4 seconds
    7. Return VisualRemediationResult

    Args:
        video_path: Path to the source video file.
        violation: The visual Violation to remediate.
        output_dir: Directory to store intermediate and output files.

    Returns:
        VisualRemediationResult with success/failure status and clip path.

    Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.9
    """
    # Step 1: Validate segment duration
    segment_duration = violation.timestamp_end - violation.timestamp_start
    if segment_duration <= 0:
        logger.error(
            f"Invalid time range: start={violation.timestamp_start}, "
            f"end={violation.timestamp_end}"
        )
        # Use a minimal valid end value for the result model
        # (original_end must be > original_start per model validation)
        safe_end = violation.timestamp_start + 0.001
        return VisualRemediationResult(
            original_start=violation.timestamp_start,
            original_end=safe_end,
            replacement_clip_path="",
            veo_generation_duration=0.0,
            speed_factor=1.0,
            success=False,
            error="Invalid time range",
        )

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Step 2: Extract boundary frames at violation start and end timestamps
    frame_id = uuid.uuid4().hex[:8]
    frame_start_path = os.path.join(output_dir, f"frame_start_{frame_id}.png")
    frame_end_path = os.path.join(output_dir, f"frame_end_{frame_id}.png")

    start_extracted = extract_frame(video_path, violation.timestamp_start, frame_start_path)
    if not start_extracted:
        logger.error(
            f"Failed to extract start frame at {violation.timestamp_start}s"
        )
        return VisualRemediationResult(
            original_start=violation.timestamp_start,
            original_end=violation.timestamp_end,
            replacement_clip_path="",
            veo_generation_duration=0.0,
            speed_factor=1.0,
            success=False,
            error=f"Frame extraction failed at start timestamp {violation.timestamp_start}s",
        )

    end_extracted = extract_frame(video_path, violation.timestamp_end, frame_end_path)
    if not end_extracted:
        logger.error(
            f"Failed to extract end frame at {violation.timestamp_end}s"
        )
        return VisualRemediationResult(
            original_start=violation.timestamp_start,
            original_end=violation.timestamp_end,
            replacement_clip_path="",
            veo_generation_duration=0.0,
            speed_factor=1.0,
            success=False,
            error=f"Frame extraction failed at end timestamp {violation.timestamp_end}s",
        )

    # Step 3: Build compliance prompt from violation category/description
    compliance_prompt = build_compliance_prompt(
        violation.category, violation.description
    )

    # Step 4: Regenerate frames with Nano Banana
    try:
        regen_start = await regenerate_frame(frame_start_path, compliance_prompt)
        regen_end = await regenerate_frame(frame_end_path, compliance_prompt)
    except RuntimeError as e:
        logger.error(f"Nano Banana frame regeneration failed: {e}")
        return VisualRemediationResult(
            original_start=violation.timestamp_start,
            original_end=violation.timestamp_end,
            replacement_clip_path="",
            veo_generation_duration=0.0,
            speed_factor=1.0,
            success=False,
            error=f"Frame regeneration failed: {e}",
        )

    # Step 5: Generate replacement clip with Veo (min 4 seconds)
    veo_duration = max(VEO_MIN_DURATION_SECONDS, segment_duration)
    try:
        generated_clip = await generate_replacement_clip(
            regen_start, regen_end, veo_duration
        )
    except RuntimeError as e:
        logger.error(f"Veo clip generation failed: {e}")
        return VisualRemediationResult(
            original_start=violation.timestamp_start,
            original_end=violation.timestamp_end,
            replacement_clip_path="",
            veo_generation_duration=veo_duration,
            speed_factor=1.0,
            success=False,
            error=f"Clip generation failed: {e}",
        )

    # Step 6: Speed adjust if segment < 4 seconds
    if segment_duration < VEO_MIN_DURATION_SECONDS:
        speed_factor = veo_duration / segment_duration
        output_clip_path = os.path.join(
            output_dir, f"adjusted_{frame_id}.mp4"
        )
        try:
            final_clip = speed_adjust_clip(
                generated_clip, segment_duration, output_clip_path
            )
        except (ValueError, RuntimeError) as e:
            logger.error(f"Speed adjustment failed: {e}")
            return VisualRemediationResult(
                original_start=violation.timestamp_start,
                original_end=violation.timestamp_end,
                replacement_clip_path="",
                veo_generation_duration=veo_duration,
                speed_factor=speed_factor,
                success=False,
                error=f"Speed adjustment failed: {e}",
            )
    else:
        speed_factor = 1.0
        final_clip = generated_clip

    # Step 7: Return successful result
    logger.info(
        f"Visual remediation succeeded for segment "
        f"[{violation.timestamp_start}s - {violation.timestamp_end}s]: "
        f"clip={final_clip}, veo_duration={veo_duration}s, "
        f"speed_factor={speed_factor}"
    )
    return VisualRemediationResult(
        original_start=violation.timestamp_start,
        original_end=violation.timestamp_end,
        replacement_clip_path=final_clip,
        veo_generation_duration=veo_duration,
        speed_factor=speed_factor,
        success=True,
        error=None,
    )
