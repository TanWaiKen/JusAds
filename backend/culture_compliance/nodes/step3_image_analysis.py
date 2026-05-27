"""Step 3: Image processing node for the compliance pipeline.

Validates image format, size, and resolution, then invokes the vision
and OCR services to produce a unified content description for downstream
compliance evaluation.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9
"""

import base64
import logging
import struct
from typing import Optional, Tuple

from culture_compliance.models.schemas import PipelineState
from culture_compliance.services.ocr import extract_text_from_image
from culture_compliance.services.vision import analyze_image

logger = logging.getLogger(__name__)

# Constraints
MAX_IMAGE_SIZE_BYTES = 5_242_880  # 5 MB
MIN_RESOLUTION = 50  # minimum 50x50 pixels

# Supported formats mapped by magic bytes
SUPPORTED_FORMATS = {"jpeg", "png", "webp"}


def _detect_format(image_bytes: bytes) -> Optional[str]:
    """Detect image format from magic bytes.

    Returns:
        Format string ('jpeg', 'png', 'webp') or None if unrecognized.
    """
    if len(image_bytes) < 2:
        return None
    if len(image_bytes) >= 8 and image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if len(image_bytes) >= 12 and image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "webp"
    if image_bytes[:2] == b"\xff\xd8":
        return "jpeg"
    return None


def _get_png_dimensions(image_bytes: bytes) -> Optional[Tuple[int, int]]:
    """Extract width and height from a PNG file's IHDR chunk.

    PNG structure: 8-byte signature, then IHDR chunk with width (4 bytes)
    and height (4 bytes) at offsets 16 and 20.
    """
    if len(image_bytes) < 24:
        return None
    try:
        width = struct.unpack(">I", image_bytes[16:20])[0]
        height = struct.unpack(">I", image_bytes[20:24])[0]
        return (width, height)
    except struct.error:
        return None


def _get_jpeg_dimensions(image_bytes: bytes) -> Optional[Tuple[int, int]]:
    """Extract width and height from a JPEG file by scanning SOF markers.

    JPEG stores dimensions in Start of Frame (SOF) markers (0xFFC0-0xFFC3).
    """
    if len(image_bytes) < 4:
        return None

    i = 2  # Skip SOI marker (0xFFD8)
    while i < len(image_bytes) - 1:
        if image_bytes[i] != 0xFF:
            i += 1
            continue

        marker = image_bytes[i + 1]

        # SOF markers: 0xC0, 0xC1, 0xC2, 0xC3
        if marker in (0xC0, 0xC1, 0xC2, 0xC3):
            if i + 9 >= len(image_bytes):
                return None
            # SOF segment: length(2) + precision(1) + height(2) + width(2)
            height = struct.unpack(">H", image_bytes[i + 5 : i + 7])[0]
            width = struct.unpack(">H", image_bytes[i + 7 : i + 9])[0]
            return (width, height)

        # Skip non-SOF markers
        if marker == 0xD9:  # EOI
            break
        if marker in (0xD0, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0x01):
            # Standalone markers (no length field)
            i += 2
            continue

        # Read segment length and skip
        if i + 3 >= len(image_bytes):
            break
        seg_length = struct.unpack(">H", image_bytes[i + 2 : i + 4])[0]
        i += 2 + seg_length

    return None


def _get_webp_dimensions(image_bytes: bytes) -> Optional[Tuple[int, int]]:
    """Extract width and height from a WebP file.

    Supports VP8 (lossy), VP8L (lossless), and VP8X (extended) chunks.
    """
    if len(image_bytes) < 30:
        return None

    try:
        # Check for VP8X (extended format)
        if image_bytes[12:16] == b"VP8X":
            # Canvas width and height are at bytes 24-29 (3 bytes each, little-endian)
            width = (
                image_bytes[24]
                | (image_bytes[25] << 8)
                | (image_bytes[26] << 16)
            ) + 1
            height = (
                image_bytes[27]
                | (image_bytes[28] << 8)
                | (image_bytes[29] << 16)
            ) + 1
            return (width, height)

        # Check for VP8L (lossless)
        if image_bytes[12:16] == b"VP8L":
            if len(image_bytes) < 25:
                return None
            # Signature byte at offset 21, then 4 bytes with packed width/height
            bits = struct.unpack_from("<I", image_bytes, 21)[0]
            width = (bits & 0x3FFF) + 1
            height = ((bits >> 14) & 0x3FFF) + 1
            return (width, height)

        # Check for VP8 (lossy)
        if image_bytes[12:16] == b"VP8 ":
            # Frame header starts at offset 23 (after chunk header)
            # First 3 bytes are frame tag, then 3 bytes are start code
            offset = 20  # chunk size starts at 16, data at 20
            # Skip chunk size (4 bytes) to get to VP8 bitstream
            # VP8 bitstream: 3 bytes frame tag + 3 bytes start code (9D 01 2A)
            # then 2 bytes width + 2 bytes height (little-endian)
            vp8_offset = offset + 4  # skip chunk length
            if len(image_bytes) < vp8_offset + 10:
                return None
            # Look for start code 9D 01 2A
            sc_offset = vp8_offset + 3
            if (
                image_bytes[sc_offset] == 0x9D
                and image_bytes[sc_offset + 1] == 0x01
                and image_bytes[sc_offset + 2] == 0x2A
            ):
                width = struct.unpack_from("<H", image_bytes, sc_offset + 3)[0] & 0x3FFF
                height = struct.unpack_from("<H", image_bytes, sc_offset + 5)[0] & 0x3FFF
                return (width, height)

        return None
    except (IndexError, struct.error):
        return None


