"""Tests for the Storyboard Generator module.

Tests the frame count determination, prompt building, and retry logic
without making actual API calls.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from jusads_remix_pipeline.storyboard_generator import (
    MAX_RETRIES,
    _build_storyboard_prompt,
    _determine_frame_count,
    generate_storyboard,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FRAME COUNT DETERMINATION (Req 5.1, 11.1)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestDetermineFrameCount:
    """Tests for _determine_frame_count."""

    def test_2_frames_for_duration_up_to_4s(self):
        assert _determine_frame_count(2.0) == 2
        assert _determine_frame_count(3.5) == 2
        assert _determine_frame_count(4.0) == 2

    def test_3_frames_for_duration_up_to_6s(self):
        assert _determine_frame_count(4.1) == 3
        assert _determine_frame_count(5.0) == 3
        assert _determine_frame_count(6.0) == 3

    def test_4_frames_for_duration_up_to_8s(self):
        assert _determine_frame_count(6.1) == 4
        assert _determine_frame_count(7.0) == 4
        assert _determine_frame_count(8.0) == 4

    def test_short_form_duration(self):
        """Very short durations still get at least 2 frames."""
        assert _determine_frame_count(1.0) == 2
        assert _determine_frame_count(0.5) == 2


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PROMPT BUILDING (Req 5.2, 5.3, 5.4)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestBuildStoryboardPrompt:
    """Tests for _build_storyboard_prompt."""

    def test_includes_frame_count_and_duration(self):
        prompt = _build_storyboard_prompt(
            frame_count=3,
            duration=5.5,
            target_audience={"ethnicity": "", "market": "Malaysia"},
            brand_context={},
        )
        assert "3" in prompt
        assert "5.5" in prompt

    def test_includes_malay_cultural_rules(self):
        """Req 5.2: Malay target includes hijab and modesty rules."""
        prompt = _build_storyboard_prompt(
            frame_count=2,
            duration=4.0,
            target_audience={"ethnicity": "Malay", "market": "Malaysia"},
            brand_context={},
        )
        assert "Malay" in prompt
        assert "hijab" in prompt.lower()

    def test_includes_chinese_cultural_rules(self):
        """Req 5.3: Chinese target includes Chinese models only."""
        prompt = _build_storyboard_prompt(
            frame_count=2,
            duration=4.0,
            target_audience={"ethnicity": "Chinese", "market": "Malaysia"},
            brand_context={},
        )
        assert "Chinese" in prompt

    def test_includes_brand_context(self):
        """Req 5.4: Brand elements appear in prompt."""
        prompt = _build_storyboard_prompt(
            frame_count=3,
            duration=6.0,
            target_audience={"ethnicity": "", "market": "Malaysia"},
            brand_context={
                "product_name": "GlowSkin Serum",
                "brand_colors": ["#FF5733", "#C70039"],
                "logo_description": "Golden sun with leaf motif",
                "packaging_description": "White bottle with gold cap",
            },
        )
        assert "GlowSkin Serum" in prompt
        assert "#FF5733" in prompt
        assert "Golden sun with leaf motif" in prompt
        assert "White bottle with gold cap" in prompt

    def test_no_cultural_rules_for_unknown_ethnicity(self):
        """No cultural section if ethnicity is not recognized."""
        prompt = _build_storyboard_prompt(
            frame_count=2,
            duration=4.0,
            target_audience={"ethnicity": "Indian", "market": "Malaysia"},
            brand_context={},
        )
        assert "CULTURAL RULES" not in prompt


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GENERATE STORYBOARD (Req 5.5, 11.4 — retry logic)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestGenerateStoryboard:
    """Tests for generate_storyboard with mocked API calls."""

    @pytest.fixture
    def sample_chunk(self):
        return {
            "start_time": 3.0,
            "end_time": 7.0,
            "source_violation_index": 0,
            "chunk_sequence_number": 0,
            "is_short_form": False,
        }

    @pytest.fixture
    def sample_audience(self):
        return {"ethnicity": "Malay", "market": "Malaysia"}

    @pytest.fixture
    def sample_brand_context(self):
        return {
            "product_name": "GlowSkin",
            "brand_colors": ["#FFFFFF"],
            "logo_description": "Sun logo",
        }

    @patch("jusads_remix_pipeline.storyboard_generator._call_gemini_for_frames")
    def test_successful_generation(
        self, mock_call, sample_chunk, sample_audience, sample_brand_context
    ):
        """Successful generation returns frames with no error."""
        mock_call.return_value = [b"frame1", b"frame2", b"frame3"]

        result = generate_storyboard(sample_chunk, sample_audience, sample_brand_context)

        assert result["chunk_index"] == 0
        assert result["frames"] == [b"frame1", b"frame2", b"frame3"]
        assert result["frame_count"] == 3
        assert result["duration"] == 4.0
        assert result["error"] is None
        mock_call.assert_called_once()

    @patch("jusads_remix_pipeline.storyboard_generator._call_gemini_for_frames")
    def test_retry_on_empty_frames(
        self, mock_call, sample_chunk, sample_audience, sample_brand_context
    ):
        """Retries when API returns empty frames (Req 5.5, 11.4)."""
        # First two calls return empty, third returns frames
        mock_call.side_effect = [[], [], [b"frame1", b"frame2", b"frame3"]]

        result = generate_storyboard(sample_chunk, sample_audience, sample_brand_context)

        assert result["frames"] == [b"frame1", b"frame2", b"frame3"]
        assert result["error"] is None
        assert mock_call.call_count == 3

    @patch("jusads_remix_pipeline.storyboard_generator._call_gemini_for_frames")
    def test_retry_on_exception(
        self, mock_call, sample_chunk, sample_audience, sample_brand_context
    ):
        """Retries on exception, succeeds on second attempt."""
        mock_call.side_effect = [RuntimeError("API error"), [b"frame1", b"frame2", b"frame3"]]

        result = generate_storyboard(sample_chunk, sample_audience, sample_brand_context)

        assert result["frames"] == [b"frame1", b"frame2", b"frame3"]
        assert result["error"] is None
        assert mock_call.call_count == 2

    @patch("jusads_remix_pipeline.storyboard_generator._call_gemini_for_frames")
    def test_all_retries_exhausted_returns_error(
        self, mock_call, sample_chunk, sample_audience, sample_brand_context
    ):
        """After all retries fail, returns error with chunk index (Req 5.5)."""
        mock_call.side_effect = RuntimeError("Persistent failure")

        result = generate_storyboard(sample_chunk, sample_audience, sample_brand_context)

        assert result["chunk_index"] == 0
        assert result["frames"] == []
        assert result["frame_count"] == 0
        assert "failed" in result["error"].lower()
        assert "chunk 0" in result["error"].lower() or "chunk_index" in result["error"].lower()
        assert mock_call.call_count == 1 + MAX_RETRIES  # initial + retries

    @patch("jusads_remix_pipeline.storyboard_generator._call_gemini_for_frames")
    def test_frame_count_based_on_duration(
        self, mock_call, sample_audience, sample_brand_context
    ):
        """Frame count is determined by chunk duration (Req 5.1)."""
        # 3-second chunk → 2 frames expected
        short_chunk = {
            "start_time": 0.0,
            "end_time": 3.0,
            "source_violation_index": 1,
            "chunk_sequence_number": 0,
            "is_short_form": True,
        }
        mock_call.return_value = [b"f1", b"f2"]

        result = generate_storyboard(short_chunk, sample_audience, sample_brand_context)

        assert result["chunk_index"] == 1
        assert result["duration"] == 3.0
        # The prompt should have requested 2 frames
        call_args = mock_call.call_args
        assert call_args[0][1] == 2  # expected_frame_count argument

    @patch("jusads_remix_pipeline.storyboard_generator._call_gemini_for_frames")
    def test_8_second_chunk_gets_4_frames(
        self, mock_call, sample_audience, sample_brand_context
    ):
        """8-second chunk requests 4 frames (Req 5.1)."""
        chunk = {
            "start_time": 0.0,
            "end_time": 8.0,
            "source_violation_index": 2,
            "chunk_sequence_number": 0,
            "is_short_form": False,
        }
        mock_call.return_value = [b"f1", b"f2", b"f3", b"f4"]

        result = generate_storyboard(chunk, sample_audience, sample_brand_context)

        assert result["frame_count"] == 4
        call_args = mock_call.call_args
        assert call_args[0][1] == 4
