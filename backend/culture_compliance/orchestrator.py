"""Pipeline orchestrator for the content compliance system.

Builds and executes a LangGraph StateGraph that routes content through
the appropriate processing pipeline (text, image, or video), retrieves
market-specific guidelines, evaluates compliance, and formats results.

Implements retry logic with exponential backoff for transient errors and
ensures stateless design (new graph instance per invocation) for Lambda
compatibility.

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6
"""

import logging
import time
from typing import Any

from langgraph.graph import END, StateGraph

from culture_compliance.models.schemas import (
    ComplianceResult,
    ContentSubmission,
    ContentType,
    PipelineState,
)
from culture_compliance.nodes.step1_routing import (
    content_routing,
    market_resolution,
)
from culture_compliance.nodes.step2_video_analysis import video_processing
from culture_compliance.nodes.step3_image_analysis import image_processing
from culture_compliance.nodes.step4_text_analysis import text_processing
from culture_compliance.nodes.step5_guideline_retrieval import (
    guideline_retrieval,
)
from culture_compliance.nodes.step6_compliance_evaluation import (
    compliance_evaluation,
)
from culture_compliance.nodes.step7_result_formatting import (
    error_handler,
    result_formatting,
)

logger = logging.getLogger(__name__)

# --- Retry Configuration ---

RETRY_CONFIG = {
    "max_retries": 2,
    "base_delay_seconds": 1.0,
    "backoff_multiplier": 2.0,
    "retryable_errors": [
        "ThrottlingException",
        "ServiceUnavailableException",
        "ConnectionError",
        "TimeoutError",
    ],
}


def _is_transient_error(error: dict) -> bool:
    """Check if an error is a transient/retryable error.

    Args:
        error: Error dict from pipeline state with 'message' and/or
            'error_type' fields.

    Returns:
        True if the error matches a retryable error pattern.
    """
    message = error.get("message", "")
    error_type = error.get("error_type", "")

    for retryable in RETRY_CONFIG["retryable_errors"]:
        if retryable.lower() in message.lower():
            return True
        if retryable.lower() in error_type.lower():
            return True

    return False


def _with_retry(node_fn):
    """Wrap a node function with retry logic for transient errors.

    Implements exponential backoff with max 2 retries. Only retries
    when the node appends errors that match the retryable error patterns.

    Args:
        node_fn: The node function to wrap. Must accept and return PipelineState.

    Returns:
        A wrapped function with retry logic.
    """

    def wrapper(state: PipelineState) -> PipelineState:
        max_retries = RETRY_CONFIG["max_retries"]
        base_delay = RETRY_CONFIG["base_delay_seconds"]
        multiplier = RETRY_CONFIG["backoff_multiplier"]

        for attempt in range(max_retries + 1):
            # Track errors before this attempt
            errors_before = len(state.errors)

            # Execute the node
            state = node_fn(state)

            # Check if new errors were added
            new_errors = state.errors[errors_before:]

            if not new_errors:
                # No errors — success
                return state

            # Check if the new errors are transient
            transient_errors = [e for e in new_errors if _is_transient_error(e)]

            if not transient_errors:
                # Non-transient error — don't retry
                return state

            if attempt < max_retries:
                # Remove the transient errors for retry
                state.errors = state.errors[:errors_before]

                # Calculate backoff delay
                delay = base_delay * (multiplier ** attempt)
                logger.warning(
                    "Transient error in %s (attempt %d/%d). "
                    "Retrying in %.1f seconds...",
                    node_fn.__name__,
                    attempt + 1,
                    max_retries + 1,
                    delay,
                )
                time.sleep(delay)
            else:
                # Max retries exhausted
                logger.error(
                    "Max retries (%d) exhausted for %s. "
                    "Proceeding with error.",
                    max_retries,
                    node_fn.__name__,
                )

        return state

    # Preserve the original function name for LangGraph node naming
    wrapper.__name__ = node_fn.__name__
    wrapper.__qualname__ = node_fn.__qualname__
    return wrapper


# --- Routing Functions ---

