"""Unit tests for the result formatting node.

Tests the result_formatting function which parses raw LLM output into
a validated ComplianceResult with score-to-risk-level mapping, field
truncation, and processing metadata.
"""

import time

import pytest

from ..models.schemas import (
    ContentSubmission,
    ContentType,
    Market,
    PipelineState,
)
from ..nodes.step7_result_formatting import result_formatting


def _make_state(
    raw_llm_output: dict | None = None,
    content_type: ContentType = ContentType.TEXT,
    market: Market = Market.MALAYSIA,
    pipeline_start_ms: int | None = None,
    models_used: list[str] | None = None,
) -> PipelineState:
    """Helper to create a PipelineState for testing."""
    submission = ContentSubmission(
        content="Test content for compliance evaluation",
        content_type=content_type,
        market=market,
    )
    return PipelineState(
        submission=submission,
        content_type=content_type,
        market=market,
        raw_llm_output=raw_llm_output,
        pipeline_start_ms=pipeline_start_ms,
        models_used=models_used or ["apac.amazon.nova-lite-v1:0"],
    )


class TestResultFormattingBasic:
    """Tests for basic result formatting functionality."""

    def test_formats_valid_llm_output(self):
        """Valid LLM output is parsed into a ComplianceResult dict."""
        raw = {
            "risk_level": "Low",
            "score": 85,
            "high_risk_indicators": [],
            "explanation": "Content is compliant.",
            "suggestion": "No changes needed.",
        }
        state = _make_state(
            raw_llm_output=raw,
            pipeline_start_ms=int(time.time() * 1000) - 500,
        )

        result_state = result_formatting(state)

        assert result_state.compliance_result is not None
        assert result_state.compliance_result["score"] == 85
        assert result_state.compliance_result["risk_level"] == "Low"
        assert result_state.compliance_result["explanation"] == "Content is compliant."
        assert result_state.compliance_result["suggestion"] == "No changes needed."
        assert result_state.compliance_result["high_risk_indicators"] == []
        assert len(result_state.errors) == 0

    def test_no_raw_llm_output_appends_error(self):
        """Missing raw_llm_output results in an error."""
        state = _make_state(raw_llm_output=None)

        result_state = result_formatting(state)

        assert result_state.compliance_result is None
        assert len(result_state.errors) == 1
        assert result_state.errors[0]["node"] == "result_formatting"
        assert result_state.errors[0]["error_type"] == "validation"

    def test_empty_raw_llm_output_appends_error(self):
        """Empty dict raw_llm_output results in an error."""
        state = _make_state(raw_llm_output={})

        result_state = result_formatting(state)

        # Empty dict is falsy, so it should trigger the validation error
        assert result_state.compliance_result is None
        assert len(result_state.errors) == 1
        assert result_state.errors[0]["node"] == "result_formatting"


class TestScoreToRiskLevelMapping:
    """Tests for score-to-risk-level mapping override."""

    def test_high_score_maps_to_low_risk(self):
        """Score >= 75 maps to Low risk regardless of LLM risk_level."""
        raw = {
            "risk_level": "High",  # LLM says High, but score says Low
            "score": 80,
            "high_risk_indicators": [],
            "explanation": "Test",
            "suggestion": "Test",
        }
        state = _make_state(raw_llm_output=raw)

        result_state = result_formatting(state)

        assert result_state.compliance_result["risk_level"] == "Low"

    def test_medium_score_maps_to_medium_risk(self):
        """Score 40-74 maps to Medium risk."""
        raw = {
            "risk_level": "Low",  # LLM says Low, but score says Medium
            "score": 55,
            "high_risk_indicators": [],
            "explanation": "Test",
            "suggestion": "Test",
        }
        state = _make_state(raw_llm_output=raw)

        result_state = result_formatting(state)

        assert result_state.compliance_result["risk_level"] == "Medium"

    def test_low_score_maps_to_high_risk(self):
        """Score < 40 maps to High risk."""
        raw = {
            "risk_level": "Low",  # LLM says Low, but score says High
            "score": 20,
            "high_risk_indicators": [],
            "explanation": "Test",
            "suggestion": "Test",
        }
        state = _make_state(raw_llm_output=raw)

        result_state = result_formatting(state)

        assert result_state.compliance_result["risk_level"] == "High"

    def test_boundary_score_75_is_low(self):
        """Score exactly 75 maps to Low risk."""
        raw = {
            "score": 75,
            "high_risk_indicators": [],
            "explanation": "Test",
            "suggestion": "Test",
        }
        state = _make_state(raw_llm_output=raw)

        result_state = result_formatting(state)

        assert result_state.compliance_result["risk_level"] == "Low"

    def test_boundary_score_40_is_medium(self):
        """Score exactly 40 maps to Medium risk."""
        raw = {
            "score": 40,
            "high_risk_indicators": [],
            "explanation": "Test",
            "suggestion": "Test",
        }
        state = _make_state(raw_llm_output=raw)

        result_state = result_formatting(state)

        assert result_state.compliance_result["risk_level"] == "Medium"

    def test_boundary_score_39_is_high(self):
        """Score exactly 39 maps to High risk."""
        raw = {
            "score": 39,
            "high_risk_indicators": [],
            "explanation": "Test",
            "suggestion": "Test",
        }
        state = _make_state(raw_llm_output=raw)

        result_state = result_formatting(state)

        assert result_state.compliance_result["risk_level"] == "High"


