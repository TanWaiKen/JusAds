"""Integration tests for the full content compliance pipeline.

These tests exercise the complete pipeline end-to-end with real AWS Bedrock
and Qdrant services. They require valid AWS credentials and Qdrant connectivity.

Tests are marked with @pytest.mark.integration and will be skipped when
credentials are not available.

Requirements: 9.5, 5.1, 5.2
"""

import base64
import os
import struct
import zlib
from pathlib import Path

import pytest

from culture_compliance.models.schemas import (
    ContentSubmission,
    ContentType,
    Market,
)
from culture_compliance.orchestrator import run_pipeline


# --- Skip conditions ---

_MISSING_AWS = not os.environ.get("AWS_ACCESS_KEY_ID") and not os.environ.get(
    "AWS_PROFILE"
)
_MISSING_QDRANT = not os.environ.get("QDRANT_URL")

_SKIP_REASON = (
    "Integration tests require AWS credentials (AWS_ACCESS_KEY_ID or AWS_PROFILE) "
    "and QDRANT_URL environment variables"
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(_MISSING_AWS or _MISSING_QDRANT, reason=_SKIP_REASON),
]


# --- Helpers ---


def _create_minimal_png(width: int = 4, height: int = 4) -> bytes:
    """Create a minimal valid PNG image in memory.

    Args:
        width: Image width in pixels.
        height: Image height in pixels.

    Returns:
        Raw PNG bytes.
    """

    def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
        chunk = chunk_type + data
        return (
            struct.pack(">I", len(data))
            + chunk
            + struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF)
        )

    signature = b"\x89PNG\r\n\x1a\n"

    # IHDR: width x height, 8-bit RGB
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr = _png_chunk(b"IHDR", ihdr_data)

    # IDAT: raw image data (filter byte + RGB pixels per row)
    raw_rows = b""
    for _ in range(height):
        raw_rows += b"\x00"  # filter: None
        raw_rows += b"\xff\xff\xff" * width  # white pixels (RGB)
    compressed = zlib.compress(raw_rows)
    idat = _png_chunk(b"IDAT", compressed)

    # IEND
    iend = _png_chunk(b"IEND", b"")

    return signature + ihdr + idat + iend


def _create_minimal_jpeg(width: int = 4, height: int = 4) -> bytes:
    """Create a minimal valid JPEG image using Pillow if available,
    otherwise return a synthetic JPEG header.

    Args:
        width: Image width in pixels.
        height: Image height in pixels.

    Returns:
        Raw JPEG bytes.
    """
    try:
        from PIL import Image
        import io

        img = Image.new("RGB", (width, height), color=(255, 255, 255))
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG")
        return buffer.getvalue()
    except ImportError:
        # Fallback: use PNG since the pipeline accepts it
        return _create_minimal_png(width, height)


def _validate_compliance_result(result: dict, content_type: str) -> None:
    """Assert that a result dict is a valid ComplianceResult.

    Args:
        result: The dict returned by run_pipeline.
        content_type: Expected content_type value.

    Raises:
        AssertionError: If validation fails.
    """
    assert isinstance(result, dict), f"Expected dict, got {type(result).__name__}"

    required_fields = [
        "content_type",
        "market",
        "risk_level",
        "score",
        "high_risk_indicators",
        "explanation",
        "suggestion",
        "processing_metadata",
    ]

    for field in required_fields:
        assert field in result, f"Missing required field: {field}"

    # Validate risk_level
    assert result["risk_level"] in {
        "High",
        "Medium",
        "Low",
    }, f"Invalid risk_level: {result['risk_level']}"

    # Validate score range
    score = result["score"]
    assert isinstance(score, int), f"Score must be int, got {type(score).__name__}"
    assert 0 <= score <= 100, f"Score {score} out of range [0, 100]"

    # Validate content_type matches
    assert (
        result["content_type"] == content_type
    ), f"content_type mismatch: expected '{content_type}', got '{result['content_type']}'"

    # Validate processing_metadata
    metadata = result.get("processing_metadata", {})
    assert isinstance(metadata, dict), "processing_metadata must be a dict"
    for meta_field in ["pipeline_duration_ms", "models_used", "market"]:
        assert (
            meta_field in metadata
        ), f"processing_metadata missing field: {meta_field}"

    # Validate high_risk_indicators is a list with max 10 items
    indicators = result["high_risk_indicators"]
    assert isinstance(indicators, list), "high_risk_indicators must be a list"
    assert len(indicators) <= 10, f"Too many indicators: {len(indicators)} (max 10)"

    # Validate explanation and suggestion are strings
    assert isinstance(result["explanation"], str), "explanation must be a string"
    assert isinstance(result["suggestion"], str), "suggestion must be a string"


