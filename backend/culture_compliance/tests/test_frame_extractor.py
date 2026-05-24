"""Unit tests for the frame extractor service.

Tests the extract_frames function with mocked subprocess calls to verify:
- Successful frame extraction returns correct number of frames with timestamps
- Interval validation rejects values outside [0.5, 5.0]
- ffmpeg not found raises FrameExtractionError
- Invalid video file raises FrameExtractionError
- Frame count calculation matches ceil(duration / interval)

Requirements: 4.1
"""

from unittest.mock import MagicMock, patch, call
import subprocess

import pytest

from culture_compliance.services.frame_extractor import (
    extract_frames,
    _get_video_duration,
    _extract_single_frame,
    FrameExtractionError,
    MIN_INTERVAL,
    MAX_INTERVAL,
)


# --- Fake JPEG frame bytes ---
FAKE_JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 100


class TestIntervalValidation:
    """Tests for interval parameter validation."""

    def test_rejects_interval_below_minimum(self):
        """Interval below 0.5 should raise ValueError."""
        with pytest.raises(ValueError, match="between 0.5 and 5.0"):
            extract_frames("video.mp4", interval=0.1)

    def test_rejects_interval_above_maximum(self):
        """Interval above 5.0 should raise ValueError."""
        with pytest.raises(ValueError, match="between 0.5 and 5.0"):
            extract_frames("video.mp4", interval=6.0)

    def test_rejects_zero_interval(self):
        """Zero interval should raise ValueError."""
        with pytest.raises(ValueError, match="between 0.5 and 5.0"):
            extract_frames("video.mp4", interval=0.0)

    def test_rejects_negative_interval(self):
        """Negative interval should raise ValueError."""
        with pytest.raises(ValueError, match="between 0.5 and 5.0"):
            extract_frames("video.mp4", interval=-1.0)

    @patch("culture_compliance.services.frame_extractor._get_video_duration")
    @patch("culture_compliance.services.frame_extractor._extract_single_frame")
    def test_accepts_minimum_interval(self, mock_extract, mock_duration):
        """Interval of exactly 0.5 should be accepted."""
        mock_duration.return_value = 2.0
        mock_extract.return_value = FAKE_JPEG_BYTES

        result = extract_frames("video.mp4", interval=0.5)
        assert len(result) > 0

    @patch("culture_compliance.services.frame_extractor._get_video_duration")
    @patch("culture_compliance.services.frame_extractor._extract_single_frame")
    def test_accepts_maximum_interval(self, mock_extract, mock_duration):
        """Interval of exactly 5.0 should be accepted."""
        mock_duration.return_value = 10.0
        mock_extract.return_value = FAKE_JPEG_BYTES

        result = extract_frames("video.mp4", interval=5.0)
        assert len(result) > 0


class TestGetVideoDuration:
    """Tests for the _get_video_duration helper."""

    @patch("culture_compliance.services.frame_extractor.subprocess.run")
    def test_returns_duration_on_success(self, mock_run):
        """Successful ffprobe call should return parsed duration."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="10.500000\n",
            stderr="",
        )

        duration = _get_video_duration("video.mp4")
        assert duration == 10.5

    @patch("culture_compliance.services.frame_extractor.subprocess.run")
    def test_raises_on_nonzero_return_code(self, mock_run):
        """Non-zero return code should raise FrameExtractionError."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="No such file or directory",
        )

        with pytest.raises(FrameExtractionError, match="ffprobe failed"):
            _get_video_duration("nonexistent.mp4")

    @patch("culture_compliance.services.frame_extractor.subprocess.run")
    def test_raises_on_empty_output(self, mock_run):
        """Empty ffprobe output should raise FrameExtractionError."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",
            stderr="",
        )

        with pytest.raises(FrameExtractionError, match="empty duration"):
            _get_video_duration("video.mp4")

    @patch("culture_compliance.services.frame_extractor.subprocess.run")
    def test_raises_on_ffmpeg_not_found(self, mock_run):
        """FileNotFoundError should raise FrameExtractionError about ffmpeg."""
        mock_run.side_effect = FileNotFoundError("ffprobe not found")

        with pytest.raises(FrameExtractionError, match="not found"):
            _get_video_duration("video.mp4")

    @patch("culture_compliance.services.frame_extractor.subprocess.run")
    def test_raises_on_timeout(self, mock_run):
        """Timeout should raise FrameExtractionError."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ffprobe", timeout=30)

        with pytest.raises(FrameExtractionError, match="timed out"):
            _get_video_duration("video.mp4")

    @patch("culture_compliance.services.frame_extractor.subprocess.run")
    def test_raises_on_invalid_duration_value(self, mock_run):
        """Non-numeric duration output should raise FrameExtractionError."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="N/A\n",
            stderr="",
        )

        with pytest.raises(FrameExtractionError, match="Could not parse duration"):
            _get_video_duration("video.mp4")

    @patch("culture_compliance.services.frame_extractor.subprocess.run")
    def test_raises_on_zero_duration(self, mock_run):
        """Zero duration should raise FrameExtractionError."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="0.0\n",
            stderr="",
        )

        with pytest.raises(FrameExtractionError, match="Invalid video duration"):
            _get_video_duration("video.mp4")