def _get_image_dimensions(
    image_bytes: bytes, fmt: str
) -> Optional[Tuple[int, int]]:
    """Get image dimensions based on detected format.

    Args:
        image_bytes: Raw image bytes.
        fmt: Detected format ('jpeg', 'png', 'webp').

    Returns:
        Tuple of (width, height) or None if dimensions cannot be determined.
    """
    if fmt == "png":
        return _get_png_dimensions(image_bytes)
    elif fmt == "jpeg":
        return _get_jpeg_dimensions(image_bytes)
    elif fmt == "webp":
        return _get_webp_dimensions(image_bytes)
    return None


def image_processing(state: PipelineState) -> PipelineState:
    """Extract visual understanding + OCR text from an image file.

    Performs the following steps:
    1. Decode base64 content from state.submission.content
    2. Validate format (JPEG/PNG/WebP via magic bytes)
    3. Validate size (≤5 MB)
    4. Validate resolution (≥50x50 pixels)
    5. Call vision service for visual description
    6. Call OCR service for text extraction
    7. Combine results into unified_content
    8. Handle partial failures gracefully

    Args:
        state: The current pipeline state containing the submission.

    Returns:
        Updated PipelineState with unified_content set, or with errors
        appended if validation fails.
    """
    content = state.submission.content

    # Step 1: Decode base64 content
    try:
        image_bytes = base64.b64decode(content)
    except Exception as e:
        logger.error("Failed to decode base64 image content: %s", str(e))
        state.errors.append({
            "error_type": "validation",
            "message": "Invalid base64-encoded image content",
            "details": {"reason": str(e)},
        })
        return state

    # Step 2: Validate format via magic bytes
    fmt = _detect_format(image_bytes)
    if fmt is None or fmt not in SUPPORTED_FORMATS:
        state.errors.append({
            "error_type": "validation",
            "message": (
                "Unsupported image format. "
                "Supported formats: JPEG, PNG, WebP"
            ),
            "details": {"supported_formats": ["JPEG", "PNG", "WebP"]},
        })
        return state

    # Step 3: Validate size (≤5 MB)
    if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
        state.errors.append({
            "error_type": "validation",
            "message": (
                f"Image file exceeds maximum size of 5 MB. "
                f"Received: {len(image_bytes)} bytes"
            ),
            "details": {
                "max_size_bytes": MAX_IMAGE_SIZE_BYTES,
                "actual_size_bytes": len(image_bytes),
            },
        })
        return state

    # Step 4: Validate resolution (≥50x50)
    dimensions = _get_image_dimensions(image_bytes, fmt)
    if dimensions is None:
        logger.warning("Could not determine image dimensions for format: %s", fmt)
        # Allow processing to continue if dimensions can't be determined
    else:
        width, height = dimensions
        if width < MIN_RESOLUTION or height < MIN_RESOLUTION:
            state.errors.append({
                "error_type": "validation",
                "message": (
                    f"Image resolution too low. Minimum: {MIN_RESOLUTION}x{MIN_RESOLUTION} pixels. "
                    f"Received: {width}x{height}"
                ),
                "details": {
                    "min_width": MIN_RESOLUTION,
                    "min_height": MIN_RESOLUTION,
                    "actual_width": width,
                    "actual_height": height,
                },
            })
            return state

    # Step 5: Call vision service
    visual_description: Optional[str] = None
    vision_failed = False
    try:
        visual_description = analyze_image(image_bytes)
        if visual_description:
            state.models_used.append("amazon.nova-pro-v1:0")
        else:
            vision_failed = True
    except Exception as e:
        logger.error("Vision service failed: %s", str(e))
        vision_failed = True

    if vision_failed:
        state.warnings.append({
            "step_name": "vision_analysis",
            "description": (
                "Vision model unavailable or returned empty result. "
                "Proceeding with OCR-extracted text only."
            ),
            "result_may_be_incomplete": True,
        })

    # Step 6: Call OCR service
    extracted_text: Optional[str] = None
    ocr_failed = False
    try:
        extracted_text = extract_text_from_image(image_bytes)
        if extracted_text:
            state.extracted_text = extracted_text
            if "amazon.nova-pro-v1:0" not in state.models_used:
                state.models_used.append("amazon.nova-pro-v1:0")
        else:
            ocr_failed = True
    except Exception as e:
        logger.error("OCR service failed: %s", str(e))
        ocr_failed = True

    if ocr_failed:
        state.warnings.append({
            "step_name": "ocr_extraction",
            "description": (
                "OCR extraction unavailable or returned empty result. "
                "Proceeding with visual description only."
            ),
            "result_may_be_incomplete": True,
        })

    # Step 7: Combine results into unified content description
    if vision_failed and ocr_failed:
        state.errors.append({
            "error_type": "service_unavailable",
            "message": (
                "Both vision analysis and OCR extraction failed. "
                "Cannot produce content description for compliance evaluation."
            ),
            "details": {},
        })
        return state

    # Build unified content
    parts = []
    if visual_description:
        parts.append(f"[Visual Description]\n{visual_description}")
        state.visual_description = visual_description

    if extracted_text:
        parts.append(f"[OCR Extracted Text]\n{extracted_text}")

    state.unified_content = "\n\n".join(parts)

    logger.info(
        "Image processing completed: vision=%s, ocr=%s, unified_length=%d",
        "success" if not vision_failed else "failed",
        "success" if not ocr_failed else "failed",
        len(state.unified_content),
    )

    return state
