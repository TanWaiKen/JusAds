"""Unit tests for the error handler node.

Tests error capture, warning generation, timeout handling, and partial
ComplianceResult production.
"""

import time

import pytest

from culture_compliance.models.schemas import (
    ContentSubmission,
    ContentType,
    Market,
    PipelineState,
)
from culture_compliance.nodes.step7_result_formatting import error_handler


def _make_state(**overrides) -> PipelineState:
    """Create a PipelineState with sensible defaults for testing."""
    defaults = {
        "submission": ContentSubmission(
            content="Test content for compliance",
            content_type=ContentType.TEXT,
            market=Market.MALAYSIA,
        ),
        "content_type": ContentType.TEXT,
        "market": Market.MALAYSIA,
        "errors": [],
        "warnings": [],
        "models_used": [],
        "pipeline_start_ms": int(time.time() * 1000) - 500,  # 500ms ago
    }
    defaults.update(overrides)
    return PipelineState(**defaults)


class TestErrorHandlerBasic:
    """Tests for basic error handling behavior."""

    def test_captures_single_error_as_warning(self):
        """Error handler should convert errors to warnings array."""
        state = _make_state(
            errors=[
                {
                    "node_name": "guideline_retrieval",
                    "error_type": "service_unavailable",
                    "message": "Qdrant connection failed",
                }
            ]
        )

        result_state = error_handler(state)

        assert result_state.compliance_result is not None
        warnings = result_state.compliance_result["warnings"]
        assert len(warnings) == 1
        assert warnings[0]["step_name"] == "guideline_retrieval"
        assert warnings[0]["description"] == "Qdrant connection failed"
        assert warnings[0]["result_may_be_incomplete"] is True

    def test_captures_multiple_errors_as_warnings(self):
        """Error handler should convert all errors to warnings."""
        state = _make_state(
            errors=[
                {
                    "node_name": "guideline_retrieval",
                    "error_type": "service_unavailable",
                    "message": "Qdrant connection failed",
                },
                {
                    "node_name": "compliance_evaluation",
                    "error_type": "parse_error",
                    "message": "LLM returned invalid JSON",
                },
            ]
        )

        result_state = error_handler(state)

        warnings = result_state.compliance_result["warnings"]
        assert len(warnings) == 2
        assert warnings[0]["step_name"] == "guideline_retrieval"
        assert warnings[1]["step_name"] == "compliance_evaluation"

    def test_non_timeout_error_returns_high_risk(self):
        """Non-timeout errors should produce risk_level 'High' and score 0."""
        state = _make_state(
            errors=[
                {
                    "node_name": "compliance_evaluation",
                    "error_type": "parse_error",
                    "message": "LLM returned invalid JSON",
                }
            ]
        )

        result_state = error_handler(state)

        result = result_state.compliance_result
        assert result["risk_level"] == "High"
        assert result["score"] == 0
        assert result["high_risk_indicators"] == []

    def test_non_timeout_error_includes_error_description_in_explanation(self):
        """Explanation should describe the error(s) encountered."""
        state = _make_state(
            errors=[
                {
                    "node_name": "guideline_retrieval",
                    "error_type": "service_unavailable",
                    "message": "Qdrant connection failed",
                }
            ]
        )

        result_state = error_handler(state)

        result = result_state.compliance_result
        assert "Qdrant connection failed" in result["explanation"]

    def test_stores_result_in_state(self):
        """Error handler should store result in state.compliance_result."""
        state = _make_state(
            errors=[
                {
                    "node_name": "text_processing",
                    "error_type": "validation",
                    "message": "Content is empty",
                }
            ]
        )

        result_state = error_handler(state)

        assert result_state.compliance_result is not None
        assert isinstance(result_state.compliance_result, dict)


class TestErrorHandlerTimeout:
    """Tests for timeout error handling."""

    def test_timeout_returns_unknown_risk_level(self):
        """Timeout errors should produce risk_level 'Unknown'."""
        state = _make_state(
            errors=[
                {
                    "node_name": "compliance_evaluation",
                    "error_type": "timeout",
                    "message": "Pipeline execution exceeded 60 seconds",
                }
            ]
        )

        result_state = error_handler(state)

        result = result_state.compliance_result
        assert result["risk_level"] == "Unknown"

    def test_timeout_returns_score_negative_one(self):
        """Timeout errors should produce score -1."""
        state = _make_state(
            errors=[
                {
                    "node_name": "compliance_evaluation",
                    "error_type": "timeout",
                    "message": "Pipeline execution exceeded 60 seconds",
                }
            ]
        )

        result_state = error_handler(state)

        result = result_state.compliance_result
        assert result["score"] == -1

    def test_timeout_returns_empty_high_risk_indicators(self):
        """Timeout errors should produce empty high_risk_indicators."""
        state = _make_state(
            errors=[
                {
                    "node_name": "compliance_evaluation",
                    "error_type": "timeout",
                    "message": "Pipeline execution exceeded 60 seconds",
                }
            ]
        )

        result_state = error_handler(state)

        result = result_state.compliance_result
        assert result["high_risk_indicators"] == []

    def test_timeout_explanation_shows_completed_steps(self):
        """Timeout explanation should indicate which steps completed."""
        state = _make_state(
            unified_content="Some processed text",
            retrieved_guidelines="Some guidelines",
            errors=[
                {
                    "node_name": "compliance_evaluation",
                    "error_type": "timeout",
                    "message": "Pipeline execution exceeded 60 seconds",
                }
            ],
        )

        result_state = error_handler(state)

        result = result_state.compliance_result
        assert "Completed" in result["explanation"]
        assert "content_routing" in result["explanation"]
        assert "text_processing" in result["explanation"]
        assert "guideline_retrieval" in result["explanation"]

    def test_timeout_explanation_shows_not_reached_steps(self):
        """Timeout explanation should indicate which steps were not reached."""
        state = _make_state(
            unified_content="Some processed text",
            errors=[
                {
                    "node_name": "guideline_retrieval",
                    "error_type": "timeout",
                    "message": "Guideline retrieval timed out",
                }
            ],
        )

        result_state = error_handler(state)

        result = result_state.compliance_result
        assert "Not reached" in result["explanation"]
        assert "compliance_evaluation" in result["explanation"]
        assert "result_formatting" in result["explanation"]


