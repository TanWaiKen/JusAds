"""Unit tests for the content routing node.

Tests validate that the content router correctly:
- Routes valid content types (text, image, video)
- Rejects unsupported content types with descriptive errors
- Performs case-sensitive matching (lowercase only)
- Handles the routing decision without modifying other state fields
"""

import pytest

from culture_compliance.models.schemas import (
    ContentSubmission,
    ContentType,
    Market,
    PipelineState,
)
from culture_compliance.nodes.step1_routing import content_routing, SUPPORTED_CONTENT_TYPES


def _make_state(content_type: ContentType, content: str = "test content") -> PipelineState:
    """Helper to create a PipelineState with a given content_type."""
    submission = ContentSubmission(
        content=content,
        content_type=content_type,
        market=Market.MALAYSIA,
    )
    return PipelineState(
        submission=submission,
        content_type=content_type,
        market=Market.MALAYSIA,
    )


class TestValidContentTypes:
    """Tests for valid content type routing."""

    def test_routes_text_content(self):
        state = _make_state(ContentType.TEXT)
        result = content_routing(state)
        assert result.content_type == ContentType.TEXT
        assert result.errors == []

    def test_routes_image_content(self):
        state = _make_state(ContentType.IMAGE)
        result = content_routing(state)
        assert result.content_type == ContentType.IMAGE
        assert result.errors == []

    def test_routes_video_content(self):
        state = _make_state(ContentType.VIDEO)
        result = content_routing(state)
        assert result.content_type == ContentType.VIDEO
        assert result.errors == []

    def test_does_not_modify_submission(self):
        state = _make_state(ContentType.TEXT, content="hello world")
        result = content_routing(state)
        assert result.submission.content == "hello world"
        assert result.submission.content_type == ContentType.TEXT
        assert result.submission.market == Market.MALAYSIA

    def test_preserves_existing_state_fields(self):
        state = _make_state(ContentType.IMAGE)
        state.extracted_text = "some text"
        state.models_used = ["model-1"]
        result = content_routing(state)
        assert result.extracted_text == "some text"
        assert result.models_used == ["model-1"]


class TestInvalidContentTypes:
    """Tests for invalid content type rejection."""

    def test_rejects_uppercase_text(self):
        """Case-sensitive: 'Text' should be rejected at submission level."""
        # ContentType enum only accepts lowercase values, so Pydantic will
        # reject uppercase at the ContentSubmission level. This test verifies
        # that the enum validation works.
        with pytest.raises(ValueError):
            ContentSubmission(
                content="test",
                content_type="Text",  # type: ignore
                market=Market.MALAYSIA,
            )

    def test_rejects_all_caps(self):
        """Case-sensitive: 'IMAGE' should be rejected."""
        with pytest.raises(ValueError):
            ContentSubmission(
                content="test",
                content_type="IMAGE",  # type: ignore
                market=Market.MALAYSIA,
            )

    def test_rejects_mixed_case(self):
        """Case-sensitive: 'Video' should be rejected."""
        with pytest.raises(ValueError):
            ContentSubmission(
                content="test",
                content_type="Video",  # type: ignore
                market=Market.MALAYSIA,
            )

    def test_rejects_unsupported_type(self):
        """Arbitrary strings should be rejected."""
        with pytest.raises(ValueError):
            ContentSubmission(
                content="test",
                content_type="audio",  # type: ignore
                market=Market.MALAYSIA,
            )

    def test_rejects_empty_string(self):
        """Empty string should be rejected."""
        with pytest.raises(ValueError):
            ContentSubmission(
                content="test",
                content_type="",  # type: ignore
                market=Market.MALAYSIA,
            )


class TestSupportedContentTypesConstant:
    """Tests for the SUPPORTED_CONTENT_TYPES constant."""

    def test_contains_text(self):
        assert "text" in SUPPORTED_CONTENT_TYPES

    def test_contains_image(self):
        assert "image" in SUPPORTED_CONTENT_TYPES

    def test_contains_video(self):
        assert "video" in SUPPORTED_CONTENT_TYPES

    def test_exactly_three_types(self):
        assert len(SUPPORTED_CONTENT_TYPES) == 3


class TestErrorMessages:
    """Tests for error message content when validation fails at Pydantic level."""

    def test_unsupported_type_error_mentions_supported_values(self):
        """Error message should list supported types."""
        with pytest.raises(ValueError) as exc_info:
            ContentSubmission(
                content="test",
                content_type="pdf",  # type: ignore
                market=Market.MALAYSIA,
            )
        error_str = str(exc_info.value)
        # Pydantic enum validation will mention the valid values
        assert "text" in error_str or "image" in error_str or "video" in error_str
