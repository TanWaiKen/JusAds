"""Unit tests for the pipeline orchestrator.

Tests graph structure, conditional routing, retry logic, timeout handling,
and stateless invocation of the LangGraph pipeline.

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6
"""

import time
from unittest.mock import patch, MagicMock

import pytest

from culture_compliance.models.schemas import (
    ContentSubmission,
    ContentType,
    Market,
    PipelineState,
)
from culture_compliance.orchestrator import (
    RETRY_CONFIG,
    _is_transient_error,
    _route_after_content_routing,
    _route_after_processing,
    _route_after_market_resolution,
    _route_after_guideline_retrieval,
    _route_after_compliance_evaluation,
    _with_retry,
    create_pipeline,
    run_pipeline,
)


# --- Helpers ---


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
        "pipeline_start_ms": int(time.time() * 1000),
    }
    defaults.update(overrides)
    return PipelineState(**defaults)


# --- Test Graph Structure (Requirement 7.1) ---


class TestGraphStructure:
    """Tests that the graph contains the correct nodes and edges."""

    def test_pipeline_has_content_routing_node(self):
        """Graph should contain a content_routing node."""
        pipeline = create_pipeline()
        graph = pipeline.get_graph()
        assert "content_routing" in graph.nodes

    def test_pipeline_has_text_processing_node(self):
        """Graph should contain a text_processing node."""
        pipeline = create_pipeline()
        graph = pipeline.get_graph()
        assert "text_processing" in graph.nodes

    def test_pipeline_has_image_processing_node(self):
        """Graph should contain an image_processing node."""
        pipeline = create_pipeline()
        graph = pipeline.get_graph()
        assert "image_processing" in graph.nodes

    def test_pipeline_has_video_processing_node(self):
        """Graph should contain a video_processing node."""
        pipeline = create_pipeline()
        graph = pipeline.get_graph()
        assert "video_processing" in graph.nodes

    def test_pipeline_has_market_resolution_node(self):
        """Graph should contain a market_resolution node."""
        pipeline = create_pipeline()
        graph = pipeline.get_graph()
        assert "market_resolution" in graph.nodes

    def test_pipeline_has_guideline_retrieval_node(self):
        """Graph should contain a guideline_retrieval node."""
        pipeline = create_pipeline()
        graph = pipeline.get_graph()
        assert "guideline_retrieval" in graph.nodes

    def test_pipeline_has_compliance_evaluation_node(self):
        """Graph should contain a compliance_evaluation node."""
        pipeline = create_pipeline()
        graph = pipeline.get_graph()
        assert "compliance_evaluation" in graph.nodes

    def test_pipeline_has_result_formatting_node(self):
        """Graph should contain a result_formatting node."""
        pipeline = create_pipeline()
        graph = pipeline.get_graph()
        assert "result_formatting" in graph.nodes

    def test_pipeline_has_error_handler_node(self):
        """Graph should contain an error_handler node."""
        pipeline = create_pipeline()
        graph = pipeline.get_graph()
        assert "error_handler" in graph.nodes

    def test_pipeline_entry_point_is_content_routing(self):
        """Graph entry point should be content_routing (first node after __start__)."""
        pipeline = create_pipeline()
        graph = pipeline.get_graph()
        # Find the edge from __start__ to determine the entry point
        entry_edges = [
            edge for edge in graph.edges
            if edge.source == "__start__"
        ]
        assert len(entry_edges) == 1
        assert entry_edges[0].target == "content_routing"

    def test_pipeline_has_all_required_nodes(self):
        """Graph should contain all required nodes per Requirement 7.1."""
        pipeline = create_pipeline()
        graph = pipeline.get_graph()
        node_names = set(graph.nodes.keys())

        required_nodes = {
            "content_routing",
            "text_processing",
            "image_processing",
            "video_processing",
            "market_resolution",
            "guideline_retrieval",
            "compliance_evaluation",
            "result_formatting",
            "error_handler",
        }
        # All required nodes should be present (graph may also have __start__, __end__)
        assert required_nodes.issubset(node_names)


# --- Test Conditional Routing (Requirement 7.5) ---


