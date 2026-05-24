"""Unit tests for the text processing node.

Tests validate that the text processing node correctly:
- Sets unified_content for valid non-empty text
- Rejects empty text with a validation error
- Rejects whitespace-only text with a validation error
- Preserves existing state fields
"""

import pytest

from culture_compliance.models.schemas import (
    ContentSubmission,
    ContentType,
    Market,
    PipelineState,
)
from culture_compliance.nodes.step4_text_analysis import text_processing


def _make_state(content: str = "test content") -> PipelineState:
    """Helper to create a PipelineState for text processing."""
    submission = ContentSubmission(
        content=content,
        content_type=ContentType.TEXT,
        market=Market.MALAYSIA,
    )
    return PipelineState(
        submission=submission,
        content_type=ContentType.TEXT,
        market=Market.MALAYSIA,
    )


class TestValidTextProcessing:
    """Tests for valid text content processing."""

    def test_sets_unified_content_for_valid_text(self):
        state = _make_state("Hello world, this is ad copy.")
        result = text_processing(state)
        assert result.unified_content == "Hello world, this is ad copy."
        assert result.errors == []

    def test_sets_unified_content_for_single_character(self):
        state = _make_state("a")
        result = text_processing(state)
        assert result.unified_content == "a"
        assert result.errors == []

    def test_preserves_text_with_leading_trailing_whitespace(self):
        state = _make_state("  some text with spaces  ")
        result = text_processing(state)
        assert result.unified_content == "  some text with spaces  "
        assert result.errors == []

    def test_handles_multiline_text(self):
        content = "Line 1\nLine 2\nLine 3"
        state = _make_state(content)
        result = text_processing(state)
        assert result.unified_content == content
        assert result.errors == []

    def test_handles_unicode_text(self):
        content = "Selamat datang ke Malaysia 🇲🇾"
        state = _make_state(content)
        result = text_processing(state)
        assert result.unified_content == content
        assert result.errors == []

    def test_does_not_modify_submission(self):
        state = _make_state("hello world")
        result = text_processing(state)
        assert result.submission.content == "hello world"
        assert result.submission.content_type == ContentType.TEXT
        assert result.submission.market == Market.MALAYSIA

    def test_preserves_existing_state_fields(self):
        state = _make_state("valid text")
        state.models_used = ["model-1"]
        state.market = Market.SINGAPORE
        result = text_processing(state)
        assert result.models_used == ["model-1"]
        assert result.market == Market.SINGAPORE


