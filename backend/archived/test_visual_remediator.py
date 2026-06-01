"""Unit tests for visual_remediator frame extraction, speed adjustment, and orchestration.

Tests the extract_frame(), speed_adjust_clip(), build_compliance_prompt(),
and remediate_visual_segment() functions including success cases, error handling,
and edge cases.

Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.9
"""

import os
import tempfile
import subprocess
from unittest.mock import patch, AsyncMock

import pytest

from jusads_video_compliance.visual_remediator import (
    extract_frame,
    speed_adjust_clip,
    _get_video_duration,
    _build_atempo_chain,
    build_compliance_prompt,
    remediate_visual_segment,
)
from jusads_video_compliance.models import Violation, VisualRemediationResult


# Path to the test video in the project assets
TEST_VIDEO_PATH = os.path.join("backend", "assets", "Test Video.mp4")


def ffmpeg_available() -> bool:
    """Check if FFmpeg is available on the system."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _test_video_exists() -> bool:
    """Check if the test video file exists."""
    return os.path.isfile(TEST_VIDEO_PATH)


requires_ffmpeg = pytest.mark.skipif(
    not ffmpeg_available(), reason="FFmpeg not available on this system"
)
requires_test_video = pytest.mark.skipif(
    not _test_video_exists(), reason="Test video not found at expected path"
)


class TestExtractFrame:
    """Tests for extract_frame() function."""

    @requires_ffmpeg
    @requires_test_video
    def test_extract_frame_at_start(self, tmp_path):
        """Extract frame at timestamp 0 should succeed."""
        output = str(tmp_path / "frame_start.png")
        result = extract_frame(TEST_VIDEO_PATH, 0.0, output)
        assert result is True
        assert os.path.isfile(output)
        assert os.path.getsize(output) > 0

    @requires_ffmpeg
    @requires_test_video
    def test_extract_frame_at_midpoint(self, tmp_path):
        """Extract frame at a midpoint timestamp should succeed."""
        output = str(tmp_path / "frame_mid.png")
        result = extract_frame(TEST_VIDEO_PATH, 2.0, output)
        assert result is True
        assert os.path.isfile(output)
        assert os.path.getsize(output) > 0

    @requires_ffmpeg
    @requires_test_video
    def test_extract_frame_creates_output_directory(self, tmp_path):
        """extract_frame should create the output directory if it doesn't exist."""
        output = str(tmp_path / "subdir" / "nested" / "frame.png")
        result = extract_frame(TEST_VIDEO_PATH, 1.0, output)
        assert result is True
        assert os.path.isfile(output)

    def test_extract_frame_negative_timestamp(self, tmp_path):
        """Negative timestamp should return False."""
        output = str(tmp_path / "frame.png")
        result = extract_frame(TEST_VIDEO_PATH, -1.0, output)
        assert result is False
        assert not os.path.isfile(output)

    @requires_ffmpeg
    def test_extract_frame_nonexistent_video(self, tmp_path):
        """Non-existent video path should return False."""
        output = str(tmp_path / "frame.png")
        result = extract_frame("/nonexistent/video.mp4", 0.0, output)
        assert result is False
        assert not os.path.isfile(output)

    @requires_ffmpeg
    @requires_test_video
    def test_extract_frame_beyond_duration(self, tmp_path):
        """Timestamp beyond video duration should return False."""
        output = str(tmp_path / "frame.png")
        # Use a very large timestamp that's certainly beyond the video
        result = extract_frame(TEST_VIDEO_PATH, 99999.0, output)
        assert result is False


