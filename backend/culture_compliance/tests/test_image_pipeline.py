"""Unit tests for the image processing pipeline node.

Tests the image_processing function with mocked vision and OCR services to verify:
- Format validation (accept JPEG/PNG/WebP, reject others)
- Size validation (reject >5 MB)
- Resolution validation (reject <50x50)
- Vision model fallback to OCR-only
- OCR fallback to vision-only

Requirements: 3.5, 3.6, 3.7, 3.8, 3.9
"""

import base64
import struct
from unittest.mock import patch

import pytest

from culture_compliance.models.schemas import (
    ContentSubmission,
    ContentType,
    Market,
    PipelineState,
)
from culture_compliance.nodes.step3_image_analysis import (
    image_processing,
    MAX_IMAGE_SIZE_BYTES,
    MIN_RESOLUTION,
    _detect_format,
    _get_png_dimensions,
    _get_jpeg_dimensions,
    _get_webp_dimensions,
)


# --- Helpers to create synthetic image bytes ---


def _make_png_bytes(width: int, height: int, total_size: int = 100) -> bytes:
    """Create synthetic PNG bytes with correct magic bytes and IHDR dimensions.

    PNG structure: 8-byte signature + IHDR chunk with width/height at offsets 16-23.
    """
    signature = b"\x89PNG\r\n\x1a\n"
    # IHDR chunk: length(4) + "IHDR"(4) + width(4) + height(4) + ...
    ihdr_length = struct.pack(">I", 13)  # IHDR data is always 13 bytes
    ihdr_type = b"IHDR"
    ihdr_width = struct.pack(">I", width)
    ihdr_height = struct.pack(">I", height)
    # bit depth(1) + color type(1) + compression(1) + filter(1) + interlace(1)
    ihdr_rest = b"\x08\x02\x00\x00\x00"

    header = signature + ihdr_length + ihdr_type + ihdr_width + ihdr_height + ihdr_rest
    # Pad to desired total size
    padding_needed = max(0, total_size - len(header))
    return header + b"\x00" * padding_needed


def _make_jpeg_bytes(width: int, height: int, total_size: int = 100) -> bytes:
    """Create synthetic JPEG bytes with SOI marker and SOF0 segment containing dimensions.

    JPEG structure: SOI(2) + APP0 marker segment + SOF0 with height/width.
    """
    soi = b"\xff\xd8"
    # APP0 marker (minimal, just to have a segment before SOF)
    app0_marker = b"\xff\xe0"
    app0_length = struct.pack(">H", 16)  # length includes itself
    app0_data = b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"

    # SOF0 marker with dimensions
    sof0_marker = b"\xff\xc0"
    sof0_length = struct.pack(">H", 11)  # length of SOF0 segment
    sof0_precision = b"\x08"  # 8-bit precision
    sof0_height = struct.pack(">H", height)
    sof0_width = struct.pack(">H", width)
    sof0_components = b"\x03"  # 3 components (YCbCr)
    # Component specs (3 bytes each × 3 components = 9 bytes, but we keep it minimal)
    sof0_rest = b"\x01\x11\x00"

    header = (
        soi + app0_marker + app0_length + app0_data
        + sof0_marker + sof0_length + sof0_precision
        + sof0_height + sof0_width + sof0_components + sof0_rest
    )
    padding_needed = max(0, total_size - len(header))
    return header + b"\x00" * padding_needed


def _make_webp_bytes(width: int, height: int, total_size: int = 100) -> bytes:
    """Create synthetic WebP bytes with VP8X extended format containing dimensions.

    WebP VP8X structure: RIFF(4) + size(4) + WEBP(4) + VP8X(4) + chunk_size(4)
    + flags(4) + canvas_width(3) + canvas_height(3).
    """
    riff = b"RIFF"
    file_size = struct.pack("<I", total_size - 8)  # file size minus RIFF header
    webp = b"WEBP"
    vp8x = b"VP8X"
    chunk_size = struct.pack("<I", 10)  # VP8X chunk data is 10 bytes
    flags = struct.pack("<I", 0)  # no special flags

    # Canvas width and height are stored as (value - 1) in 3 bytes little-endian
    w = width - 1
    h = height - 1
    canvas_width = bytes([w & 0xFF, (w >> 8) & 0xFF, (w >> 16) & 0xFF])
    canvas_height = bytes([h & 0xFF, (h >> 8) & 0xFF, (h >> 16) & 0xFF])

    header = riff + file_size + webp + vp8x + chunk_size + flags + canvas_width + canvas_height
    padding_needed = max(0, total_size - len(header))
    return header + b"\x00" * padding_needed


