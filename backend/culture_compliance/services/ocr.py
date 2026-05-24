"""OCR text extraction service using Amazon Nova Pro.

Uses Amazon Nova Pro's vision capabilities via the Bedrock Converse API
to extract all visible text from images, including overlays, signage,
captions, watermarks, and labels.
"""

import logging

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from ..config import AWS_REGION_LLM, VISION_MODEL_ID

logger = logging.getLogger(__name__)

# Model configuration
_MODEL_ID = VISION_MODEL_ID

# OCR-specific prompt designed to extract ALL visible text
_OCR_PROMPT = (
    "Extract ALL text visible in this image. Include every piece of text you can see, "
    "regardless of size, position, or prominence. This includes but is not limited to:\n"
    "- Overlays and superimposed text\n"
    "- Signage and billboards\n"
    "- Captions and subtitles\n"
    "- Watermarks\n"
    "- Labels and product names\n"
    "- Logos with text\n"
    "- Fine print and disclaimers\n"
    "- Handwritten text\n"
    "- Text on clothing or objects\n\n"
    "Return ONLY the extracted text, preserving the original language. "
    "Separate distinct text elements with newlines. "
    "If no text is visible in the image, return an empty response."
)

# Boto3 client configuration with retry logic
_client_config = Config(
    retries={
        "max_attempts": 3,
        "mode": "adaptive",
    }
)


def _get_bedrock_client():
    """Create a bedrock-runtime client.

    Separated for testability.
    """
    return boto3.client(
        "bedrock-runtime",
        region_name=AWS_REGION_LLM,
        config=_client_config,
    )


def extract_text_from_image(image_bytes: bytes) -> str:
    """Extract all visible text from an image using Amazon Nova Pro.

    Uses the Bedrock Converse API to send the image to Amazon Nova Pro
    with an OCR-specific prompt that requests extraction of all visible
    text including overlays, signage, captions, watermarks, and labels.

    Args:
        image_bytes: Raw image file bytes (JPEG, PNG, or WebP).

    Returns:
        Extracted text as a string. Returns empty string if no text is
        found or if OCR processing fails.

    Raises:
        No exceptions are raised to the caller. All errors are handled
        gracefully with logging and an empty string return.
    """
    if not image_bytes:
        logger.warning("OCR called with empty image bytes")
        return ""

    try:
        client = _get_bedrock_client()

        # Determine image format from bytes (magic bytes)
        media_type = _detect_media_type(image_bytes)

        response = client.converse(
            modelId=_MODEL_ID,
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
                            "text": _OCR_PROMPT,
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

        # Extract text from response
        extracted_text = response["output"]["message"]["content"][0]["text"]

        logger.info(
            "OCR extraction completed: %d characters extracted",
            len(extracted_text),
        )
        return extracted_text.strip()

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        logger.error(
            "Bedrock API error during OCR extraction: %s - %s",
            error_code,
            str(e),
        )
        return ""
    except (KeyError, IndexError) as e:
        logger.error("Unexpected response structure from Bedrock: %s", str(e))
        return ""
    except Exception as e:
        logger.error("Unexpected error during OCR extraction: %s", str(e))
        return ""


def _detect_media_type(image_bytes: bytes) -> str:
    """Detect image format from magic bytes.

    Args:
        image_bytes: Raw image file bytes.

    Returns:
        Media type string suitable for the Bedrock Converse API
        ('jpeg', 'png', or 'webp'). Defaults to 'jpeg' if format
        cannot be determined.
    """
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    elif image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "webp"
    elif image_bytes[:2] == b"\xff\xd8":
        return "jpeg"
    else:
        # Default to JPEG if format cannot be determined
        logger.warning("Could not detect image format, defaulting to JPEG")
        return "jpeg"
