"""Vision service for image analysis using Gemini.

Sends image bytes directly to the model for visual content understanding,
returning a detailed description of the image contents.
"""

import logging
from ..gemini_client import analyze_image as gemini_analyze_image

logger = logging.getLogger(__name__)

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


def analyze_image(image_bytes: bytes) -> str:
    """Analyze an image using Gemini.

    Sends the image bytes directly to the model for visual content understanding
    and returns a detailed description of the image contents.

    Args:
        image_bytes: Raw bytes of the image file (JPEG, PNG, or WebP).

    Returns:
        A string containing a detailed visual description of the image.
        Returns an empty string if an error occurs.
    """
    if not image_bytes:
        logger.warning("Empty image bytes provided to analyze_image")
        return ""

    try:
        # Determine image format from bytes (magic bytes)
        media_type = _detect_media_type(image_bytes)
        mime_type = f"image/{media_type}"

        description = gemini_analyze_image(
            image_bytes=image_bytes,
            prompt=_VISION_PROMPT,
            mime_type=mime_type,
        )

        logger.info(
            "Vision analysis completed successfully using Gemini (response_length=%d)",
            len(description),
        )

        return description.strip()

    except Exception as e:
        logger.error("Unexpected error during image analysis: %s", str(e))
        return ""


def _detect_media_type(image_bytes: bytes) -> str:
    """Detect image format from magic bytes.

    Args:
        image_bytes: Raw image bytes.

    Returns:
        Media type string suitable for the Gemini API
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