def _make_gif_bytes(total_size: int = 100) -> bytes:
    """Create synthetic GIF bytes (unsupported format)."""
    gif_header = b"GIF89a"
    padding_needed = max(0, total_size - len(gif_header))
    return gif_header + b"\x00" * padding_needed


def _make_bmp_bytes(total_size: int = 100) -> bytes:
    """Create synthetic BMP bytes (unsupported format)."""
    bmp_header = b"BM" + b"\x00" * 12
    padding_needed = max(0, total_size - len(bmp_header))
    return bmp_header + b"\x00" * padding_needed


def _make_pipeline_state(image_bytes: bytes) -> PipelineState:
    """Create a PipelineState with base64-encoded image content."""
    content = base64.b64encode(image_bytes).decode("utf-8")
    submission = ContentSubmission(
        content=content,
        content_type=ContentType.IMAGE,
        market=Market.MALAYSIA,
    )
    return PipelineState(
        submission=submission,
        content_type=ContentType.IMAGE,
        market=Market.MALAYSIA,
    )


# --- Format Validation Tests ---


class TestFormatValidation:
    """Test that image format validation accepts JPEG/PNG/WebP and rejects others.

    Requirements: 3.5, 3.7
    """

    def test_accepts_jpeg_format(self):
        """JPEG images should pass format validation."""
        jpeg_bytes = _make_jpeg_bytes(100, 100)
        assert _detect_format(jpeg_bytes) == "jpeg"

    def test_accepts_png_format(self):
        """PNG images should pass format validation."""
        png_bytes = _make_png_bytes(100, 100)
        assert _detect_format(png_bytes) == "png"

    def test_accepts_webp_format(self):
        """WebP images should pass format validation."""
        webp_bytes = _make_webp_bytes(100, 100)
        assert _detect_format(webp_bytes) == "webp"

    def test_rejects_gif_format(self):
        """GIF images should be rejected (not in supported formats)."""
        gif_bytes = _make_gif_bytes()
        assert _detect_format(gif_bytes) is None

    def test_rejects_bmp_format(self):
        """BMP images should be rejected (not in supported formats)."""
        bmp_bytes = _make_bmp_bytes()
        assert _detect_format(bmp_bytes) is None

    def test_rejects_random_bytes(self):
        """Random bytes should be rejected."""
        random_bytes = b"\x00\x01\x02\x03\x04\x05\x06\x07" * 10
        assert _detect_format(random_bytes) is None

    def test_rejects_empty_bytes(self):
        """Empty bytes should be rejected."""
        assert _detect_format(b"") is None

    def test_rejects_single_byte(self):
        """Single byte should be rejected."""
        assert _detect_format(b"\xff") is None

    @patch("culture_compliance.nodes.step3_image_analysis.analyze_image")
    @patch("culture_compliance.nodes.step3_image_analysis.extract_text_from_image")
    def test_pipeline_rejects_gif(self, mock_ocr, mock_vision):
        """Full pipeline should reject GIF with error message listing supported formats."""
        gif_bytes = _make_gif_bytes()
        state = _make_pipeline_state(gif_bytes)

        result = image_processing(state)

        assert len(result.errors) == 1
        assert result.errors[0]["error_type"] == "validation"
        assert "Supported formats" in result.errors[0]["message"] or "Unsupported" in result.errors[0]["message"]
        # Vision and OCR should not be called
        mock_vision.assert_not_called()
        mock_ocr.assert_not_called()

    @patch("culture_compliance.nodes.step3_image_analysis.analyze_image")
    @patch("culture_compliance.nodes.step3_image_analysis.extract_text_from_image")
    def test_pipeline_accepts_png(self, mock_ocr, mock_vision):
        """Full pipeline should accept PNG and proceed to vision/OCR."""
        mock_vision.return_value = "A test image description"
        mock_ocr.return_value = "Some text in image"

        png_bytes = _make_png_bytes(100, 100)
        state = _make_pipeline_state(png_bytes)

        result = image_processing(state)

        assert len(result.errors) == 0
        mock_vision.assert_called_once()
        mock_ocr.assert_called_once()