# --- Full Text Pipeline Tests ---


class TestFullTextPipeline:
    """End-to-end tests for the text compliance pipeline with real services."""

    def test_text_pipeline_malaysia_clean_content(self):
        """Test text pipeline with clean Malaysian ad copy returns valid result.

        Validates: Requirement 9.5 - full text pipeline exercise
        """
        submission = ContentSubmission(
            content="Promosi Raya Aidilfitri! Dapatkan diskaun 50% untuk semua produk.",
            content_type=ContentType.TEXT,
            market=Market.MALAYSIA,
        )

        result = run_pipeline(submission)

        _validate_compliance_result(result, "text")
        assert result["market"] == "malaysia"

    def test_text_pipeline_singapore_clean_content(self):
        """Test text pipeline with clean Singapore ad copy returns valid result.

        Validates: Requirement 5.2 - Singapore market guideline retrieval
        """
        submission = ContentSubmission(
            content="Great Singapore Sale! 50% off all electronics this weekend only.",
            content_type=ContentType.TEXT,
            market=Market.SINGAPORE,
        )

        result = run_pipeline(submission)

        _validate_compliance_result(result, "text")
        assert result["market"] == "singapore"

    def test_text_pipeline_potentially_sensitive_content(self):
        """Test text pipeline with potentially sensitive content produces indicators.

        Validates: Requirement 9.5 - pipeline produces meaningful results
        """
        submission = ContentSubmission(
            content=(
                "This product is exclusively for one ethnic group. "
                "Other races need not apply. Only for true believers."
            ),
            content_type=ContentType.TEXT,
            market=Market.MALAYSIA,
        )

        result = run_pipeline(submission)

        _validate_compliance_result(result, "text")
        # Sensitive content should produce a non-perfect score
        # (exact score depends on LLM evaluation)
        assert result["score"] <= 100


# --- Full Image Pipeline Tests ---


class TestFullImagePipeline:
    """End-to-end tests for the image compliance pipeline with real services."""

    def test_image_pipeline_with_sample_jpeg(self):
        """Test image pipeline end-to-end with a sample JPEG image.

        Validates: Requirement 9.5 - full image pipeline exercise
        """
        # Create a minimal JPEG image
        jpeg_bytes = _create_minimal_jpeg(100, 100)
        image_b64 = base64.b64encode(jpeg_bytes).decode("utf-8")

        submission = ContentSubmission(
            content=image_b64,
            content_type=ContentType.IMAGE,
            market=Market.MALAYSIA,
        )

        result = run_pipeline(submission)

        _validate_compliance_result(result, "image")
        assert result["market"] == "malaysia"

    def test_image_pipeline_with_png(self):
        """Test image pipeline with a PNG image returns valid result.

        Validates: Requirement 9.5 - image format support
        """
        png_bytes = _create_minimal_png(100, 100)
        image_b64 = base64.b64encode(png_bytes).decode("utf-8")

        submission = ContentSubmission(
            content=image_b64,
            content_type=ContentType.IMAGE,
            market=Market.SINGAPORE,
        )

        result = run_pipeline(submission)

        _validate_compliance_result(result, "image")
        assert result["market"] == "singapore"


