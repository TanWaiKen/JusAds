"""Step 7: Result formatting and error handling node for the compliance pipeline.

Parses raw LLM output into a validated ComplianceResult, applying
score-to-risk-level mapping, enforcing field constraints, and adding
processing metadata. Serializes the final result to UTF-8 JSON preserving
non-ASCII characters.

Also handles pipeline failures by producing partial ComplianceResult objects
with warnings indicating which steps failed. Handles timeout scenarios
by returning a result with risk_level "Unknown" and score -1.

This module merges the functionality of the former result_formatting.py and
error_handler.py into a single result output step.
"""

import json
import logging
import time
from typing import Any

from ..models.schemas import (
    ComplianceResult,
    ContentType,
    ImageIssueLocation,
    Market,
    PipelineState,
    ProcessingMetadata,
    TextIssueLocation,
    VideoIssueLocation,
)
from ..scoring import score_to_risk_level

logger = logging.getLogger(__name__)

# --- Constants ---
MAX_HIGH_RISK_INDICATORS = 10
MAX_EXPLANATION_CHARS = 500
MAX_SUGGESTION_CHARS = 400


# =============================================================================
# Result Formatting Functions
# =============================================================================


def _truncate(text: str, max_length: int) -> str:
    """Truncate a string to max_length characters.

    Args:
        text: The string to truncate.
        max_length: Maximum allowed character count.

    Returns:
        The original string if within limits, otherwise truncated.
    """
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length]


def _parse_indicators(
    raw_indicators: list[dict], content_type: ContentType
) -> list[TextIssueLocation | ImageIssueLocation | VideoIssueLocation]:
    """Parse raw indicator dicts into typed issue location models.

    Attempts to parse each indicator according to the content type.
    Invalid indicators are skipped with a warning logged.

    Args:
        raw_indicators: List of raw indicator dicts from LLM output.
        content_type: The content type determining which model to use.

    Returns:
        List of validated issue location objects, max 10 items.
    """
    parsed: list[TextIssueLocation | ImageIssueLocation | VideoIssueLocation] = []

    for indicator in raw_indicators[:MAX_HIGH_RISK_INDICATORS]:
        try:
            if content_type == ContentType.TEXT:
                parsed.append(TextIssueLocation(**indicator))
            elif content_type == ContentType.IMAGE:
                parsed.append(ImageIssueLocation(**indicator))
            elif content_type == ContentType.VIDEO:
                parsed.append(VideoIssueLocation(**indicator))
        except (ValueError, TypeError, KeyError) as e:
            logger.warning(
                "Skipping invalid high_risk_indicator: %s (error: %s)",
                indicator,
                str(e),
            )
            continue

    return parsed


def _calculate_duration_ms(pipeline_start_ms: int | None) -> int:
    """Calculate pipeline duration in milliseconds.

    Args:
        pipeline_start_ms: The pipeline start timestamp in milliseconds,
            or None if not recorded.

    Returns:
        Duration in milliseconds, or 0 if start time is unavailable.
    """
    if pipeline_start_ms is None:
        return 0
    current_ms = int(time.time() * 1000)
    return max(0, current_ms - pipeline_start_ms)