class TestSpeedAdjustClip:
    """Tests for speed_adjust_clip() function."""

    @requires_ffmpeg
    @requires_test_video
    def test_speed_up_clip(self, tmp_path):
        """Speed up a clip to a shorter target duration."""
        # First create a short clip from the test video
        input_clip = str(tmp_path / "input_clip.mp4")
        subprocess.run(
            [
                "ffmpeg", "-y", "-ss", "0", "-t", "4",
                "-i", TEST_VIDEO_PATH, "-c", "copy", input_clip,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )

        output = str(tmp_path / "sped_up.mp4")
        result = speed_adjust_clip(input_clip, 2.0, output)
        assert result == output
        assert os.path.isfile(output)

        # Verify the output duration is approximately the target
        output_duration = _get_video_duration(output)
        assert output_duration > 0
        # Allow 0.5s tolerance for FFmpeg encoding
        assert abs(output_duration - 2.0) < 0.5

    @requires_ffmpeg
    @requires_test_video
    def test_speed_adjust_creates_output_directory(self, tmp_path):
        """speed_adjust_clip should create the output directory if needed."""
        input_clip = str(tmp_path / "input_clip.mp4")
        subprocess.run(
            [
                "ffmpeg", "-y", "-ss", "0", "-t", "4",
                "-i", TEST_VIDEO_PATH, "-c", "copy", input_clip,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )

        output = str(tmp_path / "subdir" / "output.mp4")
        result = speed_adjust_clip(input_clip, 2.0, output)
        assert result == output
        assert os.path.isfile(output)

    def test_speed_adjust_zero_target_duration(self, tmp_path):
        """Target duration of 0 should raise ValueError."""
        with pytest.raises(ValueError, match="target_duration must be > 0"):
            speed_adjust_clip("some_clip.mp4", 0.0, str(tmp_path / "out.mp4"))

    def test_speed_adjust_negative_target_duration(self, tmp_path):
        """Negative target duration should raise ValueError."""
        with pytest.raises(ValueError, match="target_duration must be > 0"):
            speed_adjust_clip("some_clip.mp4", -1.0, str(tmp_path / "out.mp4"))

    @requires_ffmpeg
    def test_speed_adjust_nonexistent_clip(self, tmp_path):
        """Non-existent clip path should raise ValueError (can't get duration)."""
        with pytest.raises(ValueError, match="Could not determine duration"):
            speed_adjust_clip(
                "/nonexistent/clip.mp4", 2.0, str(tmp_path / "out.mp4")
            )


class TestGetVideoDuration:
    """Tests for _get_video_duration() helper."""

    @requires_ffmpeg
    @requires_test_video
    def test_valid_video_returns_positive_duration(self):
        """A valid video should return a positive duration."""
        duration = _get_video_duration(TEST_VIDEO_PATH)
        assert duration > 0

    @requires_ffmpeg
    def test_nonexistent_file_returns_zero(self):
        """A non-existent file should return 0.0."""
        duration = _get_video_duration("/nonexistent/video.mp4")
        assert duration == 0.0


class TestBuildAtempoChain:
    """Tests for _build_atempo_chain() helper."""

    def test_normal_speed_factor(self):
        """A normal speed factor (e.g., 2.0) should produce a single atempo."""
        result = _build_atempo_chain(2.0)
        assert "atempo=2.0" in result

    def test_speed_factor_one(self):
        """Speed factor of 1.0 should produce atempo=1.0."""
        result = _build_atempo_chain(1.0)
        assert "atempo=1.0" in result

    def test_large_speed_factor_chains(self):
        """Speed factor > 100 should chain multiple atempo filters."""
        result = _build_atempo_chain(200.0)
        assert "atempo=100.0" in result
        # Should have at least 2 atempo filters
        assert result.count("atempo") >= 2

    def test_small_speed_factor_chains(self):
        """Speed factor < 0.5 should chain multiple atempo filters."""
        result = _build_atempo_chain(0.25)
        assert "atempo=0.5" in result
        assert result.count("atempo") >= 2


class TestBuildCompliancePrompt:
    """Tests for build_compliance_prompt() helper."""

    def test_includes_category(self):
        """Prompt should include the violation category."""
        prompt = build_compliance_prompt("Sexual/Explicit", "Exposed skin")
        assert "Sexual/Explicit" in prompt

    def test_includes_description(self):
        """Prompt should include the violation description."""
        prompt = build_compliance_prompt("Religious", "Inappropriate imagery")
        assert "Inappropriate imagery" in prompt

    def test_returns_nonempty_string(self):
        """Prompt should always be a non-empty string."""
        prompt = build_compliance_prompt("Category", "Description")
        assert isinstance(prompt, str)
        assert len(prompt) > 0


class TestRemediateVisualSegment:
    """Tests for remediate_visual_segment() orchestration function."""

    def _make_violation(
        self,
        start: float = 1.0,
        end: float = 5.0,
        category: str = "Sexual/Explicit",
        description: str = "Exposed skin in frame",
    ) -> Violation:
        """Helper to create a test Violation."""
        return Violation(
            timestamp_start=start,
            timestamp_end=end,
            category=category,
            severity="Moderate",
            description=description,
            violation_type="visual",
            guideline_source="regulatory",
        )

    @pytest.mark.asyncio
    @patch("jusads_video_compliance.visual_remediator.generate_replacement_clip")
    @patch("jusads_video_compliance.visual_remediator.regenerate_frame")
    @patch("jusads_video_compliance.visual_remediator.extract_frame")
    async def test_success_segment_above_4_seconds(
        self, mock_extract, mock_regen, mock_veo, tmp_path
    ):
        """Segment >= 4s should succeed without speed adjustment."""
        violation = self._make_violation(start=1.0, end=6.0)  # 5s segment

        mock_extract.return_value = True
        mock_regen.side_effect = [
            str(tmp_path / "regen_start.png"),
            str(tmp_path / "regen_end.png"),
        ]
        clip_path = str(tmp_path / "generated.mp4")
        # Create a dummy file so the path exists
        open(clip_path, "w").close()
        mock_veo.return_value = clip_path

        result = await remediate_visual_segment(
            video_path="video.mp4",
            violation=violation,
            output_dir=str(tmp_path),
        )

        assert result.success is True
        assert result.replacement_clip_path == clip_path
        assert result.speed_factor == 1.0
        assert result.veo_generation_duration == 5.0
        assert result.original_start == 1.0
        assert result.original_end == 6.0
        assert result.error is None

    @pytest.mark.asyncio
    @patch("jusads_video_compliance.visual_remediator.speed_adjust_clip")
    @patch("jusads_video_compliance.visual_remediator.generate_replacement_clip")
    @patch("jusads_video_compliance.visual_remediator.regenerate_frame")
    @patch("jusads_video_compliance.visual_remediator.extract_frame")
    async def test_success_segment_below_4_seconds_applies_speed_adjust(
        self, mock_extract, mock_regen, mock_veo, mock_speed, tmp_path
    ):
        """Segment < 4s should apply speed adjustment with factor = 4.0 / duration."""
        violation = self._make_violation(start=2.0, end=4.0)  # 2s segment

        mock_extract.return_value = True
        mock_regen.side_effect = [
            str(tmp_path / "regen_start.png"),
            str(tmp_path / "regen_end.png"),
        ]
        mock_veo.return_value = str(tmp_path / "generated.mp4")
        adjusted_path = str(tmp_path / "adjusted.mp4")
        mock_speed.return_value = adjusted_path

        result = await remediate_visual_segment(
            video_path="video.mp4",
            violation=violation,
            output_dir=str(tmp_path),
        )

        assert result.success is True
        assert result.replacement_clip_path == adjusted_path
        assert result.speed_factor == 4.0 / 2.0  # 2.0
        assert result.veo_generation_duration == 4.0
        # Verify speed_adjust_clip was called with correct target duration
        mock_speed.assert_called_once()
        call_args = mock_speed.call_args
        assert call_args[0][1] == 2.0  # target_duration

    @pytest.mark.asyncio
    async def test_invalid_time_range_returns_failed(self, tmp_path):
        """Segment with duration <= 0 should return failed result.

        Note: The Violation model enforces timestamp_end > timestamp_start,
        so we test with a very small but valid segment that we manually
        override to simulate the edge case.
        """
        # We can't create a Violation with end <= start due to model validation,
        # but we can test the function's behavior by patching the violation
        violation = self._make_violation(start=5.0, end=5.5)
        # Manually override to simulate invalid range
        object.__setattr__(violation, "timestamp_end", 5.0)

        result = await remediate_visual_segment(
            video_path="video.mp4",
            violation=violation,
            output_dir=str(tmp_path),
        )

        assert result.success is False
        assert result.error == "Invalid time range"
        # The result uses a safe_end to satisfy model validation
        assert result.original_start == 5.0
        assert result.original_end > result.original_start

    @pytest.mark.asyncio
    @patch("jusads_video_compliance.visual_remediator.extract_frame")
    async def test_start_frame_extraction_failure(self, mock_extract, tmp_path):
        """Failed start frame extraction should return failed result."""
        violation = self._make_violation(start=1.0, end=5.0)
        mock_extract.return_value = False

        result = await remediate_visual_segment(
            video_path="video.mp4",
            violation=violation,
            output_dir=str(tmp_path),
        )

        assert result.success is False
        assert "Frame extraction failed" in result.error
        assert "start timestamp" in result.error

    @pytest.mark.asyncio
    @patch("jusads_video_compliance.visual_remediator.extract_frame")
    async def test_end_frame_extraction_failure(self, mock_extract, tmp_path):
        """Failed end frame extraction should return failed result."""
        violation = self._make_violation(start=1.0, end=5.0)
        # First call (start) succeeds, second call (end) fails
        mock_extract.side_effect = [True, False]

        result = await remediate_visual_segment(
            video_path="video.mp4",
            violation=violation,
            output_dir=str(tmp_path),
        )

        assert result.success is False
        assert "Frame extraction failed" in result.error
        assert "end timestamp" in result.error

    @pytest.mark.asyncio
    @patch("jusads_video_compliance.visual_remediator.regenerate_frame")
    @patch("jusads_video_compliance.visual_remediator.extract_frame")
    async def test_nano_banana_failure_returns_failed(
        self, mock_extract, mock_regen, tmp_path
    ):
        """Nano Banana API failure should return failed result."""
        violation = self._make_violation(start=1.0, end=5.0)
        mock_extract.return_value = True
        mock_regen.side_effect = RuntimeError("Nano Banana API timeout")

        result = await remediate_visual_segment(
            video_path="video.mp4",
            violation=violation,
            output_dir=str(tmp_path),
        )

        assert result.success is False
        assert "Frame regeneration failed" in result.error

    @pytest.mark.asyncio
    @patch("jusads_video_compliance.visual_remediator.generate_replacement_clip")
    @patch("jusads_video_compliance.visual_remediator.regenerate_frame")
    @patch("jusads_video_compliance.visual_remediator.extract_frame")
    async def test_veo_failure_returns_failed(
        self, mock_extract, mock_regen, mock_veo, tmp_path
    ):
        """Google Veo API failure should return failed result."""
        violation = self._make_violation(start=1.0, end=6.0)  # 5s segment
        mock_extract.return_value = True
        mock_regen.side_effect = [
            str(tmp_path / "regen_start.png"),
            str(tmp_path / "regen_end.png"),
        ]
        mock_veo.side_effect = RuntimeError("Veo generation timed out")

        result = await remediate_visual_segment(
            video_path="video.mp4",
            violation=violation,
            output_dir=str(tmp_path),
        )

        assert result.success is False
        assert "Clip generation failed" in result.error
        assert result.veo_generation_duration == 5.0

    @pytest.mark.asyncio
    @patch("jusads_video_compliance.visual_remediator.speed_adjust_clip")
    @patch("jusads_video_compliance.visual_remediator.generate_replacement_clip")
    @patch("jusads_video_compliance.visual_remediator.regenerate_frame")
    @patch("jusads_video_compliance.visual_remediator.extract_frame")
    async def test_speed_adjust_failure_returns_failed(
        self, mock_extract, mock_regen, mock_veo, mock_speed, tmp_path
    ):
        """Speed adjustment failure should return failed result."""
        violation = self._make_violation(start=2.0, end=3.0)  # 1s segment
        mock_extract.return_value = True
        mock_regen.side_effect = [
            str(tmp_path / "regen_start.png"),
            str(tmp_path / "regen_end.png"),
        ]
        mock_veo.return_value = str(tmp_path / "generated.mp4")
        mock_speed.side_effect = RuntimeError("FFmpeg speed adjustment failed")

        result = await remediate_visual_segment(
            video_path="video.mp4",
            violation=violation,
            output_dir=str(tmp_path),
        )

        assert result.success is False
        assert "Speed adjustment failed" in result.error
        assert result.speed_factor == 4.0 / 1.0  # 4.0

    @pytest.mark.asyncio
    @patch("jusads_video_compliance.visual_remediator.generate_replacement_clip")
    @patch("jusads_video_compliance.visual_remediator.regenerate_frame")
    @patch("jusads_video_compliance.visual_remediator.extract_frame")
    async def test_veo_duration_is_max_4_segment(
        self, mock_extract, mock_regen, mock_veo, tmp_path
    ):
        """Veo duration should be max(4.0, segment_duration)."""
        # Test with segment > 4s
        violation = self._make_violation(start=0.0, end=7.0)  # 7s segment
        mock_extract.return_value = True
        mock_regen.side_effect = [
            str(tmp_path / "regen_start.png"),
            str(tmp_path / "regen_end.png"),
        ]
        clip_path = str(tmp_path / "generated.mp4")
        open(clip_path, "w").close()
        mock_veo.return_value = clip_path

        result = await remediate_visual_segment(
            video_path="video.mp4",
            violation=violation,
            output_dir=str(tmp_path),
        )

        assert result.success is True
        assert result.veo_generation_duration == 7.0
        # Verify Veo was called with 7.0 duration
        mock_veo.assert_called_once()
        call_args = mock_veo.call_args
        assert call_args[0][2] == 7.0  # duration_seconds arg
