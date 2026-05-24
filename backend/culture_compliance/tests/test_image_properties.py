"""Property-based tests for image pipeline validation.

Feature: content-compliance
Tests Properties 6 and 7 from the design document.

**Validates: Requirements 3.3, 3.5, 3.6, 3.7**
"""

import base64
import struct
from unittest.mock import patch

from hypothesis import given, settings, assume, strategies as st

from culture_compliance.models.schemas import (
    ContentSubmission,
    ContentType,
    Market,
    PipelineState,
)
from culture_compliance.nodes.step3_image_analysis import (
    MAX_IMAGE_SIZE_BYTES,
    MIN_RESOLUTION,
    SUPPORTED_FORMATS,
    image_processing,
)


# --- Helper functions to create synthetic image bytes ---


def _make_png_bytes(width: int, height: int, extra_size: int = 0) -> bytes:
    """Create minimal valid PNG bytes with specified dimensions.

    PNG structure: 8-byte signature + IHDR chunk (width at offset 16, height at 20).
    """
    signature = b"\x89PNG\r\n\x1a\n"
    # IHDR chunk: length(4) + "IHDR"(4) + width(4) + height(4) + bit_depth(1)
    # + color_type(1) + compression(1) + filter(1) + interlace(1) + CRC(4)
    ihdr_data = struct.pack(">II", width, height) + b"\x08\x02\x00\x00\x00"
    ihdr_length = struct.pack(">I", len(ihdr_data))
    # CRC placeholder (not validated by our code)
    ihdr_crc = b"\x00\x00\x00\x00"
    ihdr_chunk = ihdr_length + b"IHDR" + ihdr_data + ihdr_crc

    # IEND chunk to make it a complete PNG
    iend_chunk = b"\x00\x00\x00\x00IEND\xaeB`\x82"

    base = signature + ihdr_chunk + iend_chunk

    # Add padding to reach desired size
    if extra_size > 0:
        base += b"\x00" * extra_size

    return base


def _make_jpeg_bytes(width: int, height: int, extra_size: int = 0) -> bytes:
    """Create minimal valid JPEG bytes with specified dimensions.

    JPEG structure: SOI marker + SOF0 marker with dimensions.
    """
    # SOI marker
    soi = b"\xff\xd8"
    # APP0 marker (JFIF header) - minimal
    app0 = b"\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    # SOF0 marker: length(2) + precision(1) + height(2) + width(2) + components
    sof0_data = struct.pack(">BHH", 8, height, width) + b"\x03\x01\x11\x00\x02\x11\x01\x03\x11\x01"
    sof0_length = struct.pack(">H", len(sof0_data) + 2)
    sof0 = b"\xff\xc0" + sof0_length + sof0_data
    # EOI marker
    eoi = b"\xff\xd9"

    base = soi + app0 + sof0 + eoi

    # Add padding to reach desired size
    if extra_size > 0:
        # Insert padding before EOI
        base = soi + app0 + sof0 + b"\x00" * extra_size + eoi

    return base


def _make_webp_bytes(width: int, height: int, extra_size: int = 0) -> bytes:
    """Create minimal valid WebP bytes with VP8X extended format.

    WebP structure: RIFF header + WEBP + VP8X chunk with canvas dimensions.
    """
    # VP8X chunk: flags(4) + canvas_width_minus_1(3 bytes LE) + canvas_height_minus_1(3 bytes LE)
    flags = b"\x00\x00\x00\x00"
    w_minus_1 = width - 1
    h_minus_1 = height - 1
    canvas_w = bytes([
        w_minus_1 & 0xFF,
        (w_minus_1 >> 8) & 0xFF,
        (w_minus_1 >> 16) & 0xFF,
    ])
    canvas_h = bytes([
        h_minus_1 & 0xFF,
        (h_minus_1 >> 8) & 0xFF,
        (h_minus_1 >> 16) & 0xFF,
    ])
    vp8x_data = flags + canvas_w + canvas_h
    vp8x_chunk_size = struct.pack("<I", len(vp8x_data))
    vp8x_chunk = b"VP8X" + vp8x_chunk_size + vp8x_data

    # Padding for extra size
    padding = b"\x00" * extra_size

    # Total file size (after RIFF + size field)
    content = b"WEBP" + vp8x_chunk + padding
    file_size = struct.pack("<I", len(content))

    return b"RIFF" + file_size + content


def _make_invalid_format_bytes(extra_size: int = 0) -> bytes:
    """Create bytes that don't match any supported image format."""
    # GIF magic bytes (not supported)
    base = b"GIF89a" + b"\x00" * 20
    if extra_size > 0:
        base += b"\x00" * extra_size
    return base


# --- Strategies ---


@st.composite
def valid_image_metadata(draw):
    """Generate valid image metadata that should be accepted.

    Valid means: format in {jpeg, png, webp}, size <= 5MB, width >= 50, height >= 50.
    """
    fmt = draw(st.sampled_from(["jpeg", "png", "webp"]))
    # Size must be <= 5MB. We generate small images with controlled size.
    width = draw(st.integers(min_value=50, max_value=4000))
    height = draw(st.integers(min_value=50, max_value=4000))
    # Keep total size under 5MB - base image is small, add some extra
    extra_size = draw(st.integers(min_value=0, max_value=1000))
    return (fmt, width, height, extra_size)


