"""Vision service for image analysis using Amazon Nova Pro via Bedrock Converse API.

Sends image bytes directly to the model for visual content understanding,
returning a detailed description of the image contents.

Requirements: 3.1, 3.8
"""

import base64
import logging

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from ..config import AWS_REGION_LLM, VISION_MODEL_ID as _VISION_MODEL_ID

logger = logging.getLogger(__name__)

# Model configuration
VISION_MODEL_ID = _VISION_MODEL_ID

# Boto3 client configuration with retry logic
_client_config = Config(
    retries={
        "max_attempts": 3,
        "mode": "adaptive",
    }
)

_VISION_PROMPT = (
    "Analyze this image in detail for content compliance review. "
    "Describe the following aspects:\n"
    "1. Objects and items visible in the image\n"
    "2. The overall scene and setting\n"
    "3. Any text, signage, or written content visible\n"
    "4. People (if present): their appearance, actions, and attire\n"
    "5. Symbols, logos, or branding elements\n"
    "6. Any potentially sensitive content (religious symbols, cultural elements, "
    "suggestive imagery, political references)\n\n"
    "Provide a comprehensive description that would allow a compliance reviewer "
    "to assess the image without seeing it directly."
)


def _get_bedrock_client():
    """Create a Bedrock runtime client.

    Separated for testability — allows mocking in unit tests.
    """
    return boto3.client(
        "bedrock-runtime",
        region_name=AWS_REGION_LLM,
        config=_client_config,
    )


def analyze_image(image_bytes: bytes) -> str:
    """Analyze an image using Amazon Nova Pro via the Bedrock Converse API.

    Sends the image bytes directly to the model for visual content understanding
    and returns a detailed description of the image contents.

    Args:
        image_bytes: Raw bytes of the image file (JPEG, PNG, or WebP).

    Returns:
        A string containing a detailed visual description of the image.
        Returns an empty string if the model is unavailable or an error occurs.

    Requirements:
        3.1 - Send image to Vision_Model for visual content understanding
        3.8 - Handle Vision_Model unavailability gracefully
    """
    if not image_bytes:
        logger.warning("Empty image bytes provided to analyze_image")
        return ""

    try:
        client = _get_bedrock_client()

        # Determine image format from bytes (magic bytes)
        media_type = _detect_media_type(image_bytes)

        response = client.converse(
            modelId=VISION_MODEL_ID,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "image": {
                                "format": media_type,
                                "source": {
                                    "bytes": image_bytes,
                                },
                            },
                        },
                        {
                            "text": _VISION_PROMPT,
                        },
                    ],
                }
            ],
            inferenceConfig={
                "maxTokens": 2048,
                "temperature": 0.0,
                "topP": 1.0,
            },
        )

        # Extract text from the response
        output_message = response["output"]["message"]
        description = output_message["content"][0]["text"]

        logger.info(
            "Vision analysis completed successfully (model=%s, response_length=%d)",
            VISION_MODEL_ID,
            len(description),
        )

        return description

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        logger.error(
            "Bedrock vision model unavailable: %s - %s", error_code, error_message
        )
        return ""

    except Exception as e:
        logger.error("Unexpected error during image analysis: %s", str(e))
        return ""


def _detect_media_type(image_bytes: bytes) -> str:
    """Detect image format from magic bytes.

    Args:
        image_bytes: Raw image bytes.

    Returns:
        Media type string suitable for the Bedrock Converse API
        ('jpeg', 'png', or 'webp'). Defaults to 'jpeg' if unknown.
    """
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    elif image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "webp"
    elif image_bytes[:2] == b"\xff\xd8":
        return "jpeg"
    else:
        # Default to jpeg if format cannot be determined
        logger.warning("Could not detect image format from magic bytes, defaulting to jpeg")
        return "jpeg"
