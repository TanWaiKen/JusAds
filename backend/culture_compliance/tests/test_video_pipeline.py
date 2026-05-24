"""Unit tests for the video processing pipeline node.

Tests the video_processing function with mocked services to verify:
- Format validation (accept MP4/MOV/WebM, reject others)
- Size validation (reject >100 MB)
- Duration validation (reject >5 minutes)
- Video model fallback to frame-by-frame vision
- No-audio-track handling
- Transcriber failure handling

Requirements: 4.6, 4.7, 4.8, 4.9, 4.10
"""

import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest

from culture_compliance.models.schemas import (
    ContentSubmission,
    ContentType,
    Market,
    PipelineState,
)
from culture_compliance.nodes.step2_video_analysis import (
    video_processing,
    MAX_VIDEO_SIZE_BYTES,
    MAX_DURATION_SECONDS,
    SUPPORTED_EXTENSIONS,
    _detect_video_format_by_extension,
    _detect_video_format_by_magic,
    _merge_chronologically,
)


# --- Helpers ---


def _make_mp4_file(tmp_dir: str, size: int = 100, name: str = "test.mp4") -> str:
    """Create a temporary file with MP4 magic bytes (ftyp box)."""
    path = os.path.join(tmp_dir, name)
    # MP4 ftyp box: 4 bytes size + "ftyp" + brand "isom"
    header = b"\x00\x00\x00\x18" + b"ftyp" + b"isom" + b"\x00" * 8
    padding = max(0, size - len(header))
    with open(path, "wb") as f:
        f.write(header + b"\x00" * padding)
    return path


def _make_mov_file(tmp_dir: str, size: int = 100, name: str = "test.mov") -> str:
    """Create a temporary file with MOV magic bytes (ftyp qt brand)."""
    path = os.path.join(tmp_dir, name)
    # MOV ftyp box: 4 bytes size + "ftyp" + brand "qt  "
    header = b"\x00\x00\x00\x18" + b"ftyp" + b"qt  " + b"\x00" * 8
    padding = max(0, size - len(header))
    with open(path, "wb") as f:
        f.write(header + b"\x00" * padding)
    return path


def _make_webm_file(tmp_dir: str, size: int = 100, name: str = "test.webm") -> str:
    """Create a temporary file with WebM/EBML magic bytes."""
    path = os.path.join(tmp_dir, name)
    # EBML header for WebM
    header = b"\x1a\x45\xdf\xa3" + b"\x00" * 20
    padding = max(0, size - len(header))
    with open(path, "wb") as f:
        f.write(header + b"\x00" * padding)
    return path


def _make_avi_file(tmp_dir: str, size: int = 100, name: str = "test.avi") -> str:
    """Create a temporary file with AVI-like bytes (unsupported format)."""
    path = os.path.join(tmp_dir, name)
    header = b"RIFF" + b"\x00" * 4 + b"AVI " + b"\x00" * 8
    padding = max(0, size - len(header))
    with open(path, "wb") as f:
        f.write(header + b"\x00" * padding)
    return path


def _make_pipeline_state(video_path: str) -> PipelineState:
    """Create a PipelineState with a video file path as content."""
    submission = ContentSubmission(
        content=video_path,
        content_type=ContentType.VIDEO,
        market=Market.MALAYSIA,
    )
    return PipelineState(
        submission=submission,
        content_type=ContentType.VIDEO,
        market=Market.MALAYSIA,
    )


# --- Format Validation Tests ---