class TestFieldTruncation:
    """Tests for field length enforcement."""

    def test_truncates_explanation_to_500_chars(self):
        """Explanation exceeding 500 chars is truncated."""
        long_explanation = "A" * 600
        raw = {
            "score": 80,
            "high_risk_indicators": [],
            "explanation": long_explanation,
            "suggestion": "Test",
        }
        state = _make_state(raw_llm_output=raw)

        result_state = result_formatting(state)

        assert len(result_state.compliance_result["explanation"]) == 500

    def test_truncates_suggestion_to_400_chars(self):
        """Suggestion exceeding 400 chars is truncated."""
        long_suggestion = "B" * 500
        raw = {
            "score": 80,
            "high_risk_indicators": [],
            "explanation": "Test",
            "suggestion": long_suggestion,
        }
        state = _make_state(raw_llm_output=raw)

        result_state = result_formatting(state)

        assert len(result_state.compliance_result["suggestion"]) == 400

    def test_max_10_high_risk_indicators(self):
        """More than 10 indicators are truncated to 10."""
        indicators = [
            {
                "phrase": f"issue {i}",
                "char_offset": i * 10,
                "category": "Profanity",
                "severity": "Minor",
            }
            for i in range(15)
        ]
        raw = {
            "score": 30,
            "high_risk_indicators": indicators,
            "explanation": "Many issues found",
            "suggestion": "Fix them",
        }
        state = _make_state(raw_llm_output=raw)

        result_state = result_formatting(state)

        assert len(result_state.compliance_result["high_risk_indicators"]) == 10


class TestHighRiskIndicatorParsing:
    """Tests for parsing indicators based on content type."""

    def test_parses_text_indicators(self):
        """Text indicators with phrase and char_offset are parsed."""
        raw = {
            "score": 50,
            "high_risk_indicators": [
                {
                    "phrase": "offensive word",
                    "char_offset": 42,
                    "category": "Profanity",
                    "severity": "Moderate",
                }
            ],
            "explanation": "Contains profanity",
            "suggestion": "Remove offensive language",
        }
        state = _make_state(
            raw_llm_output=raw, content_type=ContentType.TEXT
        )

        result_state = result_formatting(state)

        indicators = result_state.compliance_result["high_risk_indicators"]
        assert len(indicators) == 1
        assert indicators[0]["phrase"] == "offensive word"
        assert indicators[0]["char_offset"] == 42
        assert indicators[0]["category"] == "Profanity"
        assert indicators[0]["severity"] == "Moderate"

    def test_parses_image_indicators(self):
        """Image indicators with bounding_box are parsed."""
        raw = {
            "score": 45,
            "high_risk_indicators": [
                {
                    "bounding_box": {
                        "x": 10,
                        "y": 20,
                        "width": 30,
                        "height": 40,
                    },
                    "description": "Inappropriate visual element",
                    "category": "Sexual/Explicit",
                    "severity": "Severe",
                }
            ],
            "explanation": "Contains explicit imagery",
            "suggestion": "Remove the visual element",
        }
        state = _make_state(
            raw_llm_output=raw, content_type=ContentType.IMAGE
        )

        result_state = result_formatting(state)

        indicators = result_state.compliance_result["high_risk_indicators"]
        assert len(indicators) == 1
        assert indicators[0]["bounding_box"] == {
            "x": 10,
            "y": 20,
            "width": 30,
            "height": 40,
        }

    def test_parses_video_indicators(self):
        """Video indicators with timestamp are parsed."""
        raw = {
            "score": 35,
            "high_risk_indicators": [
                {
                    "timestamp": "01:23",
                    "description": "Problematic scene",
                    "category": "Religious Sensitivity",
                    "severity": "Severe",
                }
            ],
            "explanation": "Contains sensitive content",
            "suggestion": "Edit the scene",
        }
        state = _make_state(
            raw_llm_output=raw, content_type=ContentType.VIDEO
        )

        result_state = result_formatting(state)

        indicators = result_state.compliance_result["high_risk_indicators"]
        assert len(indicators) == 1
        assert indicators[0]["timestamp"] == "01:23"

    def test_skips_invalid_indicators(self):
        """Invalid indicators are skipped without failing."""
        raw = {
            "score": 60,
            "high_risk_indicators": [
                {"invalid": "data"},  # Missing required fields
                {
                    "phrase": "valid issue",
                    "char_offset": 5,
                    "category": "Profanity",
                    "severity": "Minor",
                },
            ],
            "explanation": "Test",
            "suggestion": "Test",
        }
        state = _make_state(raw_llm_output=raw)

        result_state = result_formatting(state)

        indicators = result_state.compliance_result["high_risk_indicators"]
        assert len(indicators) == 1
        assert indicators[0]["phrase"] == "valid issue"


