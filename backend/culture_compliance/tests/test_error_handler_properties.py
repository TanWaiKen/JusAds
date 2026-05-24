"""Property-based tests for error handling.

Feature: content-compliance
Tests Property 14 from the design document.
"""

import time

from hypothesis import given, settings, strategies as st

from culture_compliance.models.schemas import (
    ContentSubmission,
    ContentType,
    Market,
    PipelineState,
)
from culture_compliance.nodes.step7_result_formatting import error_handler


# --- Strategies ---

# Pipeline node names that can fail
NODE_NAMES = [
    "content_routing",
    "text_processing",
    "image_processing",
    "video_processing",
    "guideline_retrieval",
    "compliance_evaluation",
    "result_formatting",
]

# Error types that can occur in the pipeline
ERROR_TYPES = [
    "validation",
    "service_unavailable",
    "timeout",
    "parse_error",
]


def node_name_strategy():
    """Generate realistic pipeline node names."""
    return st.sampled_from(NODE_NAMES) | st.text(
        alphabet=st.characters(whitelist_categories=("L", "N", "Pd")),
        min_size=1,
        max_size=50,
    )


def error_type_strategy():
    """Generate error type strings."""
    return st.sampled_from(ERROR_TYPES) | st.text(
        alphabet=st.characters(whitelist_categories=("L", "N", "Pd")),
        min_size=1,
        max_size=50,
    )


def error_description_strategy():
    """Generate error description strings."""
    return st.text(
        alphabet=st.characters(
            whitelist_categories=("L", "N", "P", "Z"),
            blacklist_characters="\x00",
        ),
        min_size=1,
        max_size=200,
    )


def _make_state_with_error(node_name: str, error_type: str, description: str) -> PipelineState:
    """Create a PipelineState with a single error entry."""
    return PipelineState(
        submission=ContentSubmission(
            content="Test content for compliance",
            content_type=ContentType.TEXT,
            market=Market.MALAYSIA,
        ),
        content_type=ContentType.TEXT,
        market=Market.MALAYSIA,
        errors=[
            {
                "node_name": node_name,
                "error_type": error_type,
                "message": description,
            }
        ],
        warnings=[],
        models_used=[],
        pipeline_start_ms=int(time.time() * 1000) - 500,
    )


# --- Property 14: Error State Capture Completeness ---
# **Validates: Requirements 7.3, 10.6**


@settings(max_examples=100, deadline=5000)
@given(
    node_name=node_name_strategy(),
    error_type=error_type_strategy(),
    description=error_description_strategy(),
)
def test_property_14_error_state_contains_all_error_details(
    node_name, error_type, description
):
    """Property 14: Error State Capture Completeness - error details preserved.

    For any pipeline node failure (given a node name, error type, and error
    description), the error handler SHALL produce a state containing all three
    error details.

    **Validates: Requirements 7.3, 10.6**
    """
    state = _make_state_with_error(node_name, error_type, description)

    result_state = error_handler(state)

    # The state should still contain the original error details
    assert len(result_state.errors) == 1
    error_entry = result_state.errors[0]
    assert error_entry["node_name"] == node_name
    assert error_entry["error_type"] == error_type
    assert error_entry["message"] == description


@settings(max_examples=100, deadline=5000)
@given(
    node_name=node_name_strategy(),
    error_type=error_type_strategy(),
    description=error_description_strategy(),
)
def test_property_14_warnings_array_identifies_failed_step(
    node_name, error_type, description
):
    """Property 14: Error State Capture Completeness - warnings identify failed step.

    For any pipeline node failure, the error handler SHALL produce a warnings
    array entry identifying the failed step (step_name matches node_name).

    **Validates: Requirements 7.3, 10.6**
    """
    state = _make_state_with_error(node_name, error_type, description)

    result_state = error_handler(state)

    # The compliance_result must have a warnings array
    assert result_state.compliance_result is not None
    warnings = result_state.compliance_result["warnings"]
    assert len(warnings) >= 1

    # The first warning should identify the failed step by node_name
    warning = warnings[0]
    assert warning["step_name"] == node_name


@settings(max_examples=100, deadline=5000)
@given(
    node_name=node_name_strategy(),
    error_type=error_type_strategy(),
    description=error_description_strategy(),
)
def test_property_14_warnings_contain_failure_description(
    node_name, error_type, description
):
    """Property 14: Error State Capture Completeness - warnings contain description.

    For any pipeline node failure, the error handler SHALL produce a warnings
    array entry containing the failure description.

    **Validates: Requirements 7.3, 10.6**
    """
    state = _make_state_with_error(node_name, error_type, description)

    result_state = error_handler(state)

    assert result_state.compliance_result is not None
    warnings = result_state.compliance_result["warnings"]
    assert len(warnings) >= 1

    # The warning description should match the error message
    warning = warnings[0]
    assert warning["description"] == description


@settings(max_examples=100, deadline=5000)
@given(
    node_name=node_name_strategy(),
    error_type=error_type_strategy(),
    description=error_description_strategy(),
)
def test_property_14_warnings_indicate_result_may_be_incomplete(
    node_name, error_type, description
):
    """Property 14: Error State Capture Completeness - result_may_be_incomplete flag.

    For any pipeline node failure, the error handler SHALL produce a warnings
    array entry indicating whether the result may be incomplete
    (result_may_be_incomplete is True).

    **Validates: Requirements 7.3, 10.6**
    """
    state = _make_state_with_error(node_name, error_type, description)

    result_state = error_handler(state)

    assert result_state.compliance_result is not None
    warnings = result_state.compliance_result["warnings"]
    assert len(warnings) >= 1

    # The warning must indicate the result may be incomplete
    warning = warnings[0]
    assert "result_may_be_incomplete" in warning
    assert warning["result_may_be_incomplete"] is True
