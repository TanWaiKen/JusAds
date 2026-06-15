"""
conftest.py
───────────
Shared pytest fixtures for the remix remediation test suite.
"""

import pytest
from unittest.mock import MagicMock, patch
from agent.data_model import ComplianceState


# ── Mock Client Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def mock_gemini():
    """Mock the Gemini client from agent.clients."""
    with patch("agent.clients.gemini") as mock:
        mock_response = MagicMock()
        mock_response.text = '{"rewritten_text": "compliant text", "changes_made": ["fixed violation"]}'
        mock.models.generate_content.return_value = mock_response
        yield mock


@pytest.fixture
def mock_elevenlabs():
    """Mock the ElevenLabs client from agent.clients."""
    with patch("agent.clients.elevenlabs") as mock:
        mock_audio = MagicMock()
        mock_audio.content = b"\x00" * 1024
        mock.text_to_speech.convert.return_value = mock_audio
        mock_dubbing = MagicMock()
        mock_dubbing.dubbing_id = "dub_test_123"
        mock.dubbing.create.return_value = mock_dubbing
        yield mock


@pytest.fixture
def mock_ffmpeg():
    """Mock FFmpeg subprocess calls."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
        yield mock_run


# ── Sample Asset Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def sample_text():
    """Sample ad text for testing text rewriting."""
    return "Buy now! This amazing product will cure all your health problems instantly!"


@pytest.fixture
def sample_image_path(tmp_path):
    """Sample image path for testing image editing."""
    img_path = tmp_path / "test_ad.png"
    img_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    return str(img_path)


@pytest.fixture
def sample_audio_path(tmp_path):
    """Sample audio path for testing audio remediation."""
    audio_path = tmp_path / "test_ad.wav"
    audio_path.write_bytes(b"RIFF" + b"\x00" * 256)
    return str(audio_path)


@pytest.fixture
def sample_video_path(tmp_path):
    """Sample video path for testing video composition."""
    video_path = tmp_path / "test_ad.mp4"
    video_path.write_bytes(b"\x00" * 256)
    return str(video_path)


# ── ComplianceState Factory Fixture ───────────────────────────────────────────


@pytest.fixture
def compliance_state_factory():
    """Factory that creates ComplianceState instances with remix fields."""

    def _create(
        media_type: str = "text",
        session_id: str = "test-session-001",
        input_path: str = "/tmp/test_asset.png",
        text_input: str = "Sample ad text for compliance check",
        market: str = "malaysia",
        platform: str = "tiktok",
        ethnicity: str = "malay",
        age_group: str = "gen_z",
        status: str = "edit_pending",
        remediated_path: str = "",
        remix_iteration: int = 0,
        result: dict | None = None,
    ) -> ComplianceState:
        if result is None:
            result = {
                "violations": [{"description": "Non-compliant content", "severity": "high"}],
                "compliance_score": 45,
            }
        return ComplianceState(
            session_id=session_id,
            media_type=media_type,
            input_path=input_path,
            text_input=text_input,
            market=market,
            platform=platform,
            ethnicity=ethnicity,
            age_group=age_group,
            iteration=0,
            result=result,
            status=status,
            remediated_path=remediated_path,
            remix_iteration=remix_iteration,
        )

    return _create
