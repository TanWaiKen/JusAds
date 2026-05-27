"""OCR text extraction service using Gemini."""

import logging
from ..gemini_client import analyze_image as gemini_analyze_image

logger = logging.getLogger(__name__)

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


def extract_text_from_image(image_bytes: bytes) -> str:
    """Extract all visible text from an image using Gemini.

    Args:
        image_bytes: Raw image file bytes (JPEG, PNG, or WebP).

    Returns:
        Extracted text as a string. Returns empty string if no text is
        found or if OCR processing fails.
    """
    if not image_bytes:
        logger.warning("OCR called with empty image bytes")
        return ""

    try:
        # Determine image format from bytes (magic bytes)
        media_type = _detect_media_type(image_bytes)
        mime_type = f"image/{media_type}"

        extracted_text = gemini_analyze_image(
            image_bytes=image_bytes,
            prompt=_OCR_PROMPT,
            mime_type=mime_type,
        )

        logger.info(
            "OCR extraction completed using Gemini: %d characters extracted",
            len(extracted_text),
        )
        return extracted_text.strip()

    except Exception as e:
        logger.error("Unexpected error during OCR extraction: %s", str(e))
        return ""


def _detect_media_type(image_bytes: bytes) -> str:
    """Detect image format from magic bytes.

    Args:
        image_bytes: Raw image file bytes.

    Returns:
        Media type string suitable for the Gemini API
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