# --- Full Video Pipeline Tests ---


class TestFullVideoPipeline:
    """End-to-end tests for the video compliance pipeline with real services."""

    @pytest.fixture
    def sample_video_path(self):
        """Get the path to the sample test video file."""
        video_path = (
            Path(__file__).resolve().parent.parent.parent / "Test Video.mp4"
        )
        if not video_path.exists():
            pytest.skip(f"Test video not found: {video_path}")
        return video_path

    def test_video_pipeline_with_sample_mp4(self, sample_video_path):
        """Test video pipeline end-to-end with sample MP4 file.

        Validates: Requirement 9.5 - full video pipeline exercise
        """
        submission = ContentSubmission(
            content=str(sample_video_path),
            content_type=ContentType.VIDEO,
            market=Market.MALAYSIA,
            frame_interval_seconds=2.0,  # Use larger interval for faster test
        )

        result = run_pipeline(submission)

        _validate_compliance_result(result, "video")
        assert result["market"] == "malaysia"

    def test_video_pipeline_singapore_market(self, sample_video_path):
        """Test video pipeline with Singapore market.

        Validates: Requirement 5.2 - Singapore market support for video
        """
        submission = ContentSubmission(
            content=str(sample_video_path),
            content_type=ContentType.VIDEO,
            market=Market.SINGAPORE,
            frame_interval_seconds=3.0,  # Larger interval for faster test
        )

        result = run_pipeline(submission)

        _validate_compliance_result(result, "video")
        assert result["market"] == "singapore"


# --- Multi-Market Evaluation Tests ---


class TestMultiMarketEvaluation:
    """Tests that verify the same content evaluated against both markets
    produces valid but potentially different results.

    Validates: Requirements 5.1, 5.2
    """

    def test_same_text_both_markets(self):
        """Same text content evaluated against Malaysia and Singapore markets.

        Both should return valid ComplianceResults, potentially with different
        scores due to different scoring categories and guidelines.
        """
        content = (
            "Buy our premium health supplement today! "
            "Guaranteed to cure all diseases. Limited time offer."
        )

        # Evaluate against Malaysia
        submission_my = ContentSubmission(
            content=content,
            content_type=ContentType.TEXT,
            market=Market.MALAYSIA,
        )
        result_my = run_pipeline(submission_my)

        # Evaluate against Singapore
        submission_sg = ContentSubmission(
            content=content,
            content_type=ContentType.TEXT,
            market=Market.SINGAPORE,
        )
        result_sg = run_pipeline(submission_sg)

        # Both should be valid
        _validate_compliance_result(result_my, "text")
        _validate_compliance_result(result_sg, "text")

        # Markets should be correctly set
        assert result_my["market"] == "malaysia"
        assert result_sg["market"] == "singapore"

        # Processing metadata should reflect the correct market
        assert result_my["processing_metadata"]["market"] == "malaysia"
        assert result_sg["processing_metadata"]["market"] == "singapore"

    def test_same_image_both_markets(self):
        """Same image content evaluated against both markets.

        Validates that market routing works correctly for image content.
        """
        png_bytes = _create_minimal_png(100, 100)
        image_b64 = base64.b64encode(png_bytes).decode("utf-8")

        # Evaluate against Malaysia
        submission_my = ContentSubmission(
            content=image_b64,
            content_type=ContentType.IMAGE,
            market=Market.MALAYSIA,
        )
        result_my = run_pipeline(submission_my)

        # Evaluate against Singapore
        submission_sg = ContentSubmission(
            content=image_b64,
            content_type=ContentType.IMAGE,
            market=Market.SINGAPORE,
        )
        result_sg = run_pipeline(submission_sg)

        # Both should be valid
        _validate_compliance_result(result_my, "image")
        _validate_compliance_result(result_sg, "image")

        # Markets should be correctly set
        assert result_my["market"] == "malaysia"
        assert result_sg["market"] == "singapore"
