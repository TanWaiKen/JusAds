"""Property-based tests for content routing and market resolution.

Feature: content-compliance
Tests Properties 1, 11, and 13 from the design document.
"""

from hypothesis import given, settings, assume, strategies as st

from culture_compliance.models.schemas import (
    ContentSubmission,
    ContentType,
    Market,
    PipelineState,
)
from culture_compliance.nodes.step1_routing import content_routing
from culture_compliance.nodes.step1_routing import (
    get_collection_name,
    market_resolution,
    resolve_market,
)


# --- Strategies ---


def valid_content_type_strategy():
    """Generate valid ContentType enum values."""
    return st.sampled_from([ContentType.TEXT, ContentType.IMAGE, ContentType.VIDEO])


def case_variant_strategy(base_string: str):
    """Generate arbitrary case variants of a given string.

    For each character, randomly choose upper or lower case.
    """
    return st.tuples(
        *[st.sampled_from([c.lower(), c.upper()]) for c in base_string]
    ).map(lambda chars: "".join(chars))


def invalid_market_strategy():
    """Generate strings that do NOT match 'malaysia' or 'singapore' (case-insensitive).

    Uses text generation and filters out valid market values.
    """
    return st.text(
        alphabet=st.characters(whitelist_categories=("L", "N", "P", "S")),
        min_size=1,
        max_size=30,
    ).filter(lambda s: s.strip().lower() not in ("malaysia", "singapore", ""))


# --- Property 1: Content Type Routing Preserves Type ---
# **Validates: Requirements 1.1, 1.2, 1.3, 7.5**


@settings(max_examples=100, deadline=5000)
@given(content_type=valid_content_type_strategy())
def test_property_1_content_type_routing_preserves_type(content_type):
    """Property 1: Content Type Routing Preserves Type.

    For any valid ContentSubmission with content_type in {"text", "image", "video"},
    the pipeline routing node SHALL select the corresponding pipeline path and the
    final ComplianceResult.content_type SHALL equal the input content_type.

    **Validates: Requirements 1.1, 1.2, 1.3, 7.5**
    """
    # Create a valid submission with the given content type
    submission = ContentSubmission(
        content="Sample content for compliance review",
        content_type=content_type,
        market=Market.MALAYSIA,
    )

    state = PipelineState(
        submission=submission,
        content_type=content_type,
        market=Market.MALAYSIA,
    )

    # Run the content routing node
    result_state = content_routing(state)

    # The routing node should preserve the content_type without errors
    assert result_state.errors == [], (
        f"Unexpected errors for valid content_type '{content_type.value}': "
        f"{result_state.errors}"
    )

    # The content_type in the state should equal the input content_type
    assert result_state.content_type == content_type, (
        f"Content type mismatch: input was '{content_type.value}', "
        f"but state has '{result_state.content_type.value}'"
    )


@settings(max_examples=100, deadline=5000)
@given(content_type=valid_content_type_strategy())
def test_property_1_routing_does_not_alter_submission(content_type):
    """Property 1: Content Type Routing Preserves Type - submission unchanged.

    The routing node SHALL NOT modify the original submission's content_type field.

    **Validates: Requirements 1.1, 1.2, 1.3, 7.5**
    """
    submission = ContentSubmission(
        content="Test content for routing verification",
        content_type=content_type,
        market=Market.MALAYSIA,
    )

    state = PipelineState(
        submission=submission,
        content_type=content_type,
        market=Market.MALAYSIA,
    )

    result_state = content_routing(state)

    # The submission's content_type should remain unchanged
    assert result_state.submission.content_type == content_type, (
        f"Submission content_type was modified: expected '{content_type.value}', "
        f"got '{result_state.submission.content_type.value}'"
    )


# --- Property 11: Market Routing Correctness ---
# **Validates: Requirements 5.1, 5.2**


@settings(max_examples=100, deadline=5000)
@given(malaysia_variant=case_variant_strategy("malaysia"))
def test_property_11_malaysia_routes_to_mcmc_collection(malaysia_variant):
    """Property 11: Market Routing Correctness (Malaysia).

    For any case variant of "malaysia" (e.g., "Malaysia", "MALAYSIA", "mAlAySiA"),
    the pipeline SHALL select the "mcmc-guidelines" collection.

    **Validates: Requirements 5.1, 5.2**
    """
    # resolve_market should handle any case variant of "malaysia"
    resolved = resolve_market(malaysia_variant)

    assert resolved == Market.MALAYSIA, (
        f"Expected Market.MALAYSIA for input '{malaysia_variant}', "
        f"got {resolved}"
    )

    # The collection name for Malaysia should be "mcmc-guidelines"
    collection = get_collection_name(resolved)
    assert collection == "mcmc-guidelines", (
        f"Expected 'mcmc-guidelines' for Malaysia, got '{collection}'"
    )