class TestConditionalRouting:
    """Tests for conditional routing based on content_type."""

    def test_route_text_content_to_text_processing(self):
        """Text content should route to text_processing node."""
        state = _make_state(content_type=ContentType.TEXT)
        result = _route_after_content_routing(state)
        assert result == "text_processing"

    def test_route_image_content_to_image_processing(self):
        """Image content should route to image_processing node."""
        state = _make_state(
            content_type=ContentType.IMAGE,
            submission=ContentSubmission(
                content="base64imagedata",
                content_type=ContentType.IMAGE,
                market=Market.MALAYSIA,
            ),
        )
        result = _route_after_content_routing(state)
        assert result == "image_processing"

    def test_route_video_content_to_video_processing(self):
        """Video content should route to video_processing node."""
        state = _make_state(
            content_type=ContentType.VIDEO,
            submission=ContentSubmission(
                content="s3://bucket/video.mp4",
                content_type=ContentType.VIDEO,
                market=Market.MALAYSIA,
            ),
        )
        result = _route_after_content_routing(state)
        assert result == "video_processing"

    def test_route_to_error_handler_when_errors_present(self):
        """Should route to error_handler when state has errors."""
        state = _make_state(
            errors=[{"error_type": "validation", "message": "Invalid input"}]
        )
        result = _route_after_content_routing(state)
        assert result == "error_handler"

    def test_route_after_processing_to_market_resolution(self):
        """After processing, should route to market_resolution when no errors."""
        state = _make_state()
        result = _route_after_processing(state)
        assert result == "market_resolution"

    def test_route_after_processing_to_error_handler_on_error(self):
        """After processing, should route to error_handler when errors present."""
        state = _make_state(
            errors=[{"error_type": "service_unavailable", "message": "Vision failed"}]
        )
        result = _route_after_processing(state)
        assert result == "error_handler"

    def test_route_after_market_resolution_to_guideline_retrieval(self):
        """After market resolution, should route to guideline_retrieval."""
        state = _make_state()
        result = _route_after_market_resolution(state)
        assert result == "guideline_retrieval"

    def test_route_after_market_resolution_to_error_handler_on_error(self):
        """After market resolution, should route to error_handler on error."""
        state = _make_state(
            errors=[{"error_type": "validation", "message": "Invalid market"}]
        )
        result = _route_after_market_resolution(state)
        assert result == "error_handler"

    def test_route_after_guideline_retrieval_to_compliance_evaluation(self):
        """After guideline retrieval, should route to compliance_evaluation."""
        state = _make_state()
        result = _route_after_guideline_retrieval(state)
        assert result == "compliance_evaluation"

    def test_route_after_guideline_retrieval_to_error_handler_on_error(self):
        """After guideline retrieval, should route to error_handler on error."""
        state = _make_state(
            errors=[{"error_type": "service_unavailable", "message": "Qdrant down"}]
        )
        result = _route_after_guideline_retrieval(state)
        assert result == "error_handler"

    def test_route_after_compliance_evaluation_to_result_formatting(self):
        """After compliance evaluation, should route to result_formatting."""
        state = _make_state()
        result = _route_after_compliance_evaluation(state)
        assert result == "result_formatting"

    def test_route_after_compliance_evaluation_to_error_handler_on_error(self):
        """After compliance evaluation, should route to error_handler on error."""
        state = _make_state(
            errors=[{"error_type": "parse_error", "message": "LLM returned garbage"}]
        )
        result = _route_after_compliance_evaluation(state)
        assert result == "error_handler"


# --- Test Retry Logic (Requirement 7.4) ---