class TestProcessingMetadata:
    """Tests for processing metadata generation."""

    def test_includes_pipeline_duration(self):
        """Processing metadata includes pipeline duration."""
        start_ms = int(time.time() * 1000) - 1000  # 1 second ago
        raw = {
            "score": 100,
            "high_risk_indicators": [],
            "explanation": "Clean",
            "suggestion": "None",
        }
        state = _make_state(
            raw_llm_output=raw, pipeline_start_ms=start_ms
        )

        result_state = result_formatting(state)

        metadata = result_state.compliance_result["processing_metadata"]
        assert metadata["pipeline_duration_ms"] >= 1000

    def test_includes_models_used(self):
        """Processing metadata includes models used."""
        raw = {
            "score": 100,
            "high_risk_indicators": [],
            "explanation": "Clean",
            "suggestion": "None",
        }
        state = _make_state(
            raw_llm_output=raw,
            models_used=["model-a", "model-b"],
        )

        result_state = result_formatting(state)

        metadata = result_state.compliance_result["processing_metadata"]
        assert metadata["models_used"] == ["model-a", "model-b"]

    def test_includes_market(self):
        """Processing metadata includes the evaluated market."""
        raw = {
            "score": 100,
            "high_risk_indicators": [],
            "explanation": "Clean",
            "suggestion": "None",
        }
        state = _make_state(
            raw_llm_output=raw, market=Market.SINGAPORE
        )

        result_state = result_formatting(state)

        metadata = result_state.compliance_result["processing_metadata"]
        assert metadata["market"] == "singapore"

    def test_zero_duration_when_no_start_time(self):
        """Duration is 0 when pipeline_start_ms is None."""
        raw = {
            "score": 100,
            "high_risk_indicators": [],
            "explanation": "Clean",
            "suggestion": "None",
        }
        state = _make_state(
            raw_llm_output=raw, pipeline_start_ms=None
        )

        result_state = result_formatting(state)

        metadata = result_state.compliance_result["processing_metadata"]
        assert metadata["pipeline_duration_ms"] == 0


class TestScoreEdgeCases:
    """Tests for score edge cases and type coercion."""

    def test_score_clamped_to_0_minimum(self):
        """Negative scores are clamped to 0."""
        raw = {
            "score": -10,
            "high_risk_indicators": [],
            "explanation": "Test",
            "suggestion": "Test",
        }
        state = _make_state(raw_llm_output=raw)

        result_state = result_formatting(state)

        assert result_state.compliance_result["score"] == 0

    def test_score_clamped_to_100_maximum(self):
        """Scores above 100 are clamped to 100."""
        raw = {
            "score": 150,
            "high_risk_indicators": [],
            "explanation": "Test",
            "suggestion": "Test",
        }
        state = _make_state(raw_llm_output=raw)

        result_state = result_formatting(state)

        assert result_state.compliance_result["score"] == 100

    def test_string_score_coerced_to_int(self):
        """String scores are coerced to integers."""
        raw = {
            "score": "85",
            "high_risk_indicators": [],
            "explanation": "Test",
            "suggestion": "Test",
        }
        state = _make_state(raw_llm_output=raw)

        result_state = result_formatting(state)

        assert result_state.compliance_result["score"] == 85

    def test_invalid_score_defaults_to_zero(self):
        """Non-numeric scores default to 0."""
        raw = {
            "score": "invalid",
            "high_risk_indicators": [],
            "explanation": "Test",
            "suggestion": "Test",
        }
        state = _make_state(raw_llm_output=raw)

        result_state = result_formatting(state)

        assert result_state.compliance_result["score"] == 0


class TestUTF8Serialization:
    """Tests for UTF-8 JSON serialization preserving non-ASCII."""

    def test_preserves_malay_characters(self):
        """Non-ASCII Malay text is preserved in serialization."""
        raw = {
            "score": 70,
            "high_risk_indicators": [],
            "explanation": "Kandungan mengandungi isu sensitiviti agama",
            "suggestion": "Sila ubah kandungan untuk mengelakkan isu",
        }
        state = _make_state(raw_llm_output=raw)

        result_state = result_formatting(state)

        assert (
            result_state.compliance_result["explanation"]
            == "Kandungan mengandungi isu sensitiviti agama"
        )

    def test_preserves_chinese_characters(self):
        """Chinese characters are preserved in serialization."""
        raw = {
            "score": 90,
            "high_risk_indicators": [],
            "explanation": "内容符合规定",
            "suggestion": "无需修改",
        }
        state = _make_state(raw_llm_output=raw)

        result_state = result_formatting(state)

        assert result_state.compliance_result["explanation"] == "内容符合规定"
        assert result_state.compliance_result["suggestion"] == "无需修改"

    def test_preserves_tamil_characters(self):
        """Tamil characters are preserved in serialization."""
        raw = {
            "score": 80,
            "high_risk_indicators": [],
            "explanation": "உள்ளடக்கம் இணக்கமானது",
            "suggestion": "மாற்றங்கள் தேவையில்லை",
        }
        state = _make_state(raw_llm_output=raw)

        result_state = result_formatting(state)

        assert (
            result_state.compliance_result["explanation"]
            == "உள்ளடக்கம் இணக்கமானது"
        )