class TestExtractFrames:
    """Tests for the extract_frames function."""

    @patch("culture_compliance.services.frame_extractor._get_video_duration")
    @patch("culture_compliance.services.frame_extractor._extract_single_frame")
    def test_correct_frame_count_exact_division(self, mock_extract, mock_duration):
        """10s video at 1s interval should produce exactly 10 frames."""
        mock_duration.return_value = 10.0
        mock_extract.return_value = FAKE_JPEG_BYTES

        result = extract_frames("video.mp4", interval=1.0)

        assert len(result) == 10

    @patch("culture_compliance.services.frame_extractor._get_video_duration")
    @patch("culture_compliance.services.frame_extractor._extract_single_frame")
    def test_correct_frame_count_ceil_division(self, mock_extract, mock_duration):
        """7s video at 2s interval should produce ceil(7/2) = 4 frames."""
        mock_duration.return_value = 7.0
        mock_extract.return_value = FAKE_JPEG_BYTES

        result = extract_frames("video.mp4", interval=2.0)

        # ceil(7/2) = 4, timestamps: 0, 2, 4, 6 (all < 7)
        assert len(result) == 4

    @patch("culture_compliance.services.frame_extractor._get_video_duration")
    @patch("culture_compliance.services.frame_extractor._extract_single_frame")
    def test_timestamps_are_multiples_of_interval(self, mock_extract, mock_duration):
        """Each frame timestamp should be a multiple of the interval starting from 0."""
        mock_duration.return_value = 5.0
        mock_extract.return_value = FAKE_JPEG_BYTES

        result = extract_frames("video.mp4", interval=1.5)

        # ceil(5/1.5) = 4, timestamps: 0, 1.5, 3.0, 4.5
        timestamps = [f["timestamp"] for f in result]
        assert timestamps == [0.0, 1.5, 3.0, 4.5]

    @patch("culture_compliance.services.frame_extractor._get_video_duration")
    @patch("culture_compliance.services.frame_extractor._extract_single_frame")
    def test_frame_bytes_present_in_result(self, mock_extract, mock_duration):
        """Each frame dict should contain 'frame_bytes' with actual bytes."""
        mock_duration.return_value = 2.0
        mock_extract.return_value = FAKE_JPEG_BYTES

        result = extract_frames("video.mp4", interval=1.0)

        for frame in result:
            assert "frame_bytes" in frame
            assert isinstance(frame["frame_bytes"], bytes)
            assert frame["frame_bytes"] == FAKE_JPEG_BYTES

    @patch("culture_compliance.services.frame_extractor._get_video_duration")
    @patch("culture_compliance.services.frame_extractor._extract_single_frame")
    def test_default_interval_is_one_second(self, mock_extract, mock_duration):
        """Default interval should be 1.0 second."""
        mock_duration.return_value = 3.0
        mock_extract.return_value = FAKE_JPEG_BYTES

        result = extract_frames("video.mp4")

        # 3s video at 1s interval = 3 frames at 0, 1, 2
        assert len(result) == 3
        timestamps = [f["timestamp"] for f in result]
        assert timestamps == [0.0, 1.0, 2.0]

    @patch("culture_compliance.services.frame_extractor._get_video_duration")
    @patch("culture_compliance.services.frame_extractor._extract_single_frame")
    def test_skips_failed_frames_continues_extraction(self, mock_extract, mock_duration):
        """If one frame fails, extraction should continue with remaining frames."""
        mock_duration.return_value = 3.0

        # Second frame fails, others succeed
        mock_extract.side_effect = [
            FAKE_JPEG_BYTES,
            FrameExtractionError("Frame failed"),
            FAKE_JPEG_BYTES,
        ]

        result = extract_frames("video.mp4", interval=1.0)

        # Should have 2 frames (skipped the failed one)
        assert len(result) == 2
        assert result[0]["timestamp"] == 0.0
        assert result[1]["timestamp"] == 2.0

    @patch("culture_compliance.services.frame_extractor._get_video_duration")
    @patch("culture_compliance.services.frame_extractor._extract_single_frame")
    def test_raises_when_all_frames_fail(self, mock_extract, mock_duration):
        """If all frames fail, should raise FrameExtractionError."""
        mock_duration.return_value = 2.0
        mock_extract.side_effect = FrameExtractionError("All frames failed")

        with pytest.raises(FrameExtractionError, match="No frames could be extracted"):
            extract_frames("video.mp4", interval=1.0)

    @patch("culture_compliance.services.frame_extractor._get_video_duration")
    def test_raises_on_ffmpeg_not_found(self, mock_duration):
        """FileNotFoundError from ffmpeg should raise FrameExtractionError."""
        mock_duration.return_value = 5.0

        with patch(
            "culture_compliance.services.frame_extractor.subprocess.run"
        ) as mock_run:
            mock_run.side_effect = FileNotFoundError("ffmpeg not found")

            with pytest.raises(FrameExtractionError, match="No frames could be extracted"):
                extract_frames("video.mp4", interval=1.0)

    @patch("culture_compliance.services.frame_extractor._get_video_duration")
    @patch("culture_compliance.services.frame_extractor._extract_single_frame")
    def test_short_video_single_frame(self, mock_extract, mock_duration):
        """Video shorter than interval should still produce 1 frame at timestamp 0."""
        mock_duration.return_value = 0.3
        mock_extract.return_value = FAKE_JPEG_BYTES

        result = extract_frames("video.mp4", interval=0.5)

        # ceil(0.3/0.5) = 1, timestamp 0.0 < 0.3 so it's extracted
        assert len(result) == 1
        assert result[0]["timestamp"] == 0.0