class TestRetryLogic:
    """Tests for retry logic with exponential backoff."""

    def test_is_transient_error_throttling(self):
        """ThrottlingException should be identified as transient."""
        error = {"message": "ThrottlingException: Rate exceeded", "error_type": ""}
        assert _is_transient_error(error) is True

    def test_is_transient_error_service_unavailable(self):
        """ServiceUnavailableException should be identified as transient."""
        error = {"message": "", "error_type": "ServiceUnavailableException"}
        assert _is_transient_error(error) is True

    def test_is_transient_error_connection_error(self):
        """ConnectionError should be identified as transient."""
        error = {"message": "ConnectionError: Failed to connect", "error_type": ""}
        assert _is_transient_error(error) is True

    def test_is_transient_error_timeout(self):
        """TimeoutError should be identified as transient."""
        error = {"message": "TimeoutError: Request timed out", "error_type": ""}
        assert _is_transient_error(error) is True

    def test_is_not_transient_error_validation(self):
        """Validation errors should not be identified as transient."""
        error = {"message": "Content is empty", "error_type": "validation"}
        assert _is_transient_error(error) is False

    def test_is_not_transient_error_parse(self):
        """Parse errors should not be identified as transient."""
        error = {"message": "Invalid JSON response", "error_type": "parse_error"}
        assert _is_transient_error(error) is False

    @patch("culture_compliance.orchestrator.time.sleep")
    def test_retry_succeeds_on_second_attempt(self, mock_sleep):
        """Node should succeed after transient error on first attempt."""
        call_count = [0]

        def flaky_node(state: PipelineState) -> PipelineState:
            call_count[0] += 1
            if call_count[0] == 1:
                # First call: add transient error
                state.errors.append({
                    "message": "ThrottlingException: Rate exceeded",
                    "error_type": "ThrottlingException",
                })
            # Second call: succeed (no error added)
            return state

        wrapped = _with_retry(flaky_node)
        state = _make_state()
        result = wrapped(state)

        assert call_count[0] == 2
        assert len(result.errors) == 0
        mock_sleep.assert_called_once()

    @patch("culture_compliance.orchestrator.time.sleep")
    def test_retry_exhausts_max_retries(self, mock_sleep):
        """Node should stop retrying after max_retries attempts."""
        call_count = [0]

        def always_failing_node(state: PipelineState) -> PipelineState:
            call_count[0] += 1
            state.errors.append({
                "message": "ConnectionError: Cannot connect",
                "error_type": "ConnectionError",
            })
            return state

        wrapped = _with_retry(always_failing_node)
        state = _make_state()
        result = wrapped(state)

        # Should be called max_retries + 1 times (initial + 2 retries)
        assert call_count[0] == RETRY_CONFIG["max_retries"] + 1
        # Final error should remain in state
        assert len(result.errors) > 0
        assert mock_sleep.call_count == RETRY_CONFIG["max_retries"]

    @patch("culture_compliance.orchestrator.time.sleep")
    def test_retry_uses_exponential_backoff(self, mock_sleep):
        """Retry delays should follow exponential backoff pattern."""
        def always_failing_node(state: PipelineState) -> PipelineState:
            state.errors.append({
                "message": "TimeoutError: Request timed out",
                "error_type": "TimeoutError",
            })
            return state

        wrapped = _with_retry(always_failing_node)
        state = _make_state()
        wrapped(state)

        # Verify backoff delays: base * multiplier^attempt
        base = RETRY_CONFIG["base_delay_seconds"]
        multiplier = RETRY_CONFIG["backoff_multiplier"]
        expected_delays = [base * (multiplier ** i) for i in range(RETRY_CONFIG["max_retries"])]

        actual_delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert actual_delays == expected_delays

    @patch("culture_compliance.orchestrator.time.sleep")
    def test_no_retry_for_non_transient_error(self, mock_sleep):
        """Non-transient errors should not trigger retries."""
        call_count = [0]

        def validation_error_node(state: PipelineState) -> PipelineState:
            call_count[0] += 1
            state.errors.append({
                "message": "Content is empty",
                "error_type": "validation",
            })
            return state

        wrapped = _with_retry(validation_error_node)
        state = _make_state()
        result = wrapped(state)

        # Should only be called once (no retries for non-transient errors)
        assert call_count[0] == 1
        assert len(result.errors) == 1
        mock_sleep.assert_not_called()

    @patch("culture_compliance.orchestrator.time.sleep")
    def test_no_retry_when_no_errors(self, mock_sleep):
        """Successful nodes should not trigger retries."""
        call_count = [0]

        def successful_node(state: PipelineState) -> PipelineState:
            call_count[0] += 1
            return state

        wrapped = _with_retry(successful_node)
        state = _make_state()
        result = wrapped(state)

        assert call_count[0] == 1
        assert len(result.errors) == 0
        mock_sleep.assert_not_called()

    def test_retry_config_max_retries_is_two(self):
        """Retry config should specify max 2 retries."""
        assert RETRY_CONFIG["max_retries"] == 2

    def test_retry_config_has_expected_retryable_errors(self):
        """Retry config should include expected transient error types."""
        expected = {
            "ThrottlingException",
            "ServiceUnavailableException",
            "ConnectionError",
            "TimeoutError",
        }
        assert set(RETRY_CONFIG["retryable_errors"]) == expected

    @patch("culture_compliance.orchestrator.time.sleep")
    def test_retry_preserves_function_name(self, mock_sleep):
        """Wrapped function should preserve the original function name."""
        def my_custom_node(state: PipelineState) -> PipelineState:
            return state

        wrapped = _with_retry(my_custom_node)
        assert wrapped.__name__ == "my_custom_node"