@settings(max_examples=100, deadline=5000)
@given(singapore_variant=case_variant_strategy("singapore"))
def test_property_11_singapore_routes_to_imda_asas_collection(singapore_variant):
    """Property 11: Market Routing Correctness (Singapore).

    For any case variant of "singapore" (e.g., "Singapore", "SINGAPORE", "sInGaPoRe"),
    the pipeline SHALL select the "singapore-imda-asas-guidelines" collection.

    **Validates: Requirements 5.1, 5.2**
    """
    # resolve_market should handle any case variant of "singapore"
    resolved = resolve_market(singapore_variant)

    assert resolved == Market.SINGAPORE, (
        f"Expected Market.SINGAPORE for input '{singapore_variant}', "
        f"got {resolved}"
    )

    # The collection name for Singapore should be "singapore-imda-asas-guidelines"
    collection = get_collection_name(resolved)
    assert collection == "singapore-imda-asas-guidelines", (
        f"Expected 'singapore-imda-asas-guidelines' for Singapore, got '{collection}'"
    )


@settings(max_examples=100, deadline=5000)
@given(malaysia_variant=case_variant_strategy("malaysia"))
def test_property_11_market_resolution_node_malaysia(malaysia_variant):
    """Property 11: Market Routing Correctness - full node (Malaysia).

    The market_resolution node SHALL set guideline_collection to "mcmc-guidelines"
    for any case variant of "malaysia".

    **Validates: Requirements 5.1, 5.2**
    """
    # The Market enum only accepts lowercase, so we test resolve_market directly
    # and verify the node works with the resolved enum value
    resolved_market = resolve_market(malaysia_variant)

    submission = ContentSubmission(
        content="Test content",
        content_type=ContentType.TEXT,
        market=resolved_market,
    )

    state = PipelineState(
        submission=submission,
        content_type=ContentType.TEXT,
        market=resolved_market,
    )

    result_state = market_resolution(state)

    assert result_state.guideline_collection == "mcmc-guidelines", (
        f"Expected 'mcmc-guidelines' for market variant '{malaysia_variant}', "
        f"got '{result_state.guideline_collection}'"
    )
    assert result_state.errors == []


@settings(max_examples=100, deadline=5000)
@given(singapore_variant=case_variant_strategy("singapore"))
def test_property_11_market_resolution_node_singapore(singapore_variant):
    """Property 11: Market Routing Correctness - full node (Singapore).

    The market_resolution node SHALL set guideline_collection to
    "singapore-imda-asas-guidelines" for any case variant of "singapore".

    **Validates: Requirements 5.1, 5.2**
    """
    resolved_market = resolve_market(singapore_variant)

    submission = ContentSubmission(
        content="Test content",
        content_type=ContentType.TEXT,
        market=resolved_market,
    )

    state = PipelineState(
        submission=submission,
        content_type=ContentType.TEXT,
        market=resolved_market,
    )

    result_state = market_resolution(state)

    assert result_state.guideline_collection == "singapore-imda-asas-guidelines", (
        f"Expected 'singapore-imda-asas-guidelines' for market variant "
        f"'{singapore_variant}', got '{result_state.guideline_collection}'"
    )
    assert result_state.errors == []


# --- Property 13: Invalid Market Rejection ---
# **Validates: Requirements 5.6**


@settings(max_examples=100, deadline=5000)
@given(invalid_market=invalid_market_strategy())
def test_property_13_invalid_market_rejection(invalid_market):
    """Property 13: Invalid Market Rejection.

    For any string that does not match "malaysia" or "singapore" (case-insensitive),
    the pipeline SHALL reject the submission with an error indicating the supported
    markets.

    **Validates: Requirements 5.6**
    """
    import pytest

    with pytest.raises(ValueError) as exc_info:
        resolve_market(invalid_market)

    error_message = str(exc_info.value)

    # Error should mention "Unsupported market"
    assert "Unsupported market" in error_message or "unsupported" in error_message.lower(), (
        f"Error message for '{invalid_market}' should indicate unsupported market, "
        f"got: '{error_message}'"
    )

    # Error should list supported markets
    assert "malaysia" in error_message.lower(), (
        f"Error message should list 'malaysia' as supported, got: '{error_message}'"
    )
    assert "singapore" in error_message.lower(), (
        f"Error message should list 'singapore' as supported, got: '{error_message}'"
    )


@settings(max_examples=100, deadline=5000)
@given(invalid_market=invalid_market_strategy())
def test_property_13_invalid_market_includes_provided_value(invalid_market):
    """Property 13: Invalid Market Rejection - error includes the provided value.

    The error message SHALL include the invalid market value that was provided.

    **Validates: Requirements 5.6**
    """
    import pytest

    with pytest.raises(ValueError) as exc_info:
        resolve_market(invalid_market)

    error_message = str(exc_info.value)

    # Error should include the provided invalid value
    assert invalid_market in error_message, (
        f"Error message should include the invalid value '{invalid_market}', "
        f"got: '{error_message}'"
    )