class TestExtractSingleFrame:
    """Tests for the _extract_single_frame helper."""

    @patch("culture_compliance.services.frame_extractor.subprocess.run")
    def test_returns_frame_bytes_on_success(self, mock_run):
        """Successful ffmpeg call should return stdout bytes."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=FAKE_JPEG_BYTES,
            stderr=b"",
        )

        result = _extract_single_frame("video.mp4", 1.0)
        assert result == FAKE_JPEG_BYTES

    @patch("culture_compliance.services.frame_extractor.subprocess.run")
    def test_raises_on_nonzero_return_code(self, mock_run):
        """Non-zero return code should raise FrameExtractionError."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout=b"",
            stderr=b"Error processing video",
        )

        with pytest.raises(FrameExtractionError, match="ffmpeg failed"):
            _extract_single_frame("video.mp4", 1.0)

    @patch("culture_compliance.services.frame_extractor.subprocess.run")
    def test_raises_on_empty_output(self, mock_run):
        """Empty stdout should raise FrameExtractionError."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=b"",
            stderr=b"",
        )

        with pytest.raises(FrameExtractionError, match="empty output"):
            _extract_single_frame("video.mp4", 1.0)

    @patch("culture_compliance.services.frame_extractor.subprocess.run")
    def test_raises_on_timeout(self, mock_run):
        """Timeout should raise FrameExtractionError."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ffmpeg", timeout=30)

        with pytest.raises(FrameExtractionError, match="timed out"):
            _extract_single_frame("video.mp4", 1.0)
