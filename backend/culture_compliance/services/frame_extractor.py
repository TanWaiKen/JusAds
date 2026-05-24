"""Frame extractor service for video processing using ffmpeg.

Samples representative frames from a video file at configurable intervals
using ffmpeg subprocess calls. Returns timestamped frame data for downstream
vision analysis.

Requirements: 4.1
"""

import logging
import subprocess
from math import ceil

logger = logging.getLogger(__name__)

# Interval constraints
MIN_INTERVAL = 0.5
MAX_INTERVAL = 5.0


class FrameExtractionError(Exception):
    """Raised when frame extraction fails."""

    pass


def _get_video_duration(video_path: str) -> float:
    """Get the duration of a video file using ffprobe.

    Args:
        video_path: Path to the video file.

    Returns:
        Duration in seconds as a float.

    Raises:
        FrameExtractionError: If ffprobe is not found, the file is invalid,
            or duration cannot be determined.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() or "Unknown ffprobe error"
            raise FrameExtractionError(
                f"ffprobe failed for '{video_path}': {error_msg}"
            )

        duration_str = result.stdout.strip()
        if not duration_str:
            raise FrameExtractionError(
                f"ffprobe returned empty duration for '{video_path}'"
            )

        duration = float(duration_str)
        if duration <= 0:
            raise FrameExtractionError(
                f"Invalid video duration ({duration}s) for '{video_path}'"
            )

        return duration

    except FileNotFoundError:
        raise FrameExtractionError(
            "ffmpeg/ffprobe not found. Please install ffmpeg and ensure it is on PATH."
        )
    except subprocess.TimeoutExpired:
        raise FrameExtractionError(
            f"ffprobe timed out while reading '{video_path}'"
        )
    except ValueError as e:
        raise FrameExtractionError(
            f"Could not parse duration from ffprobe output: {e}"
        )


def extract_frames(video_path: str, interval: float = 1.0) -> list[dict]:
    """Extract frames from a video at a configurable interval using ffmpeg.

    Samples frames at the specified interval and returns them as a list of
    dictionaries containing the timestamp and raw frame bytes (JPEG encoded).

    Args:
        video_path: Path to the video file on the local filesystem.
        interval: Time between frame samples in seconds. Must be between
            0.5 and 5.0 seconds (inclusive). Defaults to 1.0.

    Returns:
        A list of dicts, each containing:
            - "timestamp" (float): The time position in seconds (multiples of interval starting from 0).
            - "frame_bytes" (bytes): JPEG-encoded frame image data.

    Raises:
        FrameExtractionError: If ffmpeg is not found, the video file is invalid,
            or frame extraction fails.
        ValueError: If interval is outside the valid range [0.5, 5.0].

    Requirements:
        4.1 - Sample frames at configurable interval between 0.5 and 5 seconds
    """
    # Validate interval
    if interval < MIN_INTERVAL or interval > MAX_INTERVAL:
        raise ValueError(
            f"Interval must be between {MIN_INTERVAL} and {MAX_INTERVAL} seconds, "
            f"got {interval}"
        )

    # Get video duration
    duration = _get_video_duration(video_path)
    logger.info(
        "Video duration: %.2fs, frame interval: %.2fs", duration, interval
    )

    # Calculate expected frame count
    expected_frame_count = ceil(duration / interval)
    logger.info("Expected frame count: %d", expected_frame_count)

    # Extract frames using ffmpeg
    frames: list[dict] = []

    for i in range(expected_frame_count):
        timestamp = i * interval

        # Don't seek past the video duration
        if timestamp >= duration:
            break

        try:
            frame_bytes = _extract_single_frame(video_path, timestamp)
            frames.append({
                "timestamp": timestamp,
                "frame_bytes": frame_bytes,
            })
        except FrameExtractionError as e:
            logger.warning(
                "Failed to extract frame at %.2fs: %s", timestamp, str(e)
            )
            # Continue extracting remaining frames even if one fails
            continue

    if not frames:
        raise FrameExtractionError(
            f"No frames could be extracted from '{video_path}'"
        )

    logger.info(
        "Extracted %d frames from '%s' (expected %d)",
        len(frames),
        video_path,
        expected_frame_count,
    )

    return frames


def _extract_single_frame(video_path: str, timestamp: float) -> bytes:
    """Extract a single frame at the given timestamp using ffmpeg.

    Args:
        video_path: Path to the video file.
        timestamp: Time position in seconds to extract the frame from.

    Returns:
        JPEG-encoded frame bytes.

    Raises:
        FrameExtractionError: If frame extraction fails.
    """
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-ss", str(timestamp),
                "-i", video_path,
                "-frames:v", "1",
                "-f", "image2",
                "-c:v", "mjpeg",
                "-q:v", "2",
                "-y",
                "pipe:1",
            ],
            capture_output=True,
            timeout=30,
        )

        if result.returncode != 0:
            error_msg = result.stderr.decode("utf-8", errors="replace").strip()
            raise FrameExtractionError(
                f"ffmpeg failed at timestamp {timestamp}s: {error_msg}"
            )

        frame_bytes = result.stdout
        if not frame_bytes:
            raise FrameExtractionError(
                f"ffmpeg produced empty output at timestamp {timestamp}s"
            )

        return frame_bytes

    except FileNotFoundError:
        raise FrameExtractionError(
            "ffmpeg not found. Please install ffmpeg and ensure it is on PATH."
        )
    except subprocess.TimeoutExpired:
        raise FrameExtractionError(
            f"ffmpeg timed out extracting frame at {timestamp}s"
        )