# --- Size Validation Tests ---


class TestSizeValidation:
    """Test that images exceeding 5 MB are rejected.

    Requirements: 3.6
    """

    @patch("culture_compliance.nodes.step3_image_analysis.analyze_image")
    @patch("culture_compliance.nodes.step3_image_analysis.extract_text_from_image")
    def test_rejects_image_over_5mb(self, mock_ocr, mock_vision):
        """Images larger than 5 MB should be rejected with an error."""
        # Create a PNG that exceeds 5 MB
        oversized_bytes = _make_png_bytes(100, 100, total_size=MAX_IMAGE_SIZE_BYTES + 1)
        state = _make_pipeline_state(oversized_bytes)

        result = image_processing(state)

        assert len(result.errors) == 1
        assert result.errors[0]["error_type"] == "validation"
        assert "5 MB" in result.errors[0]["message"]
        assert result.errors[0]["details"]["max_size_bytes"] == MAX_IMAGE_SIZE_BYTES
        # Vision and OCR should not be called
        mock_vision.assert_not_called()
        mock_ocr.assert_not_called()

    @patch("culture_compliance.nodes.step3_image_analysis.analyze_image")
    @patch("culture_compliance.nodes.step3_image_analysis.extract_text_from_image")
    def test_accepts_image_exactly_5mb(self, mock_ocr, mock_vision):
        """Images exactly at 5 MB should be accepted."""
        mock_vision.return_value = "Description"
        mock_ocr.return_value = "Text"

        exact_bytes = _make_png_bytes(100, 100, total_size=MAX_IMAGE_SIZE_BYTES)
        state = _make_pipeline_state(exact_bytes)

        result = image_processing(state)

        assert len(result.errors) == 0
        mock_vision.assert_called_once()

    @patch("culture_compliance.nodes.step3_image_analysis.analyze_image")
    @patch("culture_compliance.nodes.step3_image_analysis.extract_text_from_image")
    def test_accepts_small_image(self, mock_ocr, mock_vision):
        """Small images well under 5 MB should be accepted."""
        mock_vision.return_value = "Description"
        mock_ocr.return_value = "Text"

        small_bytes = _make_png_bytes(100, 100, total_size=1024)
        state = _make_pipeline_state(small_bytes)

        result = image_processing(state)

        assert len(result.errors) == 0


# --- Resolution Validation Tests ---


