"""
test_remix_finalize.py
──────────────────────
Unit tests for the remix_finalize node quality threshold enforcement.

Tests validate:
- Image media type with quality_score < 70 → status = "remix_failed"
- Image media type with quality_score ≥ 70 → status remains "remediated"
- Non-image media types always pass through (no quality threshold check)
- Edge case: quality_score exactly 70 (boundary condition)

Requirements: 1.5, 1.7
"""

import sys
from unittest.mock import MagicMock, patch

# Mock heavy dependencies before importing pipeline
sys.modules.setdefault("langgraph", MagicMock())
sys.modules.setdefault("langgraph.graph", MagicMock())
sys.modules.setdefault("langgraph.types", MagicMock())
sys.modules.setdefault("google", MagicMock())
sys.modules.setdefault("google.genai", MagicMock())
sys.modules.setdefault("google.genai.types", MagicMock())
sys.modules.setdefault("tavily", MagicMock())

# Mock agent submodules that have external deps
sys.modules.setdefault("agent.clients", MagicMock())
sys.modules.setdefault("agent.compliance_tools", MagicMock())
sys.modules.setdefault("agent.remix_tools", MagicMock())
sys.modules.setdefault("agent.prompts", MagicMock())

from agent.data_model import ComplianceState
from agent.pipeline import node_remix_finalize


def _make_state(media_type: str, status: str, quality_score: int = 100) -> ComplianceState:
    """Helper to create a ComplianceState for remix_finalize tests."""
    state = ComplianceState(
        session_id="test_remix_finalize",
        media_type=media_type,
        input_path="/tmp/test.png",
        text_input="",
        market="malaysia",
        platform="tiktok",
        ethnicity="malay",
        age_group="gen_z",
        status=status,
        result={
            "remix": {
                "tool_used": "image_editor",
                "output_path": "/tmp/edited.png",
                "changes_made": ["Edited"],
                "duration_seconds": 1.0,
                "quality_score": quality_score,
            }
        },
    )
    return state


class TestRemixFinalizeQualityThreshold:
    """Tests for image quality threshold enforcement in remix_finalize."""

    def test_image_quality_below_threshold_fails(self):
        """Image with quality_score < 70 should set status to 'remix_failed'."""
        state = _make_state("image", "remediated", quality_score=50)
        result = node_remix_finalize(state)
        assert result.status == "remix_failed"

    def test_image_quality_at_threshold_passes(self):
        """Image with quality_score == 70 should keep status as 'remediated'."""
        state = _make_state("image", "remediated", quality_score=70)
        result = node_remix_finalize(state)
        assert result.status == "remediated"

    def test_image_quality_above_threshold_passes(self):
        """Image with quality_score > 70 should keep status as 'remediated'."""
        state = _make_state("image", "remediated", quality_score=95)
        result = node_remix_finalize(state)
        assert result.status == "remediated"

    def test_image_quality_zero_fails(self):
        """Image with quality_score == 0 should set status to 'remix_failed'."""
        state = _make_state("image", "remediated", quality_score=0)
        result = node_remix_finalize(state)
        assert result.status == "remix_failed"

    def test_image_quality_69_fails(self):
        """Image with quality_score == 69 (just below threshold) should fail."""
        state = _make_state("image", "remediated", quality_score=69)
        result = node_remix_finalize(state)
        assert result.status == "remix_failed"

    def test_image_quality_issues_message_on_failure(self):
        """When quality fails, result.remix should contain quality_issues message."""
        state = _make_state("image", "remediated", quality_score=40)
        result = node_remix_finalize(state)
        assert "quality_issues" in result.result["remix"]
        assert "40" in result.result["remix"]["quality_issues"]
        assert "70" in result.result["remix"]["quality_issues"]


class TestRemixFinalizeNonImagePassthrough:
    """Non-image media types should always pass through without quality checks."""

    def test_text_always_passes(self):
        """Text media type should keep status as 'remediated' regardless of quality_score."""
        state = _make_state("text", "remediated", quality_score=10)
        state.media_type = "text"
        result = node_remix_finalize(state)
        assert result.status == "remediated"

    def test_audio_always_passes(self):
        """Audio media type should keep status as 'remediated' regardless of quality_score."""
        state = _make_state("audio", "remediated", quality_score=10)
        state.media_type = "audio"
        result = node_remix_finalize(state)
        assert result.status == "remediated"

    def test_video_always_passes(self):
        """Video media type should keep status as 'remediated' regardless of quality_score."""
        state = _make_state("video", "remediated", quality_score=10)
        state.media_type = "video"
        result = node_remix_finalize(state)
        assert result.status == "remediated"


class TestRemixFinalizeNonRemediatedState:
    """If status is not 'remediated', remix_finalize should skip quality check."""

    def test_already_failed_status_unchanged(self):
        """If status is already 'remix_failed', it should not change."""
        state = _make_state("image", "remix_failed", quality_score=50)
        result = node_remix_finalize(state)
        assert result.status == "remix_failed"

    def test_pending_status_unchanged(self):
        """If status is 'pending', remix_finalize should not modify it."""
        state = _make_state("image", "pending", quality_score=50)
        result = node_remix_finalize(state)
        assert result.status == "pending"
