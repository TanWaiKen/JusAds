"""Step 2: Video processing node for the compliance pipeline.

Validates video format, size, and duration, then uses TwelveLabs Pegasus
for whole-video understanding via Bedrock InvokeModel API.

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10
"""

import base64
import json
import logging
import os
import subprocess
from typing import Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from culture_compliance.config import AWS_REGION_LLM, VIDEO_MODEL_ID
from culture_compliance.models.schemas import PipelineState

logger = logging.getLogger(__name__)

# Constraints
MAX_VIDEO_SIZE_BYTES = 104_857_600  # 100 MB
MAX_DURATION_SECONDS = 300  # 5 minutes
MAX_BASE64_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB for Pegasus base64 input

# Supported video formats by extension
SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".webm"}

# Magic bytes for video format detection
_MP4_FTYP_MARKER = b"ftyp"
_WEBM_MAGIC = b"\x1a\x45\xdf\xa3"  # EBML header (Matroska/WebM)

# Boto3 client configuration
_bedrock_config = Config(
    retries={"max_attempts": 3, "mode": "adaptive"},
    read_timeout=300,
)


def _get_bedrock_client():
    """Create a Bedrock Runtime client for Pegasus invocation."""
    return boto3.client(
        "bedrock-runtime",
        region_name=AWS_REGION_LLM,
        config=_bedrock_config,
    )


def _merge_chronologically(
    frame_descriptions: list[dict], transcript_segments: list[dict]
) -> str:
    """Merge frame descriptions and transcript segments in chronological order.

    Args:
        frame_descriptions: List of dicts with 'timestamp' (float) and 'description' (str).
        transcript_segments: List of dicts with 'start_time' (float), 'end_time' (float), and 'text' (str).

    Returns:
        A newline-separated string with entries formatted as [MM:SS] [Visual|Audio] description,
        ordered by timestamp. Returns empty string if both inputs are empty.
    """
    if not frame_descriptions and not transcript_segments:
        return ""

    entries: list[tuple[float, str]] = []

    for frame in frame_descriptions:
        ts = frame.get("timestamp", 0.0)
        desc = frame.get("description", "")
        minutes = int(ts) // 60
        seconds = int(ts) % 60
        entries.append((ts, f"[{minutes:02d}:{seconds:02d}] [Visual] {desc}"))

    for segment in transcript_segments:
        ts = segment.get("start_time", 0.0)
        text = segment.get("text", "")
        minutes = int(ts) // 60
        seconds = int(ts) % 60
        entries.append((ts, f"[{minutes:02d}:{seconds:02d}] [Audio] {text}"))

    # Sort by timestamp (stable sort preserves insertion order for equal timestamps)
    entries.sort(key=lambda x: x[0])

    return "\n".join(entry[1] for entry in entries)


def _detect_video_format_by_extension(video_path: str) -> Optional[str]:
    ext = os.path.splitext(video_path)[1].lower()
    return ext if ext in SUPPORTED_EXTENSIONS else None


def _detect_video_format_by_magic(video_path: str) -> Optional[str]:
    try:
        with open(video_path, "rb") as f:
            header = f.read(32)
        if len(header) < 12:
            return None
        if header[4:8] == _MP4_FTYP_MARKER:
            brand = header[8:12]
            return ".mov" if brand in (b"qt  ", b"MSNV") else ".mp4"
        if header[:4] == _WEBM_MAGIC:
            return ".webm"
        return None
    except (OSError, IOError):
        return None


def _get_file_size(video_path: str) -> int:
    try:
        return os.path.getsize(video_path)
    except OSError:
        return 0


def _get_video_duration(video_path: str) -> Optional[float]:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", video_path],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return None
        duration_str = result.stdout.strip()
        if not duration_str:
            return None
        duration = float(duration_str)
        return duration if duration > 0 else None
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        return None


def _analyze_video_with_pegasus(video_path: str, prompt: str) -> str:
    """Analyze a video using TwelveLabs Pegasus via Bedrock InvokeModel.

    Reads the video file, base64-encodes it, and sends to Pegasus for
    whole-video understanding in a single API call.

    Args:
        video_path: Path to the video file.
        prompt: The analysis prompt to send to Pegasus.

    Returns:
        The model's text response describing the video content.

    Raises:
        Exception: If the API call fails.
    """
    # Read and base64-encode the video
    with open(video_path, "rb") as f:
        video_bytes = f.read()

    if len(video_bytes) > MAX_BASE64_SIZE_BYTES:
        raise ValueError(
            f"Video file too large for Pegasus base64 input "
            f"({len(video_bytes)} bytes, max {MAX_BASE64_SIZE_BYTES})"
        )

    video_b64 = base64.b64encode(video_bytes).decode("utf-8")

    # Build Pegasus request body
    request_body = {
        "inputPrompt": prompt,
        "mediaSource": {
            "base64String": video_b64,
        },
        "temperature": 0,
        "maxOutputTokens": 4096,
    }

    client = _get_bedrock_client()
    response = client.invoke_model(
        modelId=VIDEO_MODEL_ID,
        body=json.dumps(request_body),
        contentType="application/json",
        accept="application/json",
    )

    response_body = json.loads(response["body"].read())
    return response_body.get("message", "")