class TestResolutionValidation:
    """Test that images below 50x50 pixels are rejected.

    Requirements: 3.5
    """

    @patch("culture_compliance.nodes.step3_image_analysis.analyze_image")
    @patch("culture_compliance.nodes.step3_image_analysis.extract_text_from_image")
    def test_rejects_width_below_minimum(self, mock_ocr, mock_vision):
        """Images with width < 50 pixels should be rejected."""
        small_width_bytes = _make_png_bytes(49, 100)
        state = _make_pipeline_state(small_width_bytes)

        result = image_processing(state)

        assert len(result.errors) == 1
        assert result.errors[0]["error_type"] == "validation"
        assert "resolution" in result.errors[0]["message"].lower() or "Resolution" in result.errors[0]["message"]
        assert result.errors[0]["details"]["actual_width"] == 49
        mock_vision.assert_not_called()
        mock_ocr.assert_not_called()

    @patch("culture_compliance.nodes.step3_image_analysis.analyze_image")
    @patch("culture_compliance.nodes.step3_image_analysis.extract_text_from_image")
    def test_rejects_height_below_minimum(self, mock_ocr, mock_vision):
        """Images with height < 50 pixels should be rejected."""
        small_height_bytes = _make_png_bytes(100, 49)
        state = _make_pipeline_state(small_height_bytes)

        result = image_processing(state)

        assert len(result.errors) == 1
        assert result.errors[0]["error_type"] == "validation"
        assert result.errors[0]["details"]["actual_height"] == 49
        mock_vision.assert_not_called()
        mock_ocr.assert_not_called()

    @patch("culture_compliance.nodes.step3_image_analysis.analyze_image")
    @patch("culture_compliance.nodes.step3_image_analysis.extract_text_from_image")
    def test_rejects_both_dimensions_below_minimum(self, mock_ocr, mock_vision):
        """Images with both dimensions < 50 pixels should be rejected."""
        tiny_bytes = _make_png_bytes(30, 30)
        state = _make_pipeline_state(tiny_bytes)

        result = image_processing(state)

        assert len(result.errors) == 1
        assert result.errors[0]["error_type"] == "validation"
        mock_vision.assert_not_called()
        mock_ocr.assert_not_called()

    @patch("culture_compliance.nodes.step3_image_analysis.analyze_image")
    @patch("culture_compliance.nodes.step3_image_analysis.extract_text_from_image")
    def test_accepts_exactly_50x50(self, mock_ocr, mock_vision):
        """Images exactly at 50x50 pixels should be accepted."""
        mock_vision.return_value = "Description"
        mock_ocr.return_value = "Text"

        exact_min_bytes = _make_png_bytes(50, 50)
        state = _make_pipeline_state(exact_min_bytes)

        result = image_processing(state)

        assert len(result.errors) == 0
        mock_vision.assert_called_once()

    @patch("culture_compliance.nodes.step3_image_analysis.analyze_image")
    @patch("culture_compliance.nodes.step3_image_analysis.extract_text_from_image")
    def test_accepts_large_resolution(self, mock_ocr, mock_vision):
        """Images with large resolution should be accepted."""
        mock_vision.return_value = "Description"
        mock_ocr.return_value = "Text"

        large_bytes = _make_png_bytes(1920, 1080)
        state = _make_pipeline_state(large_bytes)

        result = image_processing(state)

        assert len(result.errors) == 0

    @patch("culture_compliance.nodes.step3_image_analysis.analyze_image")
    @patch("culture_compliance.nodes.step3_image_analysis.extract_text_from_image")
    def test_jpeg_resolution_validation(self, mock_ocr, mock_vision):
        """JPEG images with resolution < 50x50 should be rejected."""
        small_jpeg = _make_jpeg_bytes(40, 40)
        state = _make_pipeline_state(small_jpeg)

        result = image_processing(state)

        assert len(result.errors) == 1
        assert result.errors[0]["error_type"] == "validation"


# --- Vision Model Fallback Tests ---


class TestVisionModelFallback:
    """Test that when vision model fails, pipeline falls back to OCR-only.

    Requirements: 3.8
    """

    @patch("culture_compliance.nodes.step3_image_analysis.analyze_image")
    @patch("culture_compliance.nodes.step3_image_analysis.extract_text_from_image")
    def test_vision_failure_falls_back_to_ocr(self, mock_ocr, mock_vision):
        """When vision model returns empty, pipeline should use OCR text only."""
        mock_vision.return_value = ""  # Vision model unavailable
        mock_ocr.return_value = "OCR extracted text from image"

        png_bytes = _make_png_bytes(100, 100)
        state = _make_pipeline_state(png_bytes)

        result = image_processing(state)

        assert len(result.errors) == 0
        assert result.unified_content is not None
        assert "OCR extracted text from image" in result.unified_content
        # Should have a warning about vision failure
        assert len(result.warnings) >= 1
        vision_warning = next(
            (w for w in result.warnings if w.get("step_name") == "vision_analysis"),
            None,
        )
        assert vision_warning is not None
        assert vision_warning["result_may_be_incomplete"] is True

    @patch("culture_compliance.nodes.step3_image_analysis.analyze_image")
    @patch("culture_compliance.nodes.step3_image_analysis.extract_text_from_image")
    def test_vision_exception_falls_back_to_ocr(self, mock_ocr, mock_vision):
        """When vision model raises exception, pipeline should use OCR text only."""
        mock_vision.side_effect = RuntimeError("Model unavailable")
        mock_ocr.return_value = "Fallback OCR text"

        png_bytes = _make_png_bytes(100, 100)
        state = _make_pipeline_state(png_bytes)

        result = image_processing(state)

        assert len(result.errors) == 0
        assert result.unified_content is not None
        assert "Fallback OCR text" in result.unified_content
        # Should have a warning
        assert any(
            w.get("step_name") == "vision_analysis" for w in result.warnings
        )

    @patch("culture_compliance.nodes.step3_image_analysis.analyze_image")
    @patch("culture_compliance.nodes.step3_image_analysis.extract_text_from_image")
    def test_both_services_fail_returns_error(self, mock_ocr, mock_vision):
        """When both vision and OCR fail, pipeline should return an error."""
        mock_vision.return_value = ""
        mock_ocr.return_value = ""

        png_bytes = _make_png_bytes(100, 100)
        state = _make_pipeline_state(png_bytes)

        result = image_processing(state)

        assert len(result.errors) >= 1
        error = result.errors[-1]
        assert error["error_type"] == "service_unavailable"
        assert "Both" in error["message"] or "both" in error["message"]


