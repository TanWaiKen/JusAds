"""Tests for the Video Interpolator module.

Tests the frame validation, audio extraction, retry logic, and video
generation without making actual API calls.

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch, mock_open

import pytest

from jusads_remix_pipeline.video_interpolator import (
    MAX_RETRIES,
    MIN_CLIP_DURATION,
    MAX_CLIP_DURATION,
    MIN_FPS,
    TIMEOUT_SECONDS,
    interpolate_video,
    _extract_ambient_audio,
    _get_video_metadata,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FRAME VALIDATION (Req 6.6)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestFrameValidation:
    """Tests for minimum frame count validation."""

    def test_reject_zero_frames(self):
        """Req 6.6: Reject if fewer than 2 frames provided."""
        result = interpolate_video([], "/fake/segment.mp4")
        assert result["error"] is not None
        assert "2" in result["error"]
        assert result["video_path"] == ""

    def test_reject_single_frame(self):
        """Req 6.6: Reject single frame."""
        result = interpolate_video([b"single_frame"], "/fake/segment.mp4")
        assert result["error"] is not None
        assert "2" in result["error"]
        assert result["video_path"] == ""
        assert result["duration"] == 0.0
        assert result["fps"] == 0

    @patch("jusads_remix_pipeline.video_interpolator._extract_ambient_audio")
    @patch("jusads_remix_pipeline.video_interpolator._generate_video_with_retries")
    def test_accept_two_frames(self, mock_gen, mock_audio):
        """Req 6.6: Accept exactly 2 frames."""
        mock_audio.return_value = "/clips/audio.aac"
        mock_gen.return_value = ("/clips/video.mp4", 6.0, 24, None)

        result = interpolate_video([b"frame1", b"frame2"], "/fake/segment.mp4")
        assert result["error"] is None
        assert result["video_path"] == "/clips/video.mp4"

    @patch("jusads_remix_pipeline.video_interpolator._extract_ambient_audio")
    @patch("jusads_remix_pipeline.video_interpolator._generate_video_with_retries")
    def test_accept_multiple_frames(self, mock_gen, mock_audio):
        """Accept more than 2 frames."""
        mock_audio.return_value = "/clips/audio.aac"
        mock_gen.return_value = ("/clips/video.mp4", 7.5, 24, None)

        frames = [b"frame1", b"frame2", b"frame3", b"frame4"]
        result = interpolate_video(frames, "/fake/segment.mp4")
        assert result["error"] is None
        assert result["video_path"] == "/clips/video.mp4"
        assert result["duration"] == 7.5
        assert result["fps"] == 24


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AUDIO EXTRACTION (Req 6.3)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestAudioExtraction:
    """Tests for ambient audio extraction via FFmpeg."""

    @patch("jusads_remix_pipeline.video_interpolator.os.path.getsize")
    @patch("jusads_remix_pipeline.video_interpolator.os.path.exists")
    @patch("jusads_remix_pipeline.video_interpolator.subprocess.run")
    def test_successful_extraction(self, mock_run, mock_exists, mock_size):
        """Req 6.3: Extract ambient audio from source segment."""
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        mock_exists.return_value = True
        mock_size.return_value = 1024

        result = _extract_ambient_audio("/source/segment.mp4", "abc123")
        assert result.endswith("_ambient_audio.aac")
        assert "abc123" in result

    @patch("jusads_remix_pipeline.video_interpolator.subprocess.run")
    def test_extraction_ffmpeg_failure(self, mock_run):
        """Returns empty string when FFmpeg fails."""
        mock_run.return_value = MagicMock(returncode=1, stderr="error")

        result = _extract_ambient_audio("/source/segment.mp4", "abc123")
        assert result == ""

    @patch("jusads_remix_pipeline.video_interpolator.subprocess.run")
    def test_extraction_ffmpeg_not_found(self, mock_run):
        """Returns empty string when FFmpeg is not installed."""
        mock_run.side_effect = FileNotFoundError("ffmpeg not found")

        result = _extract_ambient_audio("/source/segment.mp4", "abc123")
        assert result == ""

    @patch("jusads_remix_pipeline.video_interpolator.subprocess.run")
    def test_extraction_timeout(self, mock_run):
        """Returns empty string on FFmpeg timeout."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("ffmpeg", 30)

        result = _extract_ambient_audio("/source/segment.mp4", "abc123")
        assert result == ""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RETRY AND ERROR HANDLING (Req 6.5)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestRetryLogic:
    """Tests for retry behavior on generation failure."""

    @patch("jusads_remix_pipeline.video_interpolator._extract_ambient_audio")
    @patch("jusads_remix_pipeline.video_interpolator._generate_video_with_retries")
    def test_generation_failure_returns_error(self, mock_gen, mock_audio):
        """Req 6.5: Returns error when all retries fail."""
        mock_audio.return_value = "/clips/audio.aac"
        mock_gen.return_value = ("", 0.0, 0, "Veo API timed out after 120s")

        result = interpolate_video(
            [b"frame1", b"frame2"], "/source/segment.mp4"
        )
        assert result["error"] is not None
        assert result["video_path"] == ""
        assert result["ambient_audio_path"] == "/clips/audio.aac"

    @patch("jusads_remix_pipeline.video_interpolator._extract_ambient_audio")
    @patch("jusads_remix_pipeline.video_interpolator._generate_video_with_retries")
    def test_successful_generation_returns_paths(self, mock_gen, mock_audio):
        """Successful generation returns video path, audio path, and metadata."""
        mock_audio.return_value = "/clips/test_ambient_audio.aac"
        mock_gen.return_value = ("/clips/test_interpolated.mp4", 7.0, 24, None)

        result = interpolate_video(
            [b"frame1", b"frame2", b"frame3"], "/source/segment.mp4"
        )
        assert result["error"] is None
        assert result["video_path"] == "/clips/test_interpolated.mp4"
        assert result["ambient_audio_path"] == "/clips/test_ambient_audio.aac"
        assert result["duration"] == 7.0
        assert result["fps"] == 24


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# VIDEO METADATA (Req 6.2)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestVideoMetadata:
    """Tests for video metadata extraction."""

    @patch("jusads_remix_pipeline.video_interpolator.subprocess.run")
    def test_parse_duration_and_fps(self, mock_run):
        """Correctly parses duration and fps from ffprobe output."""
        # First call is for duration, second for fps
        duration_result = MagicMock(returncode=0, stdout="6.5\n")
        fps_result = MagicMock(returncode=0, stdout="24/1\n")
        mock_run.side_effect = [duration_result, fps_result]

        duration, fps = _get_video_metadata("/clips/test.mp4")
        assert duration == 6.5
        assert fps == 24

    @patch("jusads_remix_pipeline.video_interpolator.subprocess.run")
    def test_parse_fractional_fps(self, mock_run):
        """Handles fractional fps like 30000/1001."""
        duration_result = MagicMock(returncode=0, stdout="8.0\n")
        fps_result = MagicMock(returncode=0, stdout="30000/1001\n")
        mock_run.side_effect = [duration_result, fps_result]

        duration, fps = _get_video_metadata("/clips/test.mp4")
        assert duration == 8.0
        assert fps == 30  # 30000/1001 ≈ 29.97, rounds to 30

    @patch("jusads_remix_pipeline.video_interpolator.subprocess.run")
    def test_fallback_on_ffprobe_failure(self, mock_run):
        """Returns default values when ffprobe fails."""
        mock_run.side_effect = Exception("ffprobe not found")

        duration, fps = _get_video_metadata("/clips/test.mp4")
        assert duration == float(MAX_CLIP_DURATION)
        assert fps == MIN_FPS


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIGURATION CONSTANTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestConstants:
    """Tests that configuration constants match requirements."""

    def test_timeout_is_120_seconds(self):
        """Req 6.5: Timeout is 120 seconds."""
        assert TIMEOUT_SECONDS == 120

    def test_max_retries_is_2(self):
        """Req 6.5: Up to 2 retries."""
        assert MAX_RETRIES == 2

    def test_min_clip_duration(self):
        """Req 6.2: Minimum 5 seconds."""
        assert MIN_CLIP_DURATION == 5

    def test_max_clip_duration(self):
        """Req 6.2: Maximum 8 seconds."""
        assert MAX_CLIP_DURATION == 8

    def test_min_fps(self):
        """Req 6.2: Minimum 24fps."""
        assert MIN_FPS == 24