# --- Test Timeout Handling (Requirement 7.6) ---


class TestTimeoutHandling:
    """Tests for pipeline timeout handling."""

    @patch("culture_compliance.orchestrator.time.sleep")
    def test_timeout_error_propagates_through_retry(self, mock_sleep):
        """TimeoutError should be retried as it's a transient error."""
        call_count = [0]

        def timeout_node(state: PipelineState) -> PipelineState:
            call_count[0] += 1
            state.errors.append({
                "message": "TimeoutError: Request timed out",
                "error_type": "TimeoutError",
            })
            return state

        wrapped = _with_retry(timeout_node)
        state = _make_state()
        result = wrapped(state)

        # TimeoutError is retryable, so it should retry max_retries times
        assert call_count[0] == RETRY_CONFIG["max_retries"] + 1

    def test_is_transient_error_case_insensitive(self):
        """Transient error detection should be case-insensitive."""
        error = {"message": "timeouterror: something", "error_type": ""}
        assert _is_transient_error(error) is True

    def test_is_transient_error_in_error_type_field(self):
        """Transient error detection should check error_type field."""
        error = {"message": "", "error_type": "connectionerror"}
        assert _is_transient_error(error) is True


# --- Test Stateless Invocation (Requirement 7.6) ---


class TestStatelessInvocation:
    """Tests that the pipeline is stateless between invocations."""

    def test_create_pipeline_returns_new_instance_each_call(self):
        """Each call to create_pipeline should return a new graph instance."""
        pipeline1 = create_pipeline()
        pipeline2 = create_pipeline()
        assert pipeline1 is not pipeline2

    @patch("culture_compliance.orchestrator.create_pipeline")
    def test_run_pipeline_creates_new_graph_per_invocation(self, mock_create):
        """run_pipeline should create a new graph for each invocation."""
        # Set up mock pipeline that returns a result
        mock_compiled = MagicMock()
        mock_compiled.invoke.return_value = {
            "compliance_result": {
                "content_type": "text",
                "market": "malaysia",
                "risk_level": "Low",
                "score": 100,
                "high_risk_indicators": [],
                "explanation": "No issues found.",
                "suggestion": "Content is compliant.",
                "processing_metadata": {
                    "pipeline_duration_ms": 100,
                    "models_used": [],
                    "market": "malaysia",
                },
                "warnings": [],
            }
        }
        mock_create.return_value = mock_compiled

        submission = ContentSubmission(
            content="Test content",
            content_type=ContentType.TEXT,
            market=Market.MALAYSIA,
        )

        # Call run_pipeline twice
        run_pipeline(submission)
        run_pipeline(submission)

        # create_pipeline should be called once per invocation
        assert mock_create.call_count == 2

    @patch("culture_compliance.orchestrator.create_pipeline")
    def test_run_pipeline_initializes_state_from_submission(self, mock_create):
        """run_pipeline should initialize state from the submission."""
        mock_compiled = MagicMock()
        mock_compiled.invoke.return_value = {
            "compliance_result": {
                "content_type": "text",
                "market": "singapore",
                "risk_level": "Low",
                "score": 95,
                "high_risk_indicators": [],
                "explanation": "Clean content.",
                "suggestion": "No changes needed.",
                "processing_metadata": {
                    "pipeline_duration_ms": 50,
                    "models_used": [],
                    "market": "singapore",
                },
                "warnings": [],
            }
        }
        mock_create.return_value = mock_compiled

        submission = ContentSubmission(
            content="Singapore ad content",
            content_type=ContentType.TEXT,
            market=Market.SINGAPORE,
        )

        run_pipeline(submission)

        # Verify the state passed to invoke
        invoke_call = mock_compiled.invoke.call_args[0][0]
        assert invoke_call.content_type == ContentType.TEXT
        assert invoke_call.market == Market.SINGAPORE
        assert invoke_call.submission == submission
        assert invoke_call.pipeline_start_ms is not None
        # Cultural targeting fields should be propagated from submission
        assert invoke_call.target_ethnicity == submission.target_ethnicity
        assert invoke_call.target_age_group == submission.target_age_group

    @patch("culture_compliance.orchestrator.create_pipeline")
    def test_run_pipeline_passes_cultural_targeting_fields(self, mock_create):
        """run_pipeline should pass target_ethnicity and target_age_group into initial state."""
        mock_compiled = MagicMock()
        mock_compiled.invoke.return_value = {
            "compliance_result": {
                "content_type": "text",
                "market": "malaysia",
                "risk_level": "Low",
                "score": 90,
                "high_risk_indicators": [],
                "explanation": "Clean content.",
                "suggestion": "No changes needed.",
                "processing_metadata": {
                    "pipeline_duration_ms": 50,
                    "models_used": [],
                    "market": "malaysia",
                },
                "warnings": [],
            }
        }
        mock_create.return_value = mock_compiled

        submission = ContentSubmission(
            content="Malay ad content",
            content_type=ContentType.TEXT,
            market=Market.MALAYSIA,
            target_ethnicity="malay",
            target_age_group="adults_only",
        )

        run_pipeline(submission)

        invoke_call = mock_compiled.invoke.call_args[0][0]
        assert invoke_call.target_ethnicity == "malay"
        assert invoke_call.target_age_group == "adults_only"

    @patch("culture_compliance.orchestrator.create_pipeline")
    def test_run_pipeline_returns_compliance_result(self, mock_create):
        """run_pipeline should return the compliance_result from final state."""
        expected_result = {
            "content_type": "text",
            "market": "malaysia",
            "risk_level": "Medium",
            "score": 60,
            "high_risk_indicators": [],
            "explanation": "Some issues found.",
            "suggestion": "Review flagged content.",
            "processing_metadata": {
                "pipeline_duration_ms": 200,
                "models_used": ["amazon.nova-pro-v1:0"],
                "market": "malaysia",
            },
            "warnings": [],
        }
        mock_compiled = MagicMock()
        mock_compiled.invoke.return_value = {"compliance_result": expected_result}
        mock_create.return_value = mock_compiled

        submission = ContentSubmission(
            content="Test content",
            content_type=ContentType.TEXT,
            market=Market.MALAYSIA,
        )

        result = run_pipeline(submission)
        assert result == expected_result

    @patch("culture_compliance.orchestrator.create_pipeline")
    def test_run_pipeline_handles_none_compliance_result(self, mock_create):
        """run_pipeline should return fallback result when compliance_result is None."""
        mock_compiled = MagicMock()
        mock_compiled.invoke.return_value = {"compliance_result": None}
        mock_create.return_value = mock_compiled

        submission = ContentSubmission(
            content="Test content",
            content_type=ContentType.TEXT,
            market=Market.MALAYSIA,
        )

        result = run_pipeline(submission)

        # Should return a fallback error result
        assert result is not None
        assert result["risk_level"] == "High"
        assert result["score"] == 0
        assert "internal error" in result["explanation"].lower()