def _route_after_content_routing(state: PipelineState) -> str:
    """Determine the next node after content routing.

    Routes based on content_type:
    - Video (v3): goes to market_resolution first (guidelines needed before video analysis)
    - Text/Image: goes to their respective processing nodes

    Args:
        state: The current pipeline state.

    Returns:
        The name of the next node to execute.
    """
    if state.errors:
        return "error_handler"

    content_type = state.content_type
    if content_type == ContentType.TEXT:
        return "text_processing"
    elif content_type == ContentType.IMAGE:
        return "image_processing"
    elif content_type == ContentType.VIDEO:
        # v3: video goes to market_resolution first so guidelines/persona
        # are available when video_processing runs
        return "market_resolution"
    else:
        return "error_handler"


def _route_after_processing(state: PipelineState) -> str:
    """Determine the next node after content processing (text/image only).

    Routes to market_resolution if processing succeeded, or to
    error_handler if errors occurred.

    Args:
        state: The current pipeline state.

    Returns:
        The name of the next node to execute.
    """
    if state.errors:
        return "error_handler"
    return "market_resolution"


def _route_after_market_resolution(state: PipelineState) -> str:
    """Determine the next node after market resolution.

    Routes to guideline_retrieval if market resolution succeeded, or to
    error_handler if errors occurred.

    Args:
        state: The current pipeline state.

    Returns:
        The name of the next node to execute.
    """
    if state.errors:
        return "error_handler"
    return "guideline_retrieval"


def _route_after_guideline_retrieval(state: PipelineState) -> str:
    """Determine the next node after guideline retrieval.

    Routes based on content type:
    - Video: goes to video_processing (v3 single-model path)
    - Text/Image: goes to compliance_evaluation (v2 path)

    Args:
        state: The current pipeline state.

    Returns:
        The name of the next node to execute.
    """
    if state.errors:
        return "error_handler"

    if state.content_type == ContentType.VIDEO:
        return "video_processing"
    return "compliance_evaluation"


def _route_after_video_processing(state: PipelineState) -> str:
    """Determine the next node after video processing.

    In v3, video_processing produces the final compliance JSON directly,
    so it routes straight to result_formatting (skipping step6).

    Args:
        state: The current pipeline state.

    Returns:
        The name of the next node to execute.
    """
    if state.errors:
        return "error_handler"
    return "result_formatting"


def _route_after_compliance_evaluation(state: PipelineState) -> str:
    """Determine the next node after compliance evaluation (text/image only).

    Routes to result_formatting if evaluation succeeded, or to
    error_handler if errors occurred.

    Args:
        state: The current pipeline state.

    Returns:
        The name of the next node to execute.
    """
    if state.errors:
        return "error_handler"
    return "result_formatting"


# --- Pipeline Construction ---