@st.composite
def invalid_format_metadata(draw):
    """Generate image metadata with invalid format (not jpeg/png/webp)."""
    width = draw(st.integers(min_value=50, max_value=4000))
    height = draw(st.integers(min_value=50, max_value=4000))
    return ("invalid", width, height, 0)


@st.composite
def oversized_image_metadata(draw):
    """Generate image metadata that exceeds 5MB size limit."""
    fmt = draw(st.sampled_from(["jpeg", "png", "webp"]))
    width = draw(st.integers(min_value=50, max_value=4000))
    height = draw(st.integers(min_value=50, max_value=4000))
    # Extra size to push over 5MB
    extra_size = draw(st.integers(min_value=MAX_IMAGE_SIZE_BYTES, max_value=MAX_IMAGE_SIZE_BYTES + 10000))
    return (fmt, width, height, extra_size)


@st.composite
def underresolution_image_metadata(draw):
    """Generate image metadata with resolution below 50x50.

    At least one dimension must be below 50.
    """
    fmt = draw(st.sampled_from(["jpeg", "png", "webp"]))
    # At least one dimension below minimum
    choice = draw(st.sampled_from(["width_low", "height_low", "both_low"]))
    if choice == "width_low":
        width = draw(st.integers(min_value=1, max_value=49))
        height = draw(st.integers(min_value=1, max_value=4000))
    elif choice == "height_low":
        width = draw(st.integers(min_value=1, max_value=4000))
        height = draw(st.integers(min_value=1, max_value=49))
    else:
        width = draw(st.integers(min_value=1, max_value=49))
        height = draw(st.integers(min_value=1, max_value=49))
    return (fmt, width, height, 0)


def _build_image_bytes(fmt: str, width: int, height: int, extra_size: int) -> bytes:
    """Build synthetic image bytes based on format and dimensions."""
    if fmt == "png":
        return _make_png_bytes(width, height, extra_size)
    elif fmt == "jpeg":
        return _make_jpeg_bytes(width, height, extra_size)
    elif fmt == "webp":
        return _make_webp_bytes(width, height, extra_size)
    else:
        return _make_invalid_format_bytes(extra_size)


def _create_image_pipeline_state(image_bytes: bytes) -> PipelineState:
    """Create a PipelineState with base64-encoded image content."""
    content_b64 = base64.b64encode(image_bytes).decode("utf-8")
    submission = ContentSubmission(
        content=content_b64,
        content_type=ContentType.IMAGE,
        market=Market.MALAYSIA,
    )
    return PipelineState(
        submission=submission,
        content_type=ContentType.IMAGE,
        market=Market.MALAYSIA,
    )


# --- Property 6: Image File Validation ---
# **Validates: Requirements 3.5, 3.6, 3.7**


@settings(max_examples=100, deadline=5000)
@given(metadata=valid_image_metadata())
def test_property_6_valid_images_accepted(metadata):
    """Property 6: Image File Validation - valid images are accepted.

    For any image file metadata (format, size_bytes, width, height), the image
    pipeline SHALL accept the file if and only if: format is in {JPEG, PNG, WebP}
    AND size_bytes <= 5,242,880 AND width >= 50 AND height >= 50.

    This test verifies the acceptance case: valid format, valid size, valid resolution.

    **Validates: Requirements 3.5, 3.6, 3.7**
    """
    fmt, width, height, extra_size = metadata
    image_bytes = _build_image_bytes(fmt, width, height, extra_size)

    # Ensure we haven't accidentally exceeded size limit
    assume(len(image_bytes) <= MAX_IMAGE_SIZE_BYTES)

    state = _create_image_pipeline_state(image_bytes)

    # Mock vision and OCR services to isolate validation logic
    with patch(
        "culture_compliance.nodes.step3_image_analysis.analyze_image",
        return_value="Visual description of the image",
    ), patch(
        "culture_compliance.nodes.step3_image_analysis.extract_text_from_image",
        return_value="Some OCR text",
    ):
        result_state = image_processing(state)

    # Valid images should NOT produce validation errors
    validation_errors = [
        e for e in result_state.errors if e.get("error_type") == "validation"
    ]
    assert len(validation_errors) == 0, (
        f"Valid image (format={fmt}, width={width}, height={height}, "
        f"size={len(image_bytes)}) was rejected with errors: {validation_errors}"
    )

    # Should have unified content set
    assert result_state.unified_content is not None, (
        f"Valid image (format={fmt}, width={width}, height={height}) "
        f"did not produce unified_content"
    )


