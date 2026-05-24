"""Integration-style tests for the text pipeline flow.

Tests the full text pipeline flow (text_processing → guideline_retrieval →
compliance_evaluation) with mocked external services (Qdrant, Bedrock).

These tests verify that the nodes compose correctly and state flows
properly between pipeline stages.

Requirements: 2.1, 2.5, 2.6, 2.7
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from culture_compliance.models.schemas import (
    ContentSubmission,
    ContentType,
    Market,
    PipelineState,
)
from culture_compliance.nodes.step4_text_analysis import text_processing
from culture_compliance.nodes.step5_guideline_retrieval import guideline_retrieval
from culture_compliance.nodes.step6_compliance_evaluation import compliance_evaluation


def _make_initial_state(
    content: str = "Buy our halal-certified product today!",
    market: Market = Market.MALAYSIA,
    collection: str = "mcmc-guidelines",
) -> PipelineState:
    """Create an initial PipelineState as it would be after routing."""
    submission = ContentSubmission(
        content=content,
        content_type=ContentType.TEXT,
        market=market,
    )
    state = PipelineState(
        submission=submission,
        content_type=ContentType.TEXT,
        market=market,
    )
    state.guideline_collection = collection
    return state


def _mock_qdrant_results(num_points: int = 3):
    """Create mock Qdrant query results."""
    points = []
    for i in range(num_points):
        point = SimpleNamespace(
            id=f"point-{i}",
            score=0.95 - (i * 0.05),
            payload={
                "source": "mcmc_guidelines.csv",
                "row_text": f"guideline text {i}",
                "Category": f"Category {i}",
                "Guideline": f"Guideline content {i}",
            },
        )
        points.append(point)
    return SimpleNamespace(points=points)


def _mock_bedrock_response(json_output: str) -> dict:
    """Create a mock Bedrock Converse API response."""
    return {
        "output": {
            "message": {
                "content": [{"text": json_output}]
            }
        }
    }


class TestTextPipelineFlowSuccess:
    """Tests for the full text pipeline flow with mocked services."""

    @patch("culture_compliance.nodes.step6_compliance_evaluation._get_bedrock_client")
    @patch("culture_compliance.nodes.step5_guideline_retrieval._get_qdrant_client")
    @patch("culture_compliance.nodes.step5_guideline_retrieval.embed_text")
    def test_full_flow_produces_llm_output(
        self, mock_embed, mock_get_qdrant, mock_get_bedrock
    ):
        """Full flow: text_processing → guideline_retrieval → compliance_evaluation."""
        # Setup mocks
        mock_embed.return_value = [0.1] * 1024
        mock_qdrant_client = MagicMock()
        mock_qdrant_client.query_points.return_value = _mock_qdrant_results(3)
        mock_get_qdrant.return_value = mock_qdrant_client

        llm_output = '{"RISK": "Low", "SCORE": 95, "high_risk_indicator": [], "explanation": "Content is culturally appropriate.", "suggestion": "No changes needed."}'
        mock_bedrock_client = MagicMock()
        mock_bedrock_client.converse.return_value = _mock_bedrock_response(llm_output)
        mock_get_bedrock.return_value = mock_bedrock_client

        # Execute pipeline flow
        state = _make_initial_state()
        state = text_processing(state)
        state = guideline_retrieval(state)
        state = compliance_evaluation(state)

        # Verify end state
        assert state.errors == []
        assert state.unified_content == "Buy our halal-certified product today!"
        assert state.retrieved_guidelines is not None
        assert "[R1]" in state.retrieved_guidelines
        assert state.raw_llm_output is not None
        assert state.raw_llm_output["RISK"] == "Low"
        assert state.raw_llm_output["SCORE"] == 95

    @patch("culture_compliance.nodes.step6_compliance_evaluation._get_bedrock_client")
    @patch("culture_compliance.nodes.step5_guideline_retrieval._get_qdrant_client")
    @patch("culture_compliance.nodes.step5_guideline_retrieval.embed_text")
    def test_flow_with_singapore_market(
        self, mock_embed, mock_get_qdrant, mock_get_bedrock
    ):
        """Full flow works correctly with Singapore market."""
        mock_embed.return_value = [0.1] * 1024
        mock_qdrant_client = MagicMock()
        mock_qdrant_client.query_points.return_value = _mock_qdrant_results(2)
        mock_get_qdrant.return_value = mock_qdrant_client

        llm_output = '{"RISK": "Low", "SCORE": 88, "high_risk_indicator": [], "explanation": "Appropriate for SG.", "suggestion": "None."}'
        mock_bedrock_client = MagicMock()
        mock_bedrock_client.converse.return_value = _mock_bedrock_response(llm_output)
        mock_get_bedrock.return_value = mock_bedrock_client

        state = _make_initial_state(
            market=Market.SINGAPORE,
            collection="singapore-imda-asas-guidelines",
        )
        state = text_processing(state)
        state = guideline_retrieval(state)
        state = compliance_evaluation(state)

        assert state.errors == []
        assert state.raw_llm_output["SCORE"] == 88
        # Verify correct regulatory collection was queried (first call)
        calls = mock_qdrant_client.query_points.call_args_list
        assert len(calls) == 2  # regulatory + cultural
        assert calls[0].kwargs["collection_name"] == "singapore-imda-asas-guidelines" or calls[0][1].get("collection_name") == "singapore-imda-asas-guidelines"

    @patch("culture_compliance.nodes.step6_compliance_evaluation._get_bedrock_client")
    @patch("culture_compliance.nodes.step5_guideline_retrieval._get_qdrant_client")
    @patch("culture_compliance.nodes.step5_guideline_retrieval.embed_text")
    def test_flow_tracks_model_usage(
        self, mock_embed, mock_get_qdrant, mock_get_bedrock
    ):
        """Models used are tracked through the pipeline flow."""
        mock_embed.return_value = [0.1] * 1024
        mock_qdrant_client = MagicMock()
        mock_qdrant_client.query_points.return_value = _mock_qdrant_results(1)
        mock_get_qdrant.return_value = mock_qdrant_client

        llm_output = '{"RISK": "Low", "SCORE": 100, "high_risk_indicator": [], "explanation": "OK.", "suggestion": "None."}'
        mock_bedrock_client = MagicMock()
        mock_bedrock_client.converse.return_value = _mock_bedrock_response(llm_output)
        mock_get_bedrock.return_value = mock_bedrock_client

        state = _make_initial_state()
        state = text_processing(state)
        state = guideline_retrieval(state)
        state = compliance_evaluation(state)

        assert len(state.models_used) >= 1


class TestTextPipelineFlowErrors:
    """Tests for error propagation in the text pipeline flow."""

    @patch("culture_compliance.nodes.step5_guideline_retrieval._get_qdrant_client")
    @patch("culture_compliance.nodes.step5_guideline_retrieval.embed_text")
    def test_guideline_failure_prevents_evaluation(
        self, mock_embed, mock_get_qdrant
    ):
        """When guideline retrieval fails, compliance evaluation cannot proceed.

        Validates Requirement 2.6: If the Guideline_Store is unreachable,
        the pipeline returns an error indicating guideline retrieval failed.
        """
        mock_embed.return_value = [0.1] * 1024
        mock_qdrant_client = MagicMock()
        mock_qdrant_client.query_points.side_effect = ConnectionError(
            "Qdrant unavailable"
        )
        mock_get_qdrant.return_value = mock_qdrant_client

        state = _make_initial_state()
        state = text_processing(state)
        state = guideline_retrieval(state)

        # Guideline retrieval failed — state has error, no guidelines
        assert len(state.errors) == 1
        assert state.errors[0]["error_type"] == "service_unavailable"
        assert state.retrieved_guidelines is None

        # Compliance evaluation should also fail due to missing guidelines
        state = compliance_evaluation(state)
        assert len(state.errors) == 2
        assert state.errors[1]["node"] == "compliance_evaluation"
        assert state.errors[1]["error_type"] == "validation"

    @patch("culture_compliance.nodes.step6_compliance_evaluation._get_bedrock_client")
    @patch("culture_compliance.nodes.step5_guideline_retrieval._get_qdrant_client")
    @patch("culture_compliance.nodes.step5_guideline_retrieval.embed_text")
    def test_llm_failure_after_successful_retrieval(
        self, mock_embed, mock_get_qdrant, mock_get_bedrock
    ):
        """When LLM fails, error is captured but guidelines are preserved.

        Validates Requirement 2.7: If the LLM invocation fails, the pipeline
        returns an error indicating evaluation could not be completed.
        """
        mock_embed.return_value = [0.1] * 1024
        mock_qdrant_client = MagicMock()
        mock_qdrant_client.query_points.return_value = _mock_qdrant_results(3)
        mock_get_qdrant.return_value = mock_qdrant_client

        mock_bedrock_client = MagicMock()
        mock_bedrock_client.converse.side_effect = Exception("Service unavailable")
        mock_get_bedrock.return_value = mock_bedrock_client

        state = _make_initial_state()
        state = text_processing(state)
        state = guideline_retrieval(state)
        state = compliance_evaluation(state)

        # Guidelines were retrieved successfully
        assert state.retrieved_guidelines is not None
        assert "[R1]" in state.retrieved_guidelines
        # But LLM failed
        assert len(state.errors) == 1
        assert state.errors[0]["node"] == "compliance_evaluation"
        assert state.errors[0]["error_type"] == "service_unavailable"
        assert state.raw_llm_output is None

    def test_empty_text_stops_pipeline_early(self):
        """Empty text is rejected at text_processing, preventing downstream calls.

        Validates Requirement 2.5: Empty/whitespace text returns validation error.
        """
        # Bypass Pydantic validation to test node-level defense
        submission = ContentSubmission.__new__(ContentSubmission)
        object.__setattr__(submission, "content", "   ")
        object.__setattr__(submission, "content_type", ContentType.TEXT)
        object.__setattr__(submission, "market", Market.MALAYSIA)
        object.__setattr__(submission, "frame_interval_seconds", 1.0)

        state = PipelineState.__new__(PipelineState)
        object.__setattr__(state, "submission", submission)
        object.__setattr__(state, "content_type", ContentType.TEXT)
        object.__setattr__(state, "market", Market.MALAYSIA)
        object.__setattr__(state, "extracted_text", None)
        object.__setattr__(state, "visual_description", None)
        object.__setattr__(state, "unified_content", None)
        object.__setattr__(state, "frame_descriptions", None)
        object.__setattr__(state, "transcript_segments", None)
        object.__setattr__(state, "retrieved_guidelines", None)
        object.__setattr__(state, "guideline_collection", "mcmc-guidelines")
        object.__setattr__(state, "raw_llm_output", None)
        object.__setattr__(state, "compliance_result", None)
        object.__setattr__(state, "errors", [])
        object.__setattr__(state, "warnings", [])
        object.__setattr__(state, "pipeline_start_ms", None)
        object.__setattr__(state, "models_used", [])

        state = text_processing(state)

        # Text processing rejects empty text
        assert len(state.errors) == 1
        assert state.errors[0]["error_type"] == "validation"
        assert state.unified_content is None

        # Guideline retrieval would also fail (no unified_content)
        state = guideline_retrieval(state)
        assert len(state.errors) == 2

    @patch("culture_compliance.nodes.step5_guideline_retrieval.embed_text")
    def test_embedding_failure_prevents_evaluation(self, mock_embed):
        """When embedding fails, no guidelines are retrieved and evaluation cannot proceed.

        Validates Requirement 2.6: Guideline store failure handling.
        """
        mock_embed.side_effect = Exception("Bedrock embedding throttled")

        state = _make_initial_state()
        state = text_processing(state)
        state = guideline_retrieval(state)

        assert len(state.errors) == 1
        assert state.errors[0]["error_type"] == "service_unavailable"
        assert "embed" in state.errors[0]["message"].lower()

        # Compliance evaluation cannot proceed without guidelines
        state = compliance_evaluation(state)
        assert len(state.errors) == 2
        assert state.errors[1]["error_type"] == "validation"