def create_pipeline() -> Any:
    """Build and compile the LangGraph pipeline.

    Pipeline flow:
    - Video (v3): content_routing → market_resolution → guideline_retrieval
      → video_processing → result_formatting
    - Text: content_routing → text_processing → market_resolution
      → guideline_retrieval → compliance_evaluation → result_formatting
    - Image: content_routing → image_processing → market_resolution
      → guideline_retrieval → compliance_evaluation → result_formatting

    Retry logic with exponential backoff is applied to guideline_retrieval
    and compliance_evaluation nodes for transient errors.

    Returns:
        A compiled LangGraph graph ready for execution.
    """
    # Create the state graph with PipelineState as the state schema
    graph = StateGraph(PipelineState)

    # --- Add Nodes ---
    graph.add_node("content_routing", content_routing)
    graph.add_node("text_processing", text_processing)
    graph.add_node("image_processing", image_processing)
    graph.add_node("video_processing", video_processing)
    graph.add_node("market_resolution", market_resolution)
    graph.add_node("guideline_retrieval", _with_retry(guideline_retrieval))
    graph.add_node("compliance_evaluation", _with_retry(compliance_evaluation))
    graph.add_node("result_formatting", result_formatting)
    graph.add_node("error_handler", error_handler)

    # --- Set Entry Point ---
    graph.set_entry_point("content_routing")

    # --- Add Conditional Edges ---

    # After content_routing: video → market_resolution; text/image → processing
    graph.add_conditional_edges(
        "content_routing",
        _route_after_content_routing,
        {
            "text_processing": "text_processing",
            "image_processing": "image_processing",
            "market_resolution": "market_resolution",
            "error_handler": "error_handler",
        },
    )

    # After text/image processing: route to market_resolution or error
    graph.add_conditional_edges(
        "text_processing",
        _route_after_processing,
        {
            "market_resolution": "market_resolution",
            "error_handler": "error_handler",
        },
    )
    graph.add_conditional_edges(
        "image_processing",
        _route_after_processing,
        {
            "market_resolution": "market_resolution",
            "error_handler": "error_handler",
        },
    )

    # After market_resolution: route to guideline_retrieval or error
    graph.add_conditional_edges(
        "market_resolution",
        _route_after_market_resolution,
        {
            "guideline_retrieval": "guideline_retrieval",
            "error_handler": "error_handler",
        },
    )

    # After guideline_retrieval: video → video_processing; text/image → compliance_evaluation
    graph.add_conditional_edges(
        "guideline_retrieval",
        _route_after_guideline_retrieval,
        {
            "video_processing": "video_processing",
            "compliance_evaluation": "compliance_evaluation",
            "error_handler": "error_handler",
        },
    )

    # After video_processing: route directly to result_formatting (skip step6)
    graph.add_conditional_edges(
        "video_processing",
        _route_after_video_processing,
        {
            "result_formatting": "result_formatting",
            "error_handler": "error_handler",
        },
    )

    # After compliance_evaluation (text/image only): route to result_formatting
    graph.add_conditional_edges(
        "compliance_evaluation",
        _route_after_compliance_evaluation,
        {
            "result_formatting": "result_formatting",
            "error_handler": "error_handler",
        },
    )

    # Terminal edges
    graph.add_edge("result_formatting", END)
    graph.add_edge("error_handler", END)

    # Compile and return
    compiled = graph.compile()
    return compiled


def run_pipeline(submission: ContentSubmission) -> ComplianceResult | dict:
    """Execute the full compliance pipeline for a single submission.

    Creates a new graph instance per invocation (stateless design for Lambda
    compatibility). Initializes the pipeline state from the submission and
    runs the graph to completion.

    Args:
        submission: The content submission to evaluate.

    Returns:
        A ComplianceResult dict (serializable) containing the compliance
        evaluation, or a partial result with error information if the
        pipeline encounters failures.
    """
    # Create a new graph instance per invocation (stateless design)
    pipeline = create_pipeline()

    # Initialize pipeline state from submission
    initial_state = PipelineState(
        submission=submission,
        content_type=submission.content_type,
        market=submission.market,
        target_ethnicity=submission.target_ethnicity,
        target_age_group=submission.target_age_group,
        pipeline_start_ms=int(time.time() * 1000),
    )

    logger.info(
        "Starting pipeline: content_type=%s, market=%s",
        submission.content_type.value,
        submission.market.value,
    )

    # Execute the graph
    final_state = pipeline.invoke(initial_state)

    # Extract the compliance result from the final state
    if isinstance(final_state, dict):
        compliance_result = final_state.get("compliance_result")
    else:
        compliance_result = final_state.compliance_result

    if compliance_result is None:
        # This shouldn't happen if the graph is correctly wired,
        # but handle it gracefully
        logger.error("Pipeline completed without producing a compliance result")
        compliance_result = {
            "content_type": submission.content_type.value,
            "market": submission.market.value,
            "risk_level": "High",
            "score": 0,
            "high_risk_indicators": [],
            "explanation": "Pipeline completed without producing a result. This indicates an internal error.",
            "suggestion": "Please retry the submission or contact support.",
            "processing_metadata": {
                "pipeline_duration_ms": 0,
                "models_used": [],
                "market": submission.market.value,
            },
            "warnings": [],
        }

    logger.info(
        "Pipeline completed: risk_level=%s, score=%s",
        compliance_result.get("risk_level", "unknown")
        if isinstance(compliance_result, dict)
        else "unknown",
        compliance_result.get("score", "unknown")
        if isinstance(compliance_result, dict)
        else "unknown",
    )

    return compliance_result
