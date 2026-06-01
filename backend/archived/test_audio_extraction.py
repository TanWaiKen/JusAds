"""Unit tests for audio extraction and ElevenLabs TTS integration.

Tests extract_audio_segment() and regenerate_with_elevenlabs() functions
including FFmpeg extraction, duration matching (trim/pad), and error handling.

Validates: Requirements 3.2, 3.3, 3.4, 3.6, 3.7
"""

import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.jusads_video_compliance.audio_remediator import (
    _get_audio_duration,
    _pad_audio_with_silence,
    _trim_audio,
    extract_audio_segment,
    regenerate_with_elevenlabs,
)


class TestExtractAudioSegment:
    """Tests for extract_audio_segment() (Req 3.2, 3.7)."""

    def test_invalid_start_sec_negative(self, tmp_path):
        """Negative start_sec should return False."""
        output = str(tmp_path / "out.mp3")
        result = extract_audio_segment("dummy.mp4", -1.0, 5.0, output)
        assert result is False

    def test_invalid_end_before_start(self, tmp_path):
        """end_sec <= start_sec should return False."""
        output = str(tmp_path / "out.mp3")
        result = extract_audio_segment("dummy.mp4", 5.0, 3.0, output)
        assert result is False

    def test_invalid_end_equals_start(self, tmp_path):
        """end_sec == start_sec should return False."""
        output = str(tmp_path / "out.mp3")
        result = extract_audio_segment("dummy.mp4", 3.0, 3.0, output)
        assert result is False

    def test_nonexistent_video_file(self, tmp_path):
        """Non-existent video file should return False."""
        output = str(tmp_path / "out.mp3")
        result = extract_audio_segment(
            "/nonexistent/video.mp4", 0.0, 5.0, output
        )
        assert result is False

    @patch("backend.jusads_video_compliance.audio_remediator.subprocess.run")
    def test_ffmpeg_nonzero_exit_code(self, mock_run, tmp_path):
        """FFmpeg returning non-zero exit code should return False."""
        # Create a dummy video file so the file existence check passes
        video_file = tmp_path / "video.mp4"
        video_file.write_bytes(b"fake video content")

        mock_run.return_value = MagicMock(
            returncode=1, stderr="Error: invalid input"
        )

        output = str(tmp_path / "out.mp3")
        result = extract_audio_segment(str(video_file), 0.0, 5.0, output)
        assert result is False

    @patch("backend.jusads_video_compliance.audio_remediator.subprocess.run")
    def test_ffmpeg_success_but_no_output_file(self, mock_run, tmp_path):
        """FFmpeg succeeds but output file not created should return False."""
        video_file = tmp_path / "video.mp4"
        video_file.write_bytes(b"fake video content")

        mock_run.return_value = MagicMock(returncode=0, stderr="")

        output = str(tmp_path / "nonexistent_dir" / "out.mp3")
        # Don't create the output file — simulates FFmpeg silently failing
        result = extract_audio_segment(str(video_file), 0.0, 5.0, output)
        assert result is False

    @patch("backend.jusads_video_compliance.audio_remediator.subprocess.run")
    def test_ffmpeg_timeout(self, mock_run, tmp_path):
        """FFmpeg timeout should return False."""
        video_file = tmp_path / "video.mp4"
        video_file.write_bytes(b"fake video content")

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ffmpeg", timeout=60)

        output = str(tmp_path / "out.mp3")
        result = extract_audio_segment(str(video_file), 0.0, 5.0, output)
        assert result is False

    @patch("backend.jusads_video_compliance.audio_remediator.subprocess.run")
    @patch("backend.jusads_video_compliance.audio_remediator.os.path.isfile")
    def test_successful_extraction(self, mock_isfile, mock_run, tmp_path):
        """Successful extraction should return True."""
        video_path = str(tmp_path / "video.mp4")
        output_path = str(tmp_path / "out.mp3")

        # First call checks video exists, second checks output exists
        mock_isfile.side_effect = lambda p: True

        mock_run.return_value = MagicMock(returncode=0, stderr="")

        result = extract_audio_segment(video_path, 1.0, 4.0, output_path)
        assert result is True

        # Verify FFmpeg was called with correct arguments
        call_args = mock_run.call_args[0][0]
        assert "ffmpeg" in call_args[0]
        assert "-ss" in call_args
        assert "1.0" in call_args
        assert "-t" in call_args
        assert "3.0" in call_args  # duration = end - start

    @patch("backend.jusads_video_compliance.audio_remediator.subprocess.run")
    def test_os_error_returns_false(self, mock_run, tmp_path):
        """OSError during FFmpeg execution should return False."""
        video_file = tmp_path / "video.mp4"
        video_file.write_bytes(b"fake video content")

        mock_run.side_effect = OSError("FFmpeg not found")

        output = str(tmp_path / "out.mp3")
        result = extract_audio_segment(str(video_file), 0.0, 5.0, output)
        assert result is False