class TestFormatValidation:
    """Test that video format validation accepts MP4/MOV/WebM and rejects others.

    Requirements: 4.6
    """

    def test_accepts_mp4_extension(self):
        """MP4 extension should be recognized."""
        assert _detect_video_format_by_extension("video.mp4") == ".mp4"

    def test_accepts_mov_extension(self):
        """MOV extension should be recognized."""
        assert _detect_video_format_by_extension("video.mov") == ".mov"

    def test_accepts_webm_extension(self):
        """WebM extension should be recognized."""
        assert _detect_video_format_by_extension("video.webm") == ".webm"

    def test_rejects_avi_extension(self):
        """AVI extension should be rejected."""
        assert _detect_video_format_by_extension("video.avi") is None

    def test_rejects_mkv_extension(self):
        """MKV extension should be rejected."""
        assert _detect_video_format_by_extension("video.mkv") is None

    def test_rejects_flv_extension(self):
        """FLV extension should be rejected."""
        assert _detect_video_format_by_extension("video.flv") is None

    def test_accepts_uppercase_mp4_extension(self):
        """Uppercase MP4 extension should be recognized (case-insensitive)."""
        assert _detect_video_format_by_extension("video.MP4") == ".mp4"

    def test_magic_bytes_mp4(self):
        """MP4 magic bytes (ftyp isom) should be detected."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _make_mp4_file(tmp_dir)
            assert _detect_video_format_by_magic(path) == ".mp4"

    def test_magic_bytes_mov(self):
        """MOV magic bytes (ftyp qt) should be detected."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _make_mov_file(tmp_dir)
            assert _detect_video_format_by_magic(path) == ".mov"

    def test_magic_bytes_webm(self):
        """WebM EBML magic bytes should be detected."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _make_webm_file(tmp_dir)
            assert _detect_video_format_by_magic(path) == ".webm"

    @patch("culture_compliance.nodes.step2_video_analysis._analyze_video_with_pegasus")
    @patch("culture_compliance.nodes.step2_video_analysis._get_video_duration")
    def test_pipeline_rejects_avi(self, mock_duration, mock_pegasus):
        """Full pipeline should reject AVI with error listing supported formats."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _make_avi_file(tmp_dir)
            state = _make_pipeline_state(path)

            result = video_processing(state)

            assert len(result.errors) == 1
            assert result.errors[0]["error_type"] == "validation"
            assert "Unsupported" in result.errors[0]["message"]
            assert "MP4" in result.errors[0]["message"]
            assert "MOV" in result.errors[0]["message"]
            assert "WebM" in result.errors[0]["message"]
            mock_pegasus.assert_not_called()

    @patch("culture_compliance.nodes.step2_video_analysis._analyze_video_with_pegasus")
    @patch("culture_compliance.nodes.step2_video_analysis._get_video_duration")
    def test_pipeline_accepts_mp4(self, mock_duration, mock_pegasus):
        """Full pipeline should accept MP4 and proceed to processing."""
        mock_duration.return_value = 60.0
        mock_pegasus.return_value = "A scene with people walking in a park"

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _make_mp4_file(tmp_dir)
            state = _make_pipeline_state(path)

            result = video_processing(state)

            assert len(result.errors) == 0
            mock_pegasus.assert_called_once()


# --- Size Validation Tests ---