class TestErrorHandlerMetadata:
    """Tests for processing metadata in error results."""

    def test_includes_processing_metadata(self):
        """Error result should include processing_metadata."""
        state = _make_state(
            models_used=["amazon.nova-pro-v1:0"],
            errors=[
                {
                    "node_name": "compliance_evaluation",
                    "error_type": "parse_error",
                    "message": "Invalid JSON",
                }
            ],
        )

        result_state = error_handler(state)

        metadata = result_state.compliance_result["processing_metadata"]
        assert "pipeline_duration_ms" in metadata
        assert metadata["pipeline_duration_ms"] >= 0
        assert metadata["models_used"] == ["amazon.nova-pro-v1:0"]
        assert metadata["market"] == "malaysia"

    def test_pipeline_duration_calculated_from_start(self):
        """Pipeline duration should be calculated from pipeline_start_ms."""
        start_ms = int(time.time() * 1000) - 1000  # 1 second ago
        state = _make_state(
            pipeline_start_ms=start_ms,
            errors=[
                {
                    "node_name": "text_processing",
                    "error_type": "validation",
                    "message": "Error",
                }
            ],
        )

        result_state = error_handler(state)

        metadata = result_state.compliance_result["processing_metadata"]
        # Duration should be at least 1000ms (we started 1s ago)
        assert metadata["pipeline_duration_ms"] >= 900  # Allow small timing variance

    def test_pipeline_duration_zero_when_no_start(self):
        """Pipeline duration should be 0 when pipeline_start_ms is None."""
        state = _make_state(
            pipeline_start_ms=None,
            errors=[
                {
                    "node_name": "text_processing",
                    "error_type": "validation",
                    "message": "Error",
                }
            ],
        )

        result_state = error_handler(state)

        metadata = result_state.compliance_result["processing_metadata"]
        assert metadata["pipeline_duration_ms"] == 0

    def test_preserves_content_type_and_market(self):
        """Error result should preserve content_type and market from state."""
        state = _make_state(
            content_type=ContentType.IMAGE,
            market=Market.SINGAPORE,
            submission=ContentSubmission(
                content="base64imagedata",
                content_type=ContentType.IMAGE,
                market=Market.SINGAPORE,
            ),
            errors=[
                {
                    "node_name": "image_processing",
                    "error_type": "service_unavailable",
                    "message": "Vision model unavailable",
                }
            ],
        )

        result_state = error_handler(state)

        result = result_state.compliance_result
        assert result["content_type"] == "image"
        assert result["market"] == "singapore"


class TestErrorHandlerEdgeCases:
    """Tests for edge cases in error handling."""

    def test_error_without_node_name_uses_error_type(self):
        """When node_name is missing, step_name should fall back to error_type."""
        state = _make_state(
            errors=[
                {
                    "error_type": "validation",
                    "message": "Something went wrong",
                }
            ]
        )

        result_state = error_handler(state)

        warnings = result_state.compliance_result["warnings"]
        assert warnings[0]["step_name"] == "validation"

    def test_error_without_message_uses_fallback(self):
        """When message is missing, description should use fallback text."""
        state = _make_state(
            errors=[
                {
                    "node_name": "some_node",
                    "error_type": "unknown",
                }
            ]
        )

        result_state = error_handler(state)

        warnings = result_state.compliance_result["warnings"]
        assert warnings[0]["description"] == "Unknown error"

    def test_explanation_truncated_to_500_chars(self):
        """Explanation should be truncated to 500 characters max."""
        # Create many errors to generate a long explanation
        errors = [
            {
                "node_name": f"step_{i}",
                "error_type": "service_unavailable",
                "message": f"Very long error message number {i} " * 10,
            }
            for i in range(20)
        ]
        state = _make_state(errors=errors)

        result_state = error_handler(state)

        result = result_state.compliance_result
        assert len(result["explanation"]) <= 500