def video_processing(state: PipelineState) -> PipelineState:
    """Analyze video using TwelveLabs Pegasus for whole-video understanding.

    Performs the following steps:
    1. Validate video file exists
    2. Validate format (MP4/MOV/WebM)
    3. Validate size (≤100 MB) and duration (≤5 minutes)
    4. Send entire video to Pegasus for comprehensive analysis
    5. Set unified_content in state with the analysis result

    Args:
        state: The current pipeline state containing the submission.

    Returns:
        Updated PipelineState with unified_content set, or with errors
        appended if validation fails.
    """
    video_path = state.submission.content

    # Step 1: Validate the video file exists
    if not video_path or not video_path.strip():
        state.errors.append({
            "error_type": "validation",
            "message": "Video content path is empty",
            "details": {},
        })
        return state

    video_path = video_path.strip()

    if not os.path.exists(video_path):
        state.errors.append({
            "error_type": "validation",
            "message": f"Video file not found: {video_path}",
            "details": {"path": video_path},
        })
        return state

    # Step 2: Validate format
    fmt = _detect_video_format_by_extension(video_path)
    if fmt is None:
        fmt = _detect_video_format_by_magic(video_path)

    if fmt is None:
        state.errors.append({
            "error_type": "validation",
            "message": "Unsupported video format. Supported formats: MP4, MOV, WebM",
            "details": {"supported_formats": ["MP4", "MOV", "WebM"]},
        })
        return state

    # Step 3: Validate size
    file_size = _get_file_size(video_path)
    if file_size > MAX_VIDEO_SIZE_BYTES:
        state.errors.append({
            "error_type": "validation",
            "message": f"Video file exceeds maximum size of 100 MB. Received: {file_size} bytes",
            "details": {"max_size_bytes": MAX_VIDEO_SIZE_BYTES, "actual_size_bytes": file_size},
        })
        return state

    # Step 4: Validate duration
    duration = _get_video_duration(video_path)
    if duration is not None and duration > MAX_DURATION_SECONDS:
        state.errors.append({
            "error_type": "validation",
            "message": f"Video duration exceeds maximum of 5 minutes. Received: {duration:.1f} seconds",
            "details": {"max_duration_seconds": MAX_DURATION_SECONDS, "actual_duration_seconds": duration},
        })
        return state

    # Step 5: Analyze with Pegasus
    prompt = (
        "Analyze this video and provide a structured visual audit. Do not evaluate if the content is legal or illegal. "
        "You must output exactly two sections:\n\n"
        "1. NARRATIVE SUMMARY: A brief chronological summary of the video's events, spoken dialogue, and text overlays. Include precise timestamps (MM:SS) for every major action.\n"
        "2. VISUAL AUDIT TAGS: Scan the video and explicitly list if any of the following universal elements are visually present, no matter how briefly. For every element you find, you MUST include the exact timestamp (MM:SS) it appears on screen. If none are present, state 'None'.\n"
        "- Body Exposure (Specify exactly what skin/body parts are visible, e.g., bare armpits, midriff, thighs, uncovered hair, cleavage, and provide timestamps)\n"
        "- Physical Contact (Describe any touching between actors and provide timestamps)\n"
        "- Symbols & Attire (Religious symbols, traditional clothing, specific colors, and provide timestamps)\n"
        "- Food & Animals (Specify types of food, beverages, or animals shown, and provide timestamps)\n"
        "- Gestures & Text (Specific hand signs, numbers, or prominent text, and provide timestamps)"
    )

    logger.info("Analyzing video with Pegasus: %s (%.2f MB)", video_path, file_size / (1024 * 1024))

    try:
        analysis = _analyze_video_with_pegasus(video_path, prompt)
        state.models_used.append(VIDEO_MODEL_ID)
        logger.info("Pegasus analysis completed: %d characters", len(analysis))
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        logger.error("Pegasus API error: %s - %s", error_code, str(e))
        state.errors.append({
            "error_type": "service_unavailable",
            "message": f"Video analysis model unavailable: {error_code}",
            "details": {"model": VIDEO_MODEL_ID},
        })
        return state
    except Exception as e:
        logger.error("Video analysis failed: %s", str(e))
        state.errors.append({
            "error_type": "service_unavailable",
            "message": f"Video analysis failed: {str(e)}",
            "details": {"model": VIDEO_MODEL_ID},
        })
        return state

    if not analysis:
        state.warnings.append({
            "step_name": "video_analysis",
            "description": "Pegasus returned empty analysis",
            "result_may_be_incomplete": True,
        })
        state.unified_content = "[Video] No analyzable content could be extracted."
    else:
        state.unified_content = analysis

    logger.info("Video processing completed: unified_length=%d", len(state.unified_content))
    return state