# --- OCR Fallback Tests ---


class TestOCRFallback:
    """Test that when OCR fails, pipeline falls back to vision-only.

    Requirements: 3.9
    """

    @patch("culture_compliance.nodes.step3_image_analysis.analyze_image")
    @patch("culture_compliance.nodes.step3_image_analysis.extract_text_from_image")
    def test_ocr_failure_falls_back_to_vision(self, mock_ocr, mock_vision):
        """When OCR returns empty, pipeline should use vision description only."""
        mock_vision.return_value = "Visual description of the image content"
        mock_ocr.return_value = ""  # OCR unavailable

        png_bytes = _make_png_bytes(100, 100)
        state = _make_pipeline_state(png_bytes)

        result = image_processing(state)

        assert len(result.errors) == 0
        assert result.unified_content is not None
        assert "Visual description of the image content" in result.unified_content
        # Should have a warning about OCR failure
        assert len(result.warnings) >= 1
        ocr_warning = next(
            (w for w in result.warnings if w.get("step_name") == "ocr_extraction"),
            None,
        )
        assert ocr_warning is not None
        assert ocr_warning["result_may_be_incomplete"] is True

    @patch("culture_compliance.nodes.step3_image_analysis.analyze_image")
    @patch("culture_compliance.nodes.step3_image_analysis.extract_text_from_image")
    def test_ocr_exception_falls_back_to_vision(self, mock_ocr, mock_vision):
        """When OCR raises exception, pipeline should use vision description only."""
        mock_vision.return_value = "Visual content analysis"
        mock_ocr.side_effect = RuntimeError("OCR service error")

        png_bytes = _make_png_bytes(100, 100)
        state = _make_pipeline_state(png_bytes)

        result = image_processing(state)

        assert len(result.errors) == 0
        assert result.unified_content is not None
        assert "Visual content analysis" in result.unified_content
        # Should have a warning
        assert any(
            w.get("step_name") == "ocr_extraction" for w in result.warnings
        )

    @patch("culture_compliance.nodes.step3_image_analysis.analyze_image")
    @patch("culture_compliance.nodes.step3_image_analysis.extract_text_from_image")
    def test_both_succeed_combines_results(self, mock_ocr, mock_vision):
        """When both services succeed, unified content should contain both."""
        mock_vision.return_value = "A billboard with colorful graphics"
        mock_ocr.return_value = "Buy Now! 50% Off"

        png_bytes = _make_png_bytes(200, 200)
        state = _make_pipeline_state(png_bytes)

        result = image_processing(state)

        assert len(result.errors) == 0
        assert result.unified_content is not None
        assert "A billboard with colorful graphics" in result.unified_content
        assert "Buy Now! 50% Off" in result.unified_content
        # No warnings when both succeed
        assert len(result.warnings) == 0