def result_formatting(state: PipelineState) -> PipelineState:
    """Parse raw LLM output into a validated ComplianceResult.

    Extracts fields from state.raw_llm_output, applies score-to-risk-level
    mapping to validate/override the risk level, enforces field constraints
    (max indicators, max text lengths), builds processing metadata, and
    serializes the result to UTF-8 JSON preserving non-ASCII characters.

    Args:
        state: The current pipeline state. Expects:
            - state.raw_llm_output: Dict from compliance_evaluation node
            - state.content_type: Content type for indicator parsing
            - state.market: Target market
            - state.pipeline_start_ms: Pipeline start timestamp
            - state.models_used: List of model IDs used

    Returns:
        Updated PipelineState with compliance_result set as a dict
        (JSON-serializable), or with an error appended if parsing fails.
    """
    # Validate that raw_llm_output exists
    if not state.raw_llm_output:
        state.errors.append({
            "node": "result_formatting",
            "error_type": "validation",
            "message": (
                "No raw LLM output available for result formatting. "
                "Ensure compliance evaluation ran before result formatting."
            ),
        })
        return state

    raw: dict[str, Any] = state.raw_llm_output

    try:
        # 1. Extract score and apply score-to-risk-level mapping
        score = raw.get("score", 0)
        if not isinstance(score, int):
            try:
                score = int(score)
            except (ValueError, TypeError):
                score = 0
        score = max(0, min(100, score))

        # Apply score_to_risk_level mapping to validate/override risk level
        risk_level = score_to_risk_level(score)

        # 2. Extract and truncate text fields
        explanation = _truncate(
            str(raw.get("explanation", "")), MAX_EXPLANATION_CHARS
        )
        suggestion = _truncate(
            str(raw.get("suggestion", "")), MAX_SUGGESTION_CHARS
        )

        # 3. Parse and truncate high_risk_indicators to max 10
        raw_indicators = raw.get("high_risk_indicators", [])
        if not isinstance(raw_indicators, list):
            raw_indicators = []

        # Sort by severity: Severe first, then Moderate, then Minor,
        # regardless of guideline_source (regulatory or cultural).
        SEVERITY_ORDER = {"Severe": 0, "Moderate": 1, "Minor": 2}
        raw_indicators.sort(
            key=lambda x: SEVERITY_ORDER.get(x.get("severity", "Minor"), 2)
        )

        high_risk_indicators = _parse_indicators(
            raw_indicators, state.content_type
        )

        # 4. Calculate pipeline duration
        pipeline_duration_ms = _calculate_duration_ms(state.pipeline_start_ms)

        # 5. Build processing metadata
        processing_metadata = ProcessingMetadata(
            pipeline_duration_ms=pipeline_duration_ms,
            models_used=list(state.models_used),
            market=state.market.value,
        )

        # 6. Construct and validate ComplianceResult using Pydantic
        compliance_result = ComplianceResult(
            content_type=state.content_type,
            market=state.market,
            risk_level=risk_level,
            score=score,
            high_risk_indicators=high_risk_indicators,
            explanation=explanation,
            suggestion=suggestion,
            processing_metadata=processing_metadata,
            warnings=[],
        )

        # 7. Serialize to UTF-8 JSON preserving non-ASCII characters
        result_json = compliance_result.model_dump_json(indent=None)
        # Parse back to dict for state storage (ensures valid JSON round-trip)
        result_dict = json.loads(result_json)

        # Store the validated result in state
        state.compliance_result = result_dict

        logger.info(
            "Result formatting complete: risk_level=%s, score=%d, "
            "indicators=%d, duration_ms=%d",
            risk_level,
            score,
            len(high_risk_indicators),
            pipeline_duration_ms,
        )

    except Exception as e:
        logger.error("Result formatting failed: %s", str(e))
        state.errors.append({
            "node": "result_formatting",
            "error_type": "parse_error",
            "message": f"Failed to format compliance result: {str(e)}",
        })

    return state


# =============================================================================
# Error Handling Functions
# =============================================================================


