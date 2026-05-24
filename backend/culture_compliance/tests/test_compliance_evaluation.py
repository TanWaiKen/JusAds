"""Unit tests for the compliance evaluation node.

Tests validate that the compliance evaluation node correctly:
- Invokes the LLM with content and guidelines (mocked Bedrock)
- Parses valid JSON responses from the LLM
- Handles LLM invocation failures gracefully
- Handles unparseable LLM responses
- Validates prerequisites (unified_content, retrieved_guidelines)
- Tracks model usage in state

Requirements: 2.1, 2.5, 2.6, 2.7
"""

from unittest.mock import MagicMock, patch

import pytest

from culture_compliance.models.schemas import (
    ContentSubmission,
    ContentType,
    Market,
    PipelineState,
)
from culture_compliance.nodes.step6_compliance_evaluation import (
    compliance_evaluation,
    _parse_llm_json,
    _build_prompt,
)


def _make_state(
    content: str = "Buy our halal-certified product today!",
    market: Market = Market.MALAYSIA,
    unified_content: str = "Buy our halal-certified product today!",
    retrieved_guidelines: str = "[1] (source: mcmc, relevance: 0.95)\nGuideline about halal",
) -> PipelineState:
    """Helper to create a PipelineState for compliance evaluation testing."""
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
    state.unified_content = unified_content
    state.retrieved_guidelines = retrieved_guidelines
    return state


def _mock_bedrock_response(json_output: str) -> dict:
    """Create a mock Bedrock Converse API response."""
    return {
        "output": {
            "message": {
                "content": [{"text": json_output}]
            }
        }
    }