# --- Test Pipeline State (Requirement 7.2) ---


class TestPipelineState:
    """Tests that pipeline state is correctly maintained."""

    def test_initial_state_has_empty_errors(self):
        """Initial pipeline state should have empty errors list."""
        state = _make_state()
        assert state.errors == []

    def test_initial_state_has_empty_warnings(self):
        """Initial pipeline state should have empty warnings list."""
        state = _make_state()
        assert state.warnings == []

    def test_initial_state_has_empty_models_used(self):
        """Initial pipeline state should have empty models_used list."""
        state = _make_state()
        assert state.models_used == []

    def test_state_preserves_submission(self):
        """Pipeline state should preserve the original submission."""
        submission = ContentSubmission(
            content="My ad content",
            content_type=ContentType.IMAGE,
            market=Market.SINGAPORE,
        )
        state = _make_state(
            submission=submission,
            content_type=ContentType.IMAGE,
            market=Market.SINGAPORE,
        )
        assert state.submission == submission
        assert state.content_type == ContentType.IMAGE
        assert state.market == Market.SINGAPORE

    def test_state_tracks_intermediate_results(self):
        """Pipeline state should track intermediate processing results."""
        state = _make_state(
            unified_content="Processed text content",
            retrieved_guidelines="Guideline 1\nGuideline 2",
        )
        assert state.unified_content == "Processed text content"
        assert state.retrieved_guidelines == "Guideline 1\nGuideline 2"