class TestSizeValidation:
    """Test that videos exceeding 100 MB are rejected.

    Requirements: 4.7
    """

    @patch("culture_compliance.nodes.step2_video_analysis._analyze_video_with_pegasus")
    @patch("culture_compliance.nodes.step2_video_analysis._get_video_duration")
    def test_rejects_video_over_100mb(self, mock_duration, mock_pegasus):
        """Videos larger than 100 MB should be rejected with an error."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create a file that exceeds 100 MB using sparse file technique
            path = os.path.join(tmp_dir, "large.mp4")
            # Write MP4 header
            header = b"\x00\x00\x00\x18" + b"ftyp" + b"isom" + b"\x00" * 8
            with open(path, "wb") as f:
                f.write(header)
                # Seek to just past 100 MB and write a byte to create a sparse file
                f.seek(MAX_VIDEO_SIZE_BYTES + 1)
                f.write(b"\x00")

            state = _make_pipeline_state(path)
            result = video_processing(state)

            assert len(result.errors) == 1
            assert result.errors[0]["error_type"] == "validation"
            assert "100 MB" in result.errors[0]["message"]
            assert result.errors[0]["details"]["max_size_bytes"] == MAX_VIDEO_SIZE_BYTES
            mock_pegasus.assert_not_called()

    @patch("culture_compliance.nodes.step2_video_analysis._analyze_video_with_pegasus")
    @patch("culture_compliance.nodes.step2_video_analysis._get_video_duration")
    def test_accepts_video_under_100mb(self, mock_duration, mock_pegasus):
        """Videos under 100 MB should pass size validation."""
        mock_duration.return_value = 30.0
        mock_pegasus.return_value = "Scene description from Pegasus"

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _make_mp4_file(tmp_dir, size=1024)
            state = _make_pipeline_state(path)

            result = video_processing(state)

            assert len(result.errors) == 0


# --- Duration Validation Tests ---


class TestDurationValidation:
    """Test that videos exceeding 5 minutes are rejected.

    Requirements: 4.6
    """

    @patch("culture_compliance.nodes.step2_video_analysis._analyze_video_with_pegasus")
    @patch("culture_compliance.nodes.step2_video_analysis._get_video_duration")
    def test_rejects_video_over_5_minutes(self, mock_duration, mock_pegasus):
        """Videos longer than 300 seconds should be rejected."""
        mock_duration.return_value = 301.0  # Just over 5 minutes

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _make_mp4_file(tmp_dir)
            state = _make_pipeline_state(path)

            result = video_processing(state)

            assert len(result.errors) == 1
            assert result.errors[0]["error_type"] == "validation"
            assert "5 minutes" in result.errors[0]["message"] or "300 seconds" in result.errors[0]["message"]
            assert result.errors[0]["details"]["max_duration_seconds"] == MAX_DURATION_SECONDS
            mock_pegasus.assert_not_called()

    @patch("culture_compliance.nodes.step2_video_analysis._analyze_video_with_pegasus")
    @patch("culture_compliance.nodes.step2_video_analysis._get_video_duration")
    def test_accepts_video_exactly_5_minutes(self, mock_duration, mock_pegasus):
        """Videos exactly at 300 seconds should be accepted."""
        mock_duration.return_value = 300.0
        mock_pegasus.return_value = "Scene analysis from Pegasus"

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _make_mp4_file(tmp_dir)
            state = _make_pipeline_state(path)

            result = video_processing(state)

            assert len(result.errors) == 0

    @patch("culture_compliance.nodes.step2_video_analysis._analyze_video_with_pegasus")
    @patch("culture_compliance.nodes.step2_video_analysis._get_video_duration")
    def test_accepts_short_video(self, mock_duration, mock_pegasus):
        """Short videos well under 5 minutes should be accepted."""
        mock_duration.return_value = 30.0
        mock_pegasus.return_value = "Short video analysis"

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _make_mp4_file(tmp_dir)
            state = _make_pipeline_state(path)

            result = video_processing(state)

            assert len(result.errors) == 0

    @patch("culture_compliance.nodes.step2_video_analysis._analyze_video_with_pegasus")
    @patch("culture_compliance.nodes.step2_video_analysis._get_video_duration")
    def test_duration_none_skips_validation(self, mock_duration, mock_pegasus):
        """When duration cannot be determined, skip duration validation and proceed."""
        mock_duration.return_value = None
        mock_pegasus.return_value = "Video analysis without duration check"

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _make_mp4_file(tmp_dir)
            state = _make_pipeline_state(path)

            result = video_processing(state)

            # Should not error — duration check is skipped when None
            assert len(result.errors) == 0


# --- Video Model Fallback Tests ---


class TestVideoModelFallback:
    """Test Pegasus video analysis behavior.

    Requirements: 4.8
    """

    @patch("culture_compliance.nodes.step2_video_analysis._analyze_video_with_pegasus")
    @patch("culture_compliance.nodes.step2_video_analysis._get_video_duration")
    def test_uses_pegasus_for_analysis(self, mock_duration, mock_pegasus):
        """Pipeline should analyze video using Pegasus whole-video understanding."""
        mock_duration.return_value = 3.0
        mock_pegasus.return_value = "Comprehensive video analysis: A person walking in a park with a product."

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _make_mp4_file(tmp_dir)
            state = _make_pipeline_state(path)

            result = video_processing(state)

            assert len(result.errors) == 0
            mock_pegasus.assert_called_once()
            assert result.unified_content == "Comprehensive video analysis: A person walking in a park with a product."

    @patch("culture_compliance.nodes.step2_video_analysis._analyze_video_with_pegasus")
    @patch("culture_compliance.nodes.step2_video_analysis._get_video_duration")
    def test_pegasus_failure_returns_error(self, mock_duration, mock_pegasus):
        """When Pegasus fails, pipeline should report a service error."""
        mock_duration.return_value = 3.0
        mock_pegasus.side_effect = Exception("Pegasus API error")

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _make_mp4_file(tmp_dir)
            state = _make_pipeline_state(path)

            result = video_processing(state)

            assert len(result.errors) == 1
            assert result.errors[0]["error_type"] == "service_unavailable"

    @patch("culture_compliance.nodes.step2_video_analysis._analyze_video_with_pegasus")
    @patch("culture_compliance.nodes.step2_video_analysis._get_video_duration")
    def test_pegasus_empty_response_adds_warning(self, mock_duration, mock_pegasus):
        """When Pegasus returns empty analysis, a warning should be added."""
        mock_duration.return_value = 3.0
        mock_pegasus.return_value = ""

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _make_mp4_file(tmp_dir)
            state = _make_pipeline_state(path)

            result = video_processing(state)

            assert len(result.errors) == 0
            assert any(
                w.get("step_name") == "video_analysis" for w in result.warnings
            )


# --- No Audio Track Handling Tests ---


class TestNoAudioTrackHandling:
    """Test handling of videos analyzed by Pegasus (audio is handled internally).

    Requirements: 4.9
    """

    @patch("culture_compliance.nodes.step2_video_analysis._analyze_video_with_pegasus")
    @patch("culture_compliance.nodes.step2_video_analysis._get_video_duration")
    def test_pegasus_handles_video_without_audio(self, mock_duration, mock_pegasus):
        """Pegasus handles videos without audio internally — no separate audio processing needed."""
        mock_duration.return_value = 10.0
        mock_pegasus.return_value = "Visual content: Two frames showing product placement"

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _make_mp4_file(tmp_dir)
            state = _make_pipeline_state(path)

            result = video_processing(state)

            assert len(result.errors) == 0
            assert result.unified_content is not None
            assert "Visual content" in result.unified_content

    @patch("culture_compliance.nodes.step2_video_analysis._analyze_video_with_pegasus")
    @patch("culture_compliance.nodes.step2_video_analysis._get_video_duration")
    def test_pegasus_result_set_as_unified_content(self, mock_duration, mock_pegasus):
        """Pegasus analysis result should be set as unified_content."""
        mock_duration.return_value = 5.0
        mock_pegasus.return_value = "Complete video analysis with audio and visual elements"

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _make_mp4_file(tmp_dir)
            state = _make_pipeline_state(path)

            result = video_processing(state)

            assert result.unified_content == "Complete video analysis with audio and visual elements"


# --- Transcriber Failure Handling Tests ---


class TestTranscriberFailureHandling:
    """Test handling of Pegasus API failures.

    Requirements: 4.10
    """

    @patch("culture_compliance.nodes.step2_video_analysis._analyze_video_with_pegasus")
    @patch("culture_compliance.nodes.step2_video_analysis._get_video_duration")
    def test_pegasus_client_error_returns_service_error(self, mock_duration, mock_pegasus):
        """When Pegasus raises a ClientError, pipeline should report service unavailable."""
        from botocore.exceptions import ClientError
        mock_duration.return_value = 10.0
        mock_pegasus.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "InvokeModel"
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _make_mp4_file(tmp_dir)
            state = _make_pipeline_state(path)

            result = video_processing(state)

            assert len(result.errors) == 1
            assert result.errors[0]["error_type"] == "service_unavailable"
            assert "ThrottlingException" in result.errors[0]["message"]

    @patch("culture_compliance.nodes.step2_video_analysis._analyze_video_with_pegasus")
    @patch("culture_compliance.nodes.step2_video_analysis._get_video_duration")
    def test_pegasus_generic_exception_returns_error(self, mock_duration, mock_pegasus):
        """Any unexpected exception from Pegasus should return a service error."""
        mock_duration.return_value = 5.0
        mock_pegasus.side_effect = Exception("Unexpected Pegasus failure")

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _make_mp4_file(tmp_dir)
            state = _make_pipeline_state(path)

            result = video_processing(state)

            assert len(result.errors) == 1
            assert result.errors[0]["error_type"] == "service_unavailable"
            assert "Unexpected Pegasus failure" in result.errors[0]["message"]


# --- Chronological Merge Tests ---


class TestChronologicalMerge:
    """Test the chronological merge of frame descriptions and transcript segments."""

    def test_merge_frames_only(self):
        """Merge with only frame descriptions should produce visual entries."""
        frames = [
            {"timestamp": 0.0, "description": "Opening scene"},
            {"timestamp": 2.0, "description": "Product shot"},
        ]
        result = _merge_chronologically(frames, [])

        assert "[00:00] [Visual] Opening scene" in result
        assert "[00:02] [Visual] Product shot" in result

    def test_merge_transcript_only(self):
        """Merge with only transcript segments should produce audio entries."""
        segments = [
            {"start_time": 1.0, "end_time": 3.0, "text": "Welcome to our ad"},
            {"start_time": 4.0, "end_time": 6.0, "text": "Buy now"},
        ]
        result = _merge_chronologically([], segments)

        assert "[00:01] [Audio] Welcome to our ad" in result
        assert "[00:04] [Audio] Buy now" in result

    def test_merge_interleaved_chronologically(self):
        """Merge should interleave frames and transcript by timestamp."""
        frames = [
            {"timestamp": 0.0, "description": "Logo appears"},
            {"timestamp": 3.0, "description": "Product close-up"},
        ]
        segments = [
            {"start_time": 1.5, "end_time": 2.5, "text": "Introducing our product"},
            {"start_time": 4.0, "end_time": 5.0, "text": "Available now"},
        ]
        result = _merge_chronologically(frames, segments)

        lines = result.strip().split("\n")
        assert len(lines) == 4
        # Check chronological order
        assert "[00:00] [Visual] Logo appears" in lines[0]
        assert "[00:01] [Audio] Introducing our product" in lines[1]
        assert "[00:03] [Visual] Product close-up" in lines[2]
        assert "[00:04] [Audio] Available now" in lines[3]

    def test_merge_empty_inputs(self):
        """Merge with no inputs should return empty string."""
        result = _merge_chronologically([], [])
        assert result == ""