class TestComplianceEvaluationSuccess:
    """Tests for successful compliance evaluation with mocked Bedrock."""

    @patch("culture_compliance.nodes.step6_compliance_evaluation._get_bedrock_client")
    def test_successful_evaluation_stores_raw_output(self, mock_get_client):
        """LLM returns valid JSON which is stored in state.raw_llm_output."""
        llm_output = '{"RISK": "Low", "SCORE": 95, "high_risk_indicator": [], "explanation": "Content is appropriate.", "suggestion": "No changes needed."}'
        mock_client = MagicMock()
        mock_client.converse.return_value = _mock_bedrock_response(llm_output)
        mock_get_client.return_value = mock_client

        state = _make_state()
        result = compliance_evaluation(state)

        assert result.raw_llm_output is not None
        assert result.raw_llm_output["RISK"] == "Low"
        assert result.raw_llm_output["SCORE"] == 95
        assert result.errors == []

    @patch("culture_compliance.nodes.step6_compliance_evaluation._get_bedrock_client")
    def test_tracks_model_in_models_used(self, mock_get_client):
        """Model ID is appended to state.models_used after successful invocation."""
        llm_output = '{"RISK": "Low", "SCORE": 100, "high_risk_indicator": [], "explanation": "Clean.", "suggestion": "None."}'
        mock_client = MagicMock()
        mock_client.converse.return_value = _mock_bedrock_response(llm_output)
        mock_get_client.return_value = mock_client

        state = _make_state()
        result = compliance_evaluation(state)

        assert len(result.models_used) == 1
        assert result.models_used[0] != ""

    @patch("culture_compliance.nodes.step6_compliance_evaluation._get_bedrock_client")
    def test_invokes_bedrock_with_correct_parameters(self, mock_get_client):
        """Bedrock Converse API is called with correct model and message structure."""
        llm_output = '{"RISK": "Low", "SCORE": 100, "high_risk_indicator": [], "explanation": "OK.", "suggestion": "None."}'
        mock_client = MagicMock()
        mock_client.converse.return_value = _mock_bedrock_response(llm_output)
        mock_get_client.return_value = mock_client

        state = _make_state()
        compliance_evaluation(state)

        mock_client.converse.assert_called_once()
        call_kwargs = mock_client.converse.call_args[1]
        assert "modelId" in call_kwargs
        assert call_kwargs["messages"][0]["role"] == "user"
        assert "text" in call_kwargs["messages"][0]["content"][0]
        assert call_kwargs["inferenceConfig"]["temperature"] == 0.0

    @patch("culture_compliance.nodes.step6_compliance_evaluation._get_bedrock_client")
    def test_handles_high_risk_response(self, mock_get_client):
        """LLM returns high risk result with indicators."""
        llm_output = '{"RISK": "High", "SCORE": 25, "high_risk_indicator": ["Religious insensitivity detected", "Offensive language"], "explanation": "Content contains religious insensitivity.", "suggestion": "Remove offensive references."}'
        mock_client = MagicMock()
        mock_client.converse.return_value = _mock_bedrock_response(llm_output)
        mock_get_client.return_value = mock_client

        state = _make_state(content="offensive content here")
        result = compliance_evaluation(state)

        assert result.raw_llm_output["RISK"] == "High"
        assert result.raw_llm_output["SCORE"] == 25
        assert len(result.raw_llm_output["high_risk_indicator"]) == 2
        assert result.errors == []

    @patch("culture_compliance.nodes.step6_compliance_evaluation._get_bedrock_client")
    def test_handles_json_in_markdown_code_block(self, mock_get_client):
        """LLM wraps JSON in markdown code block — still parsed correctly."""
        llm_output = '```json\n{"RISK": "Low", "SCORE": 90, "high_risk_indicator": [], "explanation": "Fine.", "suggestion": "None."}\n```'
        mock_client = MagicMock()
        mock_client.converse.return_value = _mock_bedrock_response(llm_output)
        mock_get_client.return_value = mock_client

        state = _make_state()
        result = compliance_evaluation(state)

        assert result.raw_llm_output is not None
        assert result.raw_llm_output["SCORE"] == 90
        assert result.errors == []

    @patch("culture_compliance.nodes.step6_compliance_evaluation._get_bedrock_client")
    def test_uses_separate_regulatory_and_cultural_guidelines(self, mock_get_client):
        """When regulatory_guidelines and cultural_guidelines are set, prompt uses labeled sections."""
        llm_output = '{"RISK": "Low", "SCORE": 95, "high_risk_indicator": [], "explanation": "OK.", "suggestion": "None."}'
        mock_client = MagicMock()
        mock_client.converse.return_value = _mock_bedrock_response(llm_output)
        mock_get_client.return_value = mock_client

        state = _make_state(retrieved_guidelines=None)
        state.regulatory_guidelines = "[R1] Regulatory rule about halal"
        state.cultural_guidelines = "[C1] Cultural rule about aurat"

        result = compliance_evaluation(state)

        assert result.errors == []
        assert result.raw_llm_output is not None
        # Verify the prompt sent to Bedrock contains labeled sections
        call_kwargs = mock_client.converse.call_args[1]
        prompt_text = call_kwargs["messages"][0]["content"][0]["text"]
        assert "=== REGULATORY GUIDELINES ===" in prompt_text
        assert "=== CULTURAL GUIDELINES ===" in prompt_text
        assert "[R1] Regulatory rule about halal" in prompt_text
        assert "[C1] Cultural rule about aurat" in prompt_text
        assert "guideline_source" in prompt_text

    @patch("culture_compliance.nodes.step6_compliance_evaluation._get_bedrock_client")
    def test_falls_back_to_retrieved_guidelines_when_separate_not_set(self, mock_get_client):
        """When only retrieved_guidelines is set (legacy), it is used as fallback."""
        llm_output = '{"RISK": "Low", "SCORE": 95, "high_risk_indicator": [], "explanation": "OK.", "suggestion": "None."}'
        mock_client = MagicMock()
        mock_client.converse.return_value = _mock_bedrock_response(llm_output)
        mock_get_client.return_value = mock_client

        state = _make_state(
            retrieved_guidelines="=== REGULATORY GUIDELINES ===\n[R1] Some rule\n\n=== CULTURAL GUIDELINES ===\n[C1] Some cultural rule"
        )
        # regulatory_guidelines and cultural_guidelines remain None (default)

        result = compliance_evaluation(state)

        assert result.errors == []
        assert result.raw_llm_output is not None