@settings(max_examples=100, deadline=5000)
@given(metadata=invalid_format_metadata())
def test_property_6_invalid_format_rejected(metadata):
    """Property 6: Image File Validation - invalid formats are rejected.

    For any image file with format NOT in {JPEG, PNG, WebP}, the image pipeline
    SHALL reject the file with an appropriate error message.

    **Validates: Requirements 3.5, 3.7**
    """
    fmt, width, height, extra_size = metadata
    image_bytes = _build_image_bytes(fmt, width, height, extra_size)

    state = _create_image_pipeline_state(image_bytes)

    result_state = image_processing(state)

    # Invalid format should produce a validation error
    validation_errors = [
        e for e in result_state.errors if e.get("error_type") == "validation"
    ]
    assert len(validation_errors) > 0, (
        f"Invalid format image was not rejected (format={fmt})"
    )

    # Error message should mention supported formats
    error_msg = validation_errors[0]["message"].lower()
    assert "format" in error_msg or "supported" in error_msg, (
        f"Error message does not mention format: {validation_errors[0]['message']}"
    )


@settings(max_examples=100, deadline=5000)
@given(metadata=oversized_image_metadata())
def test_property_6_oversized_images_rejected(metadata):
    """Property 6: Image File Validation - oversized images are rejected.

    For any image file with size_bytes > 5,242,880, the image pipeline SHALL
    reject the file with an appropriate error message.

    **Validates: Requirements 3.6**
    """
    fmt, width, height, extra_size = metadata
    image_bytes = _build_image_bytes(fmt, width, height, extra_size)

    # Verify we actually exceeded the limit
    assume(len(image_bytes) > MAX_IMAGE_SIZE_BYTES)

    state = _create_image_pipeline_state(image_bytes)

    result_state = image_processing(state)

    # Oversized images should produce a validation error
    validation_errors = [
        e for e in result_state.errors if e.get("error_type") == "validation"
    ]
    assert len(validation_errors) > 0, (
        f"Oversized image ({len(image_bytes)} bytes) was not rejected"
    )

    # Error message should mention size
    error_msg = validation_errors[0]["message"].lower()
    assert "size" in error_msg or "mb" in error_msg or "bytes" in error_msg, (
        f"Error message does not mention size: {validation_errors[0]['message']}"
    )


@settings(max_examples=100, deadline=5000)
@given(metadata=underresolution_image_metadata())
def test_property_6_underresolution_images_rejected(metadata):
    """Property 6: Image File Validation - under-resolution images are rejected.

    For any image file with width < 50 OR height < 50, the image pipeline SHALL
    reject the file with an appropriate error message.

    **Validates: Requirements 3.5**
    """
    fmt, width, height, extra_size = metadata
    image_bytes = _build_image_bytes(fmt, width, height, extra_size)

    # Ensure size is within limit so we test resolution specifically
    assume(len(image_bytes) <= MAX_IMAGE_SIZE_BYTES)

    state = _create_image_pipeline_state(image_bytes)

    result_state = image_processing(state)

    # Under-resolution images should produce a validation error
    validation_errors = [
        e for e in result_state.errors if e.get("error_type") == "validation"
    ]
    assert len(validation_errors) > 0, (
        f"Under-resolution image (width={width}, height={height}) was not rejected"
    )

    # Error message should mention resolution
    error_msg = validation_errors[0]["message"].lower()
    assert "resolution" in error_msg or "pixel" in error_msg or "minimum" in error_msg, (
        f"Error message does not mention resolution: {validation_errors[0]['message']}"
    )


# --- Property 7: Image Content Combination Completeness ---
# **Validates: Requirements 3.3**


@settings(max_examples=100, deadline=5000)
@given(
    visual_description=st.text(min_size=1, max_size=500).filter(lambda s: s.strip()),
    ocr_text=st.text(min_size=1, max_size=500).filter(lambda s: s.strip()),
)
def test_property_7_unified_content_contains_both(visual_description, ocr_text):
    """Property 7: Image Content Combination Completeness.

    For any non-empty visual description string and non-empty OCR text string,
    the unified content description produced by the image pipeline SHALL contain
    both the visual description content and the OCR text content as substrings
    (order-independent).

    **Validates: Requirements 3.3**
    """
    # Create a valid PNG image (100x100 to pass validation)
    image_bytes = _make_png_bytes(100, 100)
    state = _create_image_pipeline_state(image_bytes)

    # Mock vision and OCR services to return our generated strings
    with patch(
        "culture_compliance.nodes.step3_image_analysis.analyze_image",
        return_value=visual_description,
    ), patch(
        "culture_compliance.nodes.step3_image_analysis.extract_text_from_image",
        return_value=ocr_text,
    ):
        result_state = image_processing(state)

    # Should not have validation errors
    validation_errors = [
        e for e in result_state.errors if e.get("error_type") == "validation"
    ]
    assert len(validation_errors) == 0, (
        f"Valid image was rejected: {validation_errors}"
    )

    # Unified content must exist
    assert result_state.unified_content is not None, (
        "unified_content was not set despite successful vision and OCR"
    )

    # Unified content must contain both the visual description and OCR text
    assert visual_description in result_state.unified_content, (
        f"Visual description not found in unified_content.\n"
        f"Visual description: {visual_description!r}\n"
        f"Unified content: {result_state.unified_content!r}"
    )
    assert ocr_text in result_state.unified_content, (
        f"OCR text not found in unified_content.\n"
        f"OCR text: {ocr_text!r}\n"
        f"Unified content: {result_state.unified_content!r}"
    )
