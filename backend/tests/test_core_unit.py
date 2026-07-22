"""Focused unit tests for the core JusAds routing logic.

These tests avoid live AI, database, storage, and social-platform calls.
"""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jusads_compliance.compliance_pipeline import _route_after_fetch
from jusads_compliance.decision_router import route_compliance_decision
from jusads_generation.distribution import _resolve_account_id
from jusads_generation.intent import detect_media_types


def test_compliance_routes_audio_and_video_to_transcription() -> None:
    """Audio and video require transcription before analysis."""
    for media_type in ("audio", "video"):
        state = {"media_type": media_type}
        assert _route_after_fetch(state) == "transcribe_media"


def test_compliance_routes_text_and_image_to_analysis() -> None:
    """Text and image can proceed directly to multimodal analysis."""
    for media_type in ("text", "image"):
        state = {"media_type": media_type}
        assert _route_after_fetch(state) == "main_brain_analysis"


def test_decision_router_accepts_low_risk_boundary() -> None:
    """A low-risk advertisement at the 30 percent threshold passes."""
    assert route_compliance_decision("Low", 30, []) == "pass"


def test_decision_router_requests_remediation_for_moderate_risk() -> None:
    """A moderate-risk advertisement is sent for remediation."""
    assert route_compliance_decision("Moderate", 55, ["gender bias"]) == "remediate"


def test_decision_router_rejects_critical_risk() -> None:
    """Critical risk is routed to critical regeneration."""
    assert route_compliance_decision("Critical", 50, ["offensive content"]) == "critical_regen"


def test_decision_router_rejects_scores_above_85_percent() -> None:
    """A score above 85 percent is treated as critical."""
    assert route_compliance_decision("High", 86, ["serious violation"]) == "critical_regen"


def test_intent_detector_uses_keyword_fallback_for_video() -> None:
    """The fallback detector identifies a video generation request."""
    with patch("jusads_generation.intent._classify_with_gemini", return_value=None):
        assert detect_media_types("Generate a TikTok video ad") == ["video"]


def test_intent_detector_identifies_multiple_media_types() -> None:
    """The detector can identify both text and image requests."""
    with patch("jusads_generation.intent._classify_with_gemini", return_value=None):
        assert detect_media_types("Create image and text ads") == ["text", "image"]


def test_intent_detector_ignores_empty_message() -> None:
    """An empty request does not start media generation."""
    assert detect_media_types("   ") == []


def test_distribution_resolves_supported_accounts() -> None:
    """TikTok and Instagram resolve to their configured test accounts."""
    with patch("jusads_generation.distribution.ZERNIO_ACCOUNT_TIKTOK", "test-tiktok-id"), patch(
        "jusads_generation.distribution.ZERNIO_ACCOUNT_INSTAGRAM", "test-instagram-id"
    ):
        assert _resolve_account_id("TikTok") == "test-tiktok-id"
        assert _resolve_account_id("instagram") == "test-instagram-id"
        assert _resolve_account_id("unknown") is None