class TestInvalidTextProcessing:
    """Tests for invalid text content rejection."""

    def test_rejects_whitespace_only_spaces(self):
        """Whitespace-only text (spaces) should produce a validation error."""
        # ContentSubmission validator rejects empty/whitespace at model level,
        # but we test the node's own validation for defense-in-depth
        # We need to bypass Pydantic validation to test the node directly
        submission = ContentSubmission.__new__(ContentSubmission)
        object.__setattr__(submission, 'content', '   ')
        object.__setattr__(submission, 'content_type', ContentType.TEXT)
        object.__setattr__(submission, 'market', Market.MALAYSIA)
        object.__setattr__(submission, 'frame_interval_seconds', 1.0)

        state = PipelineState.__new__(PipelineState)
        object.__setattr__(state, 'submission', submission)
        object.__setattr__(state, 'content_type', ContentType.TEXT)
        object.__setattr__(state, 'market', Market.MALAYSIA)
        object.__setattr__(state, 'extracted_text', None)
        object.__setattr__(state, 'visual_description', None)
        object.__setattr__(state, 'unified_content', None)
        object.__setattr__(state, 'frame_descriptions', None)
        object.__setattr__(state, 'transcript_segments', None)
        object.__setattr__(state, 'retrieved_guidelines', None)
        object.__setattr__(state, 'guideline_collection', None)
        object.__setattr__(state, 'raw_llm_output', None)
        object.__setattr__(state, 'compliance_result', None)
        object.__setattr__(state, 'errors', [])
        object.__setattr__(state, 'warnings', [])
        object.__setattr__(state, 'pipeline_start_ms', None)
        object.__setattr__(state, 'models_used', [])

        result = text_processing(state)
        assert len(result.errors) == 1
        assert result.errors[0]["error_type"] == "validation"
        assert "empty" in result.errors[0]["message"].lower() or "whitespace" in result.errors[0]["message"].lower()
        assert result.unified_content is None

    def test_rejects_whitespace_only_tabs(self):
        """Whitespace-only text (tabs) should produce a validation error."""
        submission = ContentSubmission.__new__(ContentSubmission)
        object.__setattr__(submission, 'content', '\t\t\t')
        object.__setattr__(submission, 'content_type', ContentType.TEXT)
        object.__setattr__(submission, 'market', Market.MALAYSIA)
        object.__setattr__(submission, 'frame_interval_seconds', 1.0)

        state = PipelineState.__new__(PipelineState)
        object.__setattr__(state, 'submission', submission)
        object.__setattr__(state, 'content_type', ContentType.TEXT)
        object.__setattr__(state, 'market', Market.MALAYSIA)
        object.__setattr__(state, 'extracted_text', None)
        object.__setattr__(state, 'visual_description', None)
        object.__setattr__(state, 'unified_content', None)
        object.__setattr__(state, 'frame_descriptions', None)
        object.__setattr__(state, 'transcript_segments', None)
        object.__setattr__(state, 'retrieved_guidelines', None)
        object.__setattr__(state, 'guideline_collection', None)
        object.__setattr__(state, 'raw_llm_output', None)
        object.__setattr__(state, 'compliance_result', None)
        object.__setattr__(state, 'errors', [])
        object.__setattr__(state, 'warnings', [])
        object.__setattr__(state, 'pipeline_start_ms', None)
        object.__setattr__(state, 'models_used', [])

        result = text_processing(state)
        assert len(result.errors) == 1
        assert result.errors[0]["error_type"] == "validation"
        assert result.unified_content is None

    def test_rejects_whitespace_only_newlines(self):
        """Whitespace-only text (newlines) should produce a validation error."""
        submission = ContentSubmission.__new__(ContentSubmission)
        object.__setattr__(submission, 'content', '\n\n\n')
        object.__setattr__(submission, 'content_type', ContentType.TEXT)
        object.__setattr__(submission, 'market', Market.MALAYSIA)
        object.__setattr__(submission, 'frame_interval_seconds', 1.0)

        state = PipelineState.__new__(PipelineState)
        object.__setattr__(state, 'submission', submission)
        object.__setattr__(state, 'content_type', ContentType.TEXT)
        object.__setattr__(state, 'market', Market.MALAYSIA)
        object.__setattr__(state, 'extracted_text', None)
        object.__setattr__(state, 'visual_description', None)
        object.__setattr__(state, 'unified_content', None)
        object.__setattr__(state, 'frame_descriptions', None)
        object.__setattr__(state, 'transcript_segments', None)
        object.__setattr__(state, 'retrieved_guidelines', None)
        object.__setattr__(state, 'guideline_collection', None)
        object.__setattr__(state, 'raw_llm_output', None)
        object.__setattr__(state, 'compliance_result', None)
        object.__setattr__(state, 'errors', [])
        object.__setattr__(state, 'warnings', [])
        object.__setattr__(state, 'pipeline_start_ms', None)
        object.__setattr__(state, 'models_used', [])

        result = text_processing(state)
        assert len(result.errors) == 1
        assert result.errors[0]["error_type"] == "validation"
        assert result.unified_content is None

    def test_error_details_include_field_name(self):
        """Error details should identify the 'content' field."""
        submission = ContentSubmission.__new__(ContentSubmission)
        object.__setattr__(submission, 'content', '   ')
        object.__setattr__(submission, 'content_type', ContentType.TEXT)
        object.__setattr__(submission, 'market', Market.MALAYSIA)
        object.__setattr__(submission, 'frame_interval_seconds', 1.0)

        state = PipelineState.__new__(PipelineState)
        object.__setattr__(state, 'submission', submission)
        object.__setattr__(state, 'content_type', ContentType.TEXT)
        object.__setattr__(state, 'market', Market.MALAYSIA)
        object.__setattr__(state, 'extracted_text', None)
        object.__setattr__(state, 'visual_description', None)
        object.__setattr__(state, 'unified_content', None)
        object.__setattr__(state, 'frame_descriptions', None)
        object.__setattr__(state, 'transcript_segments', None)
        object.__setattr__(state, 'retrieved_guidelines', None)
        object.__setattr__(state, 'guideline_collection', None)
        object.__setattr__(state, 'raw_llm_output', None)
        object.__setattr__(state, 'compliance_result', None)
        object.__setattr__(state, 'errors', [])
        object.__setattr__(state, 'warnings', [])
        object.__setattr__(state, 'pipeline_start_ms', None)
        object.__setattr__(state, 'models_used', [])

        result = text_processing(state)
        assert result.errors[0]["details"]["field"] == "content"