class TestRegenerateWithElevenlabs:
    """Tests for regenerate_with_elevenlabs() (Req 3.3, 3.4, 3.6)."""

    @pytest.mark.asyncio
    async def test_empty_api_key_returns_false(self, tmp_path):
        """Missing API key should return False."""
        output = str(tmp_path / "out.mp3")
        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": ""}, clear=False):
            with patch(
                "backend.jusads_video_compliance.audio_remediator.ELEVENLABS_API_KEY",
                "",
            ):
                result = await regenerate_with_elevenlabs(
                    "Hello", "voice123", "en", 3.0, output
                )
                assert result is False

    @pytest.mark.asyncio
    async def test_empty_text_returns_false(self, tmp_path):
        """Empty text should return False."""
        output = str(tmp_path / "out.mp3")
        with patch.dict(
            os.environ, {"ELEVENLABS_API_KEY": "test_key"}, clear=False
        ):
            result = await regenerate_with_elevenlabs(
                "", "voice123", "en", 3.0, output
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_invalid_target_duration_returns_false(self, tmp_path):
        """Zero or negative target_duration should return False."""
        output = str(tmp_path / "out.mp3")
        with patch.dict(
            os.environ, {"ELEVENLABS_API_KEY": "test_key"}, clear=False
        ):
            result = await regenerate_with_elevenlabs(
                "Hello", "voice123", "en", 0.0, output
            )
            assert result is False

            result = await regenerate_with_elevenlabs(
                "Hello", "voice123", "en", -1.0, output
            )
            assert result is False

    @pytest.mark.asyncio
    @patch("backend.jusads_video_compliance.audio_remediator.httpx.AsyncClient")
    async def test_api_error_returns_false(self, mock_client_cls, tmp_path):
        """Non-200 API response should return False."""
        output = str(tmp_path / "out.mp3")

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with patch.dict(
            os.environ, {"ELEVENLABS_API_KEY": "test_key"}, clear=False
        ):
            result = await regenerate_with_elevenlabs(
                "Hello world", "voice123", "en", 3.0, output
            )
            assert result is False

    @pytest.mark.asyncio
    @patch("backend.jusads_video_compliance.audio_remediator._get_audio_duration")
    @patch("backend.jusads_video_compliance.audio_remediator.httpx.AsyncClient")
    async def test_within_tolerance_no_adjustment(
        self, mock_client_cls, mock_duration, tmp_path
    ):
        """Audio within ±0.2s tolerance should be used as-is."""
        output = str(tmp_path / "out.mp3")

        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake audio data"

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        # Duration is within tolerance (target=3.0, generated=3.1)
        mock_duration.side_effect = [3.1, 3.1]

        with patch.dict(
            os.environ, {"ELEVENLABS_API_KEY": "test_key"}, clear=False
        ):
            result = await regenerate_with_elevenlabs(
                "Hello world", "voice123", "en", 3.0, output
            )
            assert result is True
            # Verify output file exists (os.replace was called)
            assert os.path.isfile(output)

    @pytest.mark.asyncio
    @patch("backend.jusads_video_compliance.audio_remediator._get_audio_duration")
    @patch("backend.jusads_video_compliance.audio_remediator._trim_audio")
    @patch("backend.jusads_video_compliance.audio_remediator.httpx.AsyncClient")
    async def test_too_long_triggers_trim(
        self, mock_client_cls, mock_trim, mock_duration, tmp_path
    ):
        """Audio longer than target + 0.2s should be trimmed."""
        output = str(tmp_path / "out.mp3")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake audio data"

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        # Generated duration is 4.0s, target is 3.0s (diff = 1.0 > 0.2)
        mock_duration.side_effect = [4.0, 3.0]
        mock_trim.return_value = True

        # Create the output file to pass final check
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_bytes(b"trimmed audio")

        with patch.dict(
            os.environ, {"ELEVENLABS_API_KEY": "test_key"}, clear=False
        ):
            result = await regenerate_with_elevenlabs(
                "Hello world", "voice123", "en", 3.0, output
            )
            assert result is True
            mock_trim.assert_called_once()

    @pytest.mark.asyncio
    @patch("backend.jusads_video_compliance.audio_remediator._get_audio_duration")
    @patch(
        "backend.jusads_video_compliance.audio_remediator._pad_audio_with_silence"
    )
    @patch("backend.jusads_video_compliance.audio_remediator.httpx.AsyncClient")
    async def test_too_short_triggers_pad(
        self, mock_client_cls, mock_pad, mock_duration, tmp_path
    ):
        """Audio shorter than target - 0.2s should be padded with silence."""
        output = str(tmp_path / "out.mp3")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake audio data"

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        # Generated duration is 2.0s, target is 3.0s (diff = -1.0 < -0.2)
        mock_duration.side_effect = [2.0, 3.0]
        mock_pad.return_value = True

        # Create the output file to pass final check
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_bytes(b"padded audio")

        with patch.dict(
            os.environ, {"ELEVENLABS_API_KEY": "test_key"}, clear=False
        ):
            result = await regenerate_with_elevenlabs(
                "Hello world", "voice123", "en", 3.0, output
            )
            assert result is True
            mock_pad.assert_called_once()

    @pytest.mark.asyncio
    @patch("backend.jusads_video_compliance.audio_remediator._get_audio_duration")
    @patch("backend.jusads_video_compliance.audio_remediator.httpx.AsyncClient")
    async def test_duration_probe_failure_returns_false(
        self, mock_client_cls, mock_duration, tmp_path
    ):
        """Failure to probe generated audio duration should return False."""
        output = str(tmp_path / "out.mp3")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake audio data"

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        # Duration probe returns None (failure)
        mock_duration.return_value = None

        with patch.dict(
            os.environ, {"ELEVENLABS_API_KEY": "test_key"}, clear=False
        ):
            result = await regenerate_with_elevenlabs(
                "Hello world", "voice123", "en", 3.0, output
            )
            assert result is False

    @pytest.mark.asyncio
    @patch("backend.jusads_video_compliance.audio_remediator.httpx.AsyncClient")
    async def test_timeout_returns_false(self, mock_client_cls, tmp_path):
        """HTTP timeout should return False."""
        import httpx

        output = str(tmp_path / "out.mp3")

        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("Connection timed out")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with patch.dict(
            os.environ, {"ELEVENLABS_API_KEY": "test_key"}, clear=False
        ):
            result = await regenerate_with_elevenlabs(
                "Hello world", "voice123", "en", 3.0, output
            )
            assert result is False