class TestComplianceEvaluationErrors:
    """Tests for error handling in compliance evaluation."""

    def test_error_when_no_unified_content(self):
        """Returns validation error when unified_content is not set."""
        state = _make_state()
        state.unified_content = None

        result = compliance_evaluation(state)

        assert len(result.errors) == 1
        assert result.errors[0]["node"] == "compliance_evaluation"
        assert result.errors[0]["error_type"] == "validation"
        assert "content" in result.errors[0]["message"].lower()
        assert result.raw_llm_output is None

    def test_error_when_no_guidelines(self):
        """Returns validation error when retrieved_guidelines is not set."""
        state = _make_state()
        state.retrieved_guidelines = None

        result = compliance_evaluation(state)

        assert len(result.errors) == 1
        assert result.errors[0]["node"] == "compliance_evaluation"
        assert result.errors[0]["error_type"] == "validation"
        assert "guidelines" in result.errors[0]["message"].lower()
        assert result.raw_llm_output is None

    @patch("culture_compliance.nodes.step6_compliance_evaluation._get_bedrock_client")
    def test_error_when_bedrock_client_error(self, mock_get_client):
        """Returns service_unavailable error when Bedrock raises ClientError."""
        from botocore.exceptions import ClientError

        mock_client = MagicMock()
        mock_client.converse.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "Converse",
        )
        mock_get_client.return_value = mock_client

        state = _make_state()
        result = compliance_evaluation(state)

        assert len(result.errors) == 1
        assert result.errors[0]["node"] == "compliance_evaluation"
        assert result.errors[0]["error_type"] == "service_unavailable"
        assert "failed" in result.errors[0]["message"].lower()
        assert result.raw_llm_output is None

    @patch("culture_compliance.nodes.step6_compliance_evaluation._get_bedrock_client")
    def test_error_when_bedrock_connection_fails(self, mock_get_client):
        """Returns error when Bedrock connection fails entirely."""
        mock_client = MagicMock()
        mock_client.converse.side_effect = Exception("Connection timeout")
        mock_get_client.return_value = mock_client

        state = _make_state()
        result = compliance_evaluation(state)

        assert len(result.errors) == 1
        assert result.errors[0]["error_type"] == "service_unavailable"
        assert result.raw_llm_output is None

    @patch("culture_compliance.nodes.step6_compliance_evaluation._get_bedrock_client")
    def test_error_when_llm_returns_unparseable_response(self, mock_get_client):
        """Returns parse_error when LLM output is not valid JSON."""
        mock_client = MagicMock()
        mock_client.converse.return_value = _mock_bedrock_response(
            "I cannot evaluate this content because it is inappropriate."
        )
        mock_get_client.return_value = mock_client

        state = _make_state()
        result = compliance_evaluation(state)

        assert len(result.errors) == 1
        assert result.errors[0]["node"] == "compliance_evaluation"
        assert result.errors[0]["error_type"] == "parse_error"
        assert "unparseable" in result.errors[0]["message"].lower()
        assert result.raw_llm_output is None

    @patch("culture_compliance.nodes.step6_compliance_evaluation._get_bedrock_client")
    def test_error_when_llm_returns_empty_response(self, mock_get_client):
        """Returns parse_error when LLM output is empty."""
        mock_client = MagicMock()
        mock_client.converse.return_value = _mock_bedrock_response("")
        mock_get_client.return_value = mock_client

        state = _make_state()
        result = compliance_evaluation(state)

        assert len(result.errors) == 1
        assert result.errors[0]["error_type"] == "parse_error"
        assert result.raw_llm_output is None