def error_handler(state: PipelineState) -> PipelineState:
    """Build partial ComplianceResult with error context.

    Reads errors from state.errors, builds a warnings array from them,
    and produces a partial ComplianceResult stored in state.compliance_result.

    For timeout errors:
        - risk_level: "Unknown"
        - score: -1
        - high_risk_indicators: []
        - explanation: indicates which steps completed and which were not reached

    For other errors:
        - risk_level: "High"
        - score: 0
        - high_risk_indicators: []
        - explanation: describes the error(s) encountered

    Args:
        state: The current pipeline state containing errors to handle.

    Returns:
        Updated PipelineState with compliance_result set to a partial result
        dict and warnings populated.
    """
    # Build warnings array from errors
    warnings: list[dict[str, Any]] = []
    for error in state.errors:
        warning = {
            "step_name": error.get("node_name", error.get("error_type", "unknown")),
            "description": error.get("message", error.get("description", "Unknown error")),
            "result_may_be_incomplete": True,
        }
        warnings.append(warning)

    # Calculate pipeline duration
    pipeline_duration_ms = 0
    if state.pipeline_start_ms is not None:
        pipeline_duration_ms = int(time.time() * 1000) - state.pipeline_start_ms

    # Build processing metadata
    processing_metadata = {
        "pipeline_duration_ms": pipeline_duration_ms,
        "models_used": state.models_used,
        "market": state.market.value,
    }

    # Check if any error is a timeout
    is_timeout = any(
        error.get("error_type") == "timeout" for error in state.errors
    )

    if is_timeout:
        # Determine which steps completed and which were not reached
        completed_steps = _get_completed_steps(state)
        not_reached_steps = _get_not_reached_steps(state)

        explanation_parts = []
        if completed_steps:
            explanation_parts.append(
                f"Completed: {', '.join(completed_steps)}"
            )
        if not_reached_steps:
            explanation_parts.append(
                f"Not reached: {', '.join(not_reached_steps)}"
            )

        explanation = (
            "Pipeline timed out. " + ". ".join(explanation_parts)
            if explanation_parts
            else "Pipeline timed out before any steps could complete."
        )

        # Timeout: return "Unknown" risk_level and score -1
        # Stored as dict to bypass ComplianceResult Pydantic validation
        # (which constrains score to [0,100] and risk_level to High/Medium/Low)
        compliance_result = {
            "content_type": state.content_type.value,
            "market": state.market.value,
            "risk_level": "Unknown",
            "score": -1,
            "high_risk_indicators": [],
            "explanation": explanation[:500],
            "suggestion": "Please retry the submission. If the issue persists, try with smaller content or contact support.",
            "processing_metadata": processing_metadata,
            "warnings": warnings,
        }
    else:
        # Non-timeout errors: return partial result with High risk
        error_descriptions = [
            error.get("message", error.get("description", "Unknown error"))
            for error in state.errors
        ]
        explanation = (
            f"Pipeline encountered error(s): {'; '.join(error_descriptions)}"
        )

        compliance_result = {
            "content_type": state.content_type.value,
            "market": state.market.value,
            "risk_level": "High",
            "score": 0,
            "high_risk_indicators": [],
            "explanation": explanation[:500],
            "suggestion": "Review the warnings for details on which pipeline steps failed. Consider resubmitting the content.",
            "processing_metadata": processing_metadata,
            "warnings": warnings,
        }

    state.compliance_result = compliance_result

    return state


def _get_completed_steps(state: PipelineState) -> list[str]:
    """Determine which pipeline steps completed based on state fields.

    Args:
        state: The current pipeline state.

    Returns:
        List of step names that completed successfully.
    """
    completed = []

    # Content routing always completes if we got this far
    if state.content_type is not None:
        completed.append("content_routing")

    # Check content-type-specific processing
    if state.unified_content is not None:
        if state.content_type.value == "text":
            completed.append("text_processing")
        elif state.content_type.value == "image":
            completed.append("image_processing")
        elif state.content_type.value == "video":
            completed.append("video_processing")

    # Guideline retrieval
    if state.retrieved_guidelines is not None:
        completed.append("guideline_retrieval")

    # Compliance evaluation
    if state.raw_llm_output is not None:
        completed.append("compliance_evaluation")

    return completed


def _get_not_reached_steps(state: PipelineState) -> list[str]:
    """Determine which pipeline steps were not reached based on state fields.

    Args:
        state: The current pipeline state.

    Returns:
        List of step names that were not reached before timeout.
    """
    all_steps = [
        "content_routing",
        "guideline_retrieval",
        "compliance_evaluation",
        "result_formatting",
    ]

    # Add the appropriate content processing step
    if state.content_type is not None:
        processing_step = f"{state.content_type.value}_processing"
        # Insert after content_routing
        all_steps.insert(1, processing_step)

    completed = set(_get_completed_steps(state))
    not_reached = [step for step in all_steps if step not in completed]

    return not_reached
