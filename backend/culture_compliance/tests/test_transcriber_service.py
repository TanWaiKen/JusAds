"""Unit tests for the audio transcriber service.

Tests the transcribe_audio function with mocked AWS services to verify:
- Successful transcription returns segment-level timestamps
- Videos with no audio track return empty list
- Transcription failures are handled gracefully (return empty list)
- Temporary files are cleaned up

Requirements: 4.2, 4.9, 4.10
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch, call

import pytest
from botocore.exceptions import ClientError

from culture_compliance.services.transcriber import (
    transcribe_audio,
    _extract_audio,
    _items_to_segments,
    _parse_transcript_results,
)


# --- Sample transcript data ---

SAMPLE_TRANSCRIPT_DATA = {
    "results": {
        "items": [
            {
                "type": "pronunciation",
                "start_time": "0.5",
                "end_time": "0.8",
                "alternatives": [{"content": "Hello"}],
            },
            {
                "type": "pronunciation",
                "start_time": "0.9",
                "end_time": "1.2",
                "alternatives": [{"content": "world"}],
            },
            {
                "type": "punctuation",
                "alternatives": [{"content": "."}],
            },
            {
                "type": "pronunciation",
                "start_time": "2.0",
                "end_time": "2.3",
                "alternatives": [{"content": "This"}],
            },
            {
                "type": "pronunciation",
                "start_time": "2.4",
                "end_time": "2.7",
                "alternatives": [{"content": "is"}],
            },
            {
                "type": "pronunciation",
                "start_time": "2.8",
                "end_time": "3.1",
                "alternatives": [{"content": "a"}],
            },
            {
                "type": "pronunciation",
                "start_time": "3.2",
                "end_time": "3.5",
                "alternatives": [{"content": "test"}],
            },
            {
                "type": "punctuation",
                "alternatives": [{"content": "."}],
            },
        ]
    }
}


class TestItemsToSegments:
    """Tests for the _items_to_segments helper function."""

    def test_parses_segments_with_punctuation(self):
        """Items separated by punctuation should produce distinct segments."""
        segments = _items_to_segments(SAMPLE_TRANSCRIPT_DATA)

        assert len(segments) == 2
        assert segments[0] == {
            "start_time": 0.5,
            "end_time": 1.2,
            "text": "Hello world.",
        }
        assert segments[1] == {
            "start_time": 2.0,
            "end_time": 3.5,
            "text": "This is a test.",
        }

    def test_empty_items_returns_empty_list(self):
        """Empty items list should return empty segments."""
        data = {"results": {"items": []}}
        segments = _items_to_segments(data)
        assert segments == []

    def test_missing_results_returns_empty_list(self):
        """Missing results key should return empty segments."""
        data = {}
        segments = _items_to_segments(data)
        assert segments == []

    def test_words_without_trailing_punctuation(self):
        """Words without trailing punctuation should still form a segment."""
        data = {
            "results": {
                "items": [
                    {
                        "type": "pronunciation",
                        "start_time": "1.0",
                        "end_time": "1.5",
                        "alternatives": [{"content": "No"}],
                    },
                    {
                        "type": "pronunciation",
                        "start_time": "1.6",
                        "end_time": "2.0",
                        "alternatives": [{"content": "punctuation"}],
                    },
                ]
            }
        }
        segments = _items_to_segments(data)
        assert len(segments) == 1
        assert segments[0] == {
            "start_time": 1.0,
            "end_time": 2.0,
            "text": "No punctuation",
        }

    def test_handles_question_mark_punctuation(self):
        """Question marks should be handled as segment boundaries."""
        data = {
            "results": {
                "items": [
                    {
                        "type": "pronunciation",
                        "start_time": "0.0",
                        "end_time": "0.5",
                        "alternatives": [{"content": "Why"}],
                    },
                    {
                        "type": "punctuation",
                        "alternatives": [{"content": "?"}],
                    },
                ]
            }
        }
        segments = _items_to_segments(data)
        assert len(segments) == 1
        assert segments[0]["text"] == "Why?"


class TestExtractAudio:
    """Tests for the _extract_audio helper function."""

    @patch("culture_compliance.services.transcriber.subprocess.run")
    def test_no_audio_track_returns_false(self, mock_run):
        """Video with no audio stream should return False."""
        # ffprobe returns empty stdout when no audio stream
        mock_run.return_value = MagicMock(
            stdout="",
            stderr="",
            returncode=0,
        )

        result = _extract_audio("/path/to/video.mp4", "/tmp/audio.wav")
        assert result is False

    @patch("culture_compliance.services.transcriber.subprocess.run")
    @patch("culture_compliance.services.transcriber.os.path.exists")
    @patch("culture_compliance.services.transcriber.os.path.getsize")
    def test_successful_extraction_returns_true(
        self, mock_getsize, mock_exists, mock_run
    ):
        """Successful audio extraction should return True."""
        # ffprobe finds audio stream
        probe_result = MagicMock(stdout="audio\n", stderr="", returncode=0)
        # ffmpeg extraction succeeds
        extract_result = MagicMock(stdout="", stderr="", returncode=0)
        mock_run.side_effect = [probe_result, extract_result]

        mock_exists.return_value = True
        mock_getsize.return_value = 1024

        result = _extract_audio("/path/to/video.mp4", "/tmp/audio.wav")
        assert result is True

    @patch("culture_compliance.services.transcriber.subprocess.run")
    def test_ffmpeg_failure_returns_false(self, mock_run):
        """ffmpeg extraction failure should return False."""
        # ffprobe finds audio stream
        probe_result = MagicMock(stdout="audio\n", stderr="", returncode=0)
        # ffmpeg fails
        extract_result = MagicMock(
            stdout="", stderr="Error processing", returncode=1
        )
        mock_run.side_effect = [probe_result, extract_result]

        result = _extract_audio("/path/to/video.mp4", "/tmp/audio.wav")
        assert result is False

    @patch("culture_compliance.services.transcriber.subprocess.run")
    def test_ffmpeg_not_found_returns_false(self, mock_run):
        """Missing ffmpeg binary should return False."""
        mock_run.side_effect = FileNotFoundError("ffprobe not found")

        result = _extract_audio("/path/to/video.mp4", "/tmp/audio.wav")
        assert result is False

    @patch("culture_compliance.services.transcriber.subprocess.run")
    def test_timeout_returns_false(self, mock_run):
        """Subprocess timeout should return False."""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ffprobe", timeout=30)

        result = _extract_audio("/path/to/video.mp4", "/tmp/audio.wav")
        assert result is False


class TestTranscribeAudio:
    """Tests for the main transcribe_audio function."""

    def test_empty_path_returns_empty_list(self):
        """Empty video path should return empty list."""
        result = transcribe_audio("")
        assert result == []

    def test_nonexistent_file_returns_empty_list(self):
        """Non-existent video file should return empty list."""
        result = transcribe_audio("/nonexistent/path/video.mp4")
        assert result == []

    @patch("culture_compliance.services.transcriber._cleanup_transcription_job")
    @patch("culture_compliance.services.transcriber._cleanup_s3")
    @patch("culture_compliance.services.transcriber._extract_audio")
    def test_no_audio_track_returns_empty_list(
        self, mock_extract, mock_cleanup_s3, mock_cleanup_job
    ):
        """Video with no audio track should return empty list (Req 4.9)."""
        mock_extract.return_value = False

        # Create a temporary file to simulate a video file
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake video content")
            video_path = f.name

        try:
            result = transcribe_audio(video_path)
            assert result == []
            mock_extract.assert_called_once()
        finally:
            os.unlink(video_path)

    @patch("culture_compliance.services.transcriber._cleanup_transcription_job")
    @patch("culture_compliance.services.transcriber._cleanup_s3")
    @patch("culture_compliance.services.transcriber._wait_for_job")
    @patch("culture_compliance.services.transcriber._start_transcription_job")
    @patch("culture_compliance.services.transcriber._upload_to_s3")
    @patch("culture_compliance.services.transcriber._extract_audio")
    def test_successful_transcription_returns_segments(
        self,
        mock_extract,
        mock_upload,
        mock_start,
        mock_wait,
        mock_cleanup_s3,
        mock_cleanup_job,
    ):
        """Successful transcription should return segment list (Req 4.2)."""
        mock_extract.return_value = True
        mock_upload.return_value = "s3://bucket/key.wav"
        mock_start.return_value = "job-123"
        mock_wait.return_value = {
            "Transcript": {
                "TranscriptFileUri": "https://example.com/transcript.json"
            }
        }

        # Mock the transcript parsing
        expected_segments = [
            {"start_time": 0.5, "end_time": 1.2, "text": "Hello world."},
        ]

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake video content")
            video_path = f.name

        try:
            with patch(
                "culture_compliance.services.transcriber._parse_transcript_results"
            ) as mock_parse:
                mock_parse.return_value = expected_segments
                result = transcribe_audio(video_path)

            assert result == expected_segments
        finally:
            if os.path.exists(video_path):
                os.unlink(video_path)

    @patch("culture_compliance.services.transcriber._cleanup_transcription_job")
    @patch("culture_compliance.services.transcriber._cleanup_s3")
    @patch("culture_compliance.services.transcriber._wait_for_job")
    @patch("culture_compliance.services.transcriber._start_transcription_job")
    @patch("culture_compliance.services.transcriber._upload_to_s3")
    @patch("culture_compliance.services.transcriber._extract_audio")
    def test_failed_job_returns_empty_list(
        self,
        mock_extract,
        mock_upload,
        mock_start,
        mock_wait,
        mock_cleanup_s3,
        mock_cleanup_job,
    ):
        """Failed transcription job should return empty list (Req 4.10)."""
        mock_extract.return_value = True
        mock_upload.return_value = "s3://bucket/key.wav"
        mock_start.return_value = "job-123"
        mock_wait.return_value = None  # Job failed

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake video content")
            video_path = f.name

        try:
            result = transcribe_audio(video_path)
            assert result == []
        finally:
            if os.path.exists(video_path):
                os.unlink(video_path)

    @patch("culture_compliance.services.transcriber._cleanup_transcription_job")
    @patch("culture_compliance.services.transcriber._cleanup_s3")
    @patch("culture_compliance.services.transcriber._upload_to_s3")
    @patch("culture_compliance.services.transcriber._extract_audio")
    def test_s3_upload_failure_returns_empty_list(
        self, mock_extract, mock_upload, mock_cleanup_s3, mock_cleanup_job
    ):
        """S3 upload failure should return empty list gracefully (Req 4.10)."""
        mock_extract.return_value = True
        mock_upload.side_effect = ClientError(
            error_response={
                "Error": {"Code": "AccessDenied", "Message": "Access Denied"}
            },
            operation_name="PutObject",
        )

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake video content")
            video_path = f.name

        try:
            result = transcribe_audio(video_path)
            assert result == []
        finally:
            if os.path.exists(video_path):
                os.unlink(video_path)

    @patch("culture_compliance.services.transcriber._cleanup_transcription_job")
    @patch("culture_compliance.services.transcriber._cleanup_s3")
    @patch("culture_compliance.services.transcriber._extract_audio")
    def test_unexpected_error_returns_empty_list(
        self, mock_extract, mock_cleanup_s3, mock_cleanup_job
    ):
        """Unexpected errors should return empty list gracefully (Req 4.10)."""
        mock_extract.side_effect = RuntimeError("Unexpected error")

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake video content")
            video_path = f.name

        try:
            result = transcribe_audio(video_path)
            assert result == []
        finally:
            if os.path.exists(video_path):
                os.unlink(video_path)

    @patch("culture_compliance.services.transcriber._cleanup_transcription_job")
    @patch("culture_compliance.services.transcriber._cleanup_s3")
    @patch("culture_compliance.services.transcriber._wait_for_job")
    @patch("culture_compliance.services.transcriber._start_transcription_job")
    @patch("culture_compliance.services.transcriber._upload_to_s3")
    @patch("culture_compliance.services.transcriber._extract_audio")
    def test_cleanup_called_on_success(
        self,
        mock_extract,
        mock_upload,
        mock_start,
        mock_wait,
        mock_cleanup_s3,
        mock_cleanup_job,
    ):
        """Cleanup should be called after successful transcription."""
        mock_extract.return_value = True
        mock_upload.return_value = "s3://bucket/key.wav"
        mock_start.return_value = "job-123"
        mock_wait.return_value = {
            "Transcript": {
                "TranscriptFileUri": "https://example.com/transcript.json"
            }
        }

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake video content")
            video_path = f.name

        try:
            with patch(
                "culture_compliance.services.transcriber._parse_transcript_results"
            ) as mock_parse:
                mock_parse.return_value = []
                transcribe_audio(video_path)

            # Verify cleanup was called
            mock_cleanup_s3.assert_called_once()
            mock_cleanup_job.assert_called_once()
        finally:
            if os.path.exists(video_path):
                os.unlink(video_path)

    @patch("culture_compliance.services.transcriber._cleanup_transcription_job")
    @patch("culture_compliance.services.transcriber._cleanup_s3")
    @patch("culture_compliance.services.transcriber._extract_audio")
    def test_cleanup_called_on_failure(
        self, mock_extract, mock_cleanup_s3, mock_cleanup_job
    ):
        """Cleanup should be called even when transcription fails."""
        mock_extract.return_value = False

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake video content")
            video_path = f.name

        try:
            transcribe_audio(video_path)

            # Cleanup should still be called
            mock_cleanup_s3.assert_called_once()
            mock_cleanup_job.assert_called_once()
        finally:
            if os.path.exists(video_path):
                os.unlink(video_path)