class TestParseLlmJson:
    """Tests for the _parse_llm_json helper function."""

    def test_parses_valid_json(self):
        result = _parse_llm_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parses_json_in_markdown_block(self):
        result = _parse_llm_json('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_parses_json_embedded_in_text(self):
        result = _parse_llm_json('Here is the result: {"key": "value"} end.')
        assert result == {"key": "value"}

    def test_returns_none_for_empty_string(self):
        result = _parse_llm_json("")
        assert result is None

    def test_returns_none_for_whitespace_only(self):
        result = _parse_llm_json("   \n\t  ")
        assert result is None

    def test_returns_none_for_non_json_text(self):
        result = _parse_llm_json("This is just plain text with no JSON.")
        assert result is None


class TestBuildPrompt:
    """Tests for the _build_prompt helper function."""

    def test_injects_content_and_guidelines_via_fallback(self):
        """Fallback combined guidelines string is injected into the prompt."""
        prompt = _build_prompt(
            content="Test ad copy",
            content_type="text",
            market="malaysia",
            guidelines="[1] Guideline about ads",
        )
        assert "Test ad copy" in prompt
        assert "[1] Guideline about ads" in prompt

    def test_injects_separate_regulatory_and_cultural_guidelines(self):
        """Separate regulatory and cultural guidelines appear in labeled sections."""
        prompt = _build_prompt(
            content="Test ad copy",
            content_type="text",
            market="malaysia",
            regulatory_guidelines="[R1] Regulatory rule about halal",
            cultural_guidelines="[C1] Cultural rule about aurat",
        )
        assert "Test ad copy" in prompt
        assert "=== REGULATORY GUIDELINES ===" in prompt
        assert "=== CULTURAL GUIDELINES ===" in prompt
        assert "[R1] Regulatory rule about halal" in prompt
        assert "[C1] Cultural rule about aurat" in prompt

    def test_regulatory_only_shows_no_cultural_placeholder(self):
        """When only regulatory_guidelines is provided, cultural section shows placeholder."""
        prompt = _build_prompt(
            content="content",
            content_type="text",
            market="malaysia",
            regulatory_guidelines="[R1] Some regulatory rule",
        )
        assert "=== REGULATORY GUIDELINES ===" in prompt
        assert "=== CULTURAL GUIDELINES ===" in prompt
        assert "No relevant cultural guidelines found." in prompt

    def test_cultural_only_shows_no_regulatory_placeholder(self):
        """When only cultural_guidelines is provided, regulatory section shows placeholder."""
        prompt = _build_prompt(
            content="content",
            content_type="text",
            market="malaysia",
            cultural_guidelines="[C1] Some cultural rule",
        )
        assert "=== REGULATORY GUIDELINES ===" in prompt
        assert "No relevant regulatory guidelines found." in prompt
        assert "[C1] Some cultural rule" in prompt

    def test_prompt_includes_guideline_source_instruction(self):
        """Prompt instructs LLM to tag each violation with guideline_source."""
        prompt = _build_prompt(
            content="content",
            content_type="text",
            market="malaysia",
            regulatory_guidelines="reg",
            cultural_guidelines="cult",
        )
        assert "guideline_source" in prompt
        assert '"regulatory"' in prompt
        assert '"cultural"' in prompt

    def test_prompt_includes_cultural_severity_mapping(self):
        """Prompt includes the cultural severity → compliance severity mapping."""
        prompt = _build_prompt(
            content="content",
            content_type="text",
            market="malaysia",
            regulatory_guidelines="reg",
            cultural_guidelines="cult",
        )
        assert "CULTURAL SEVERITY MAPPING" in prompt
        assert "Severe" in prompt
        assert "Moderate" in prompt
        assert "Minor" in prompt

    def test_uses_text_prompt_template(self):
        prompt = _build_prompt(
            content="content",
            content_type="text",
            market="malaysia",
            guidelines="guidelines",
        )
        assert "Cultural Appropriateness Evaluator" in prompt

    def test_uses_image_prompt_template(self):
        prompt = _build_prompt(
            content="image description",
            content_type="image",
            market="malaysia",
            guidelines="guidelines",
        )
        assert "image" in prompt.lower()

    def test_falls_back_to_text_for_unknown_type(self):
        prompt = _build_prompt(
            content="content",
            content_type="unknown",
            market="malaysia",
            guidelines="guidelines",
        )
        # Should not crash, falls back to video/else branch
        assert "Cultural Appropriateness Evaluator" in prompt
