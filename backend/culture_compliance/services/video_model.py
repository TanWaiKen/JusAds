"""
services/video_model.py
───────────────────────
Swappable video model interface for the v3 single-model compliance pipeline.

Supports sending a video file + prompt to either:
- TwelveLabs Pegasus (via Bedrock InvokeModel)
- Claude (via Bedrock Converse API with video content blocks)

The active model is controlled by the VIDEO_COMPLIANCE_MODEL config.
"""

import base64
import json
import logging
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from ..config import (
    AWS_REGION_LLM,
    CLAUDE_VIDEO_MODEL_ID,
    VIDEO_COMPLIANCE_MODEL,
    VIDEO_MODEL_ID,
)

logger = logging.getLogger(__name__)

# Bedrock client configuration
_bedrock_config = Config(
    retries={"max_attempts": 3, "mode": "adaptive"},
    read_timeout=300,
)

# Maximum video size for base64 encoding (100 MB)
MAX_VIDEO_BYTES = 100 * 1024 * 1024


def _get_bedrock_client():
    """Create a Bedrock Runtime client."""
    return boto3.client(
        "bedrock-runtime",
        region_name=AWS_REGION_LLM,
        config=_bedrock_config,
    )


def _read_video_bytes(video_path: str) -> bytes:
    """Read video file and return raw bytes.

    Args:
        video_path: Path to the video file.

    Returns:
        Raw bytes of the video file.

    Raises:
        FileNotFoundError: If the video file does not exist.
        ValueError: If the file exceeds the maximum size.
    """
    path = Path(video_path)
    if not path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    video_bytes = path.read_bytes()
    if len(video_bytes) > MAX_VIDEO_BYTES:
        raise ValueError(
            f"Video file too large ({len(video_bytes)} bytes, max {MAX_VIDEO_BYTES})"
        )

    return video_bytes


def _get_media_type(video_path: str) -> str:
    """Determine the MIME type from the video file extension.

    Args:
        video_path: Path to the video file.

    Returns:
        The MIME type string (e.g., "video/mp4").
    """
    ext = Path(video_path).suffix.lower()
    mime_map = {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".webm": "video/webm",
    }
    return mime_map.get(ext, "video/mp4")


def analyze_video_with_pegasus(video_path: str, prompt: str) -> str:
    """Analyze a video using TwelveLabs Pegasus via Bedrock InvokeModel.

    Args:
        video_path: Path to the video file.
        prompt: The analysis/compliance prompt.

    Returns:
        The model's text response.
    """
    video_bytes = _read_video_bytes(video_path)
    video_b64 = base64.b64encode(video_bytes).decode("utf-8")

    request_body = {
        "inputPrompt": prompt,
        "mediaSource": {"base64String": video_b64},
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
    result = response_body.get("message", "")
    logger.info("Pegasus response: %d characters", len(result))
    return result


def analyze_video_with_claude(video_path: str, prompt: str) -> str:
    """Analyze a video using Claude via Bedrock Converse API.

    Args:
        video_path: Path to the video file.
        prompt: The analysis/compliance prompt.

    Returns:
        The model's text response.
    """
    video_bytes = _read_video_bytes(video_path)
    media_type = _get_media_type(video_path)

    client = _get_bedrock_client()
    response = client.converse(
        modelId=CLAUDE_VIDEO_MODEL_ID,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "video": {
                            "format": media_type.split("/")[1],
                            "source": {"bytes": video_bytes},
                        },
                    },
                    {"text": prompt},
                ],
            }
        ],
        inferenceConfig={
            "maxTokens": 4096,
            "temperature": 0.0,
            "topP": 1.0,
        },
    )

    result = response["output"]["message"]["content"][0]["text"]
    logger.info("Claude response: %d characters", len(result))
    return result


def analyze_video_for_compliance(
    video_path: str,
    prompt: str,
    model: str | None = None,
) -> str:
    """Analyze a video for compliance using the configured model.

    Routes to either Pegasus or Claude based on the model parameter
    or the VIDEO_COMPLIANCE_MODEL config setting.

    Args:
        video_path: Path to the video file.
        prompt: The compliance evaluation prompt.
        model: Override model selection ("pegasus" or "claude").
            If None, uses VIDEO_COMPLIANCE_MODEL from config.

    Returns:
        The model's text response (expected to be JSON).

    Raises:
        ValueError: If an unsupported model is specified.
    """
    active_model = model or VIDEO_COMPLIANCE_MODEL

    logger.info(
        "Analyzing video with model '%s': %s", active_model, video_path
    )

    if active_model == "pegasus":
        return analyze_video_with_pegasus(video_path, prompt)
    elif active_model == "claude":
        return analyze_video_with_claude(video_path, prompt)
    else:
        raise ValueError(
            f"Unsupported video compliance model: '{active_model}'. "
            "Supported: 'pegasus', 'claude'"
        )
