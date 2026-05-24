"""Property-based tests for data model validation.

Tests Properties 2, 5, and 15 from the design document using Hypothesis.

**Validates: Requirements 1.4, 1.6, 2.5, 10.1, 10.2, 10.3, 10.4, 10.5**
"""

import string

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from pydantic import ValidationError

from culture_compliance.models.schemas import (
    ComplianceResult,
    ContentSubmission,
    ContentType,
    ImageIssueLocation,
    Market,
    ProcessingMetadata,
    PipelineWarning,
    TextIssueLocation,
    VideoIssueLocation,
)


# --- Strategies ---

VALID_CONTENT_TYPES = ["text", "image", "video"]

# Strategy for strings that are NOT valid content types
invalid_content_type_strategy = st.text(
    min_size=0, max_size=50
).filter(lambda s: s not in VALID_CONTENT_TYPES)

# Strategy for whitespace-only strings (spaces, tabs, newlines, empty)
whitespace_only_strategy = st.text(
    alphabet=st.sampled_from([" ", "\t", "\n", "\r", "\x0b", "\x0c"]),
    min_size=0,
    max_size=100,
)

# Strategies for ComplianceResult fields
valid_content_type_strategy = st.sampled_from(list(ContentType))
valid_market_strategy = st.sampled_from(list(Market))
valid_risk_level_strategy = st.sampled_from(["High", "Medium", "Low"])
valid_score_strategy = st.integers(min_value=0, max_value=100)
valid_explanation_strategy = st.text(
    alphabet=st.characters(categories=("L", "N", "P", "Z", "S")),
    min_size=1,
    max_size=500,
)
valid_suggestion_strategy = st.text(
    alphabet=st.characters(categories=("L", "N", "P", "Z", "S")),
    min_size=1,
    max_size=400,
)

# Strategy for ProcessingMetadata
processing_metadata_strategy = st.builds(
    ProcessingMetadata,
    pipeline_duration_ms=st.integers(min_value=0, max_value=300000),
    models_used=st.lists(
        st.text(alphabet=string.ascii_letters + string.digits + "-.", min_size=1, max_size=50),
        min_size=1,
        max_size=5,
    ),
    market=st.sampled_from(["malaysia", "singapore"]),
)

# Strategy for TextIssueLocation
text_issue_strategy = st.builds(
    TextIssueLocation,
    phrase=st.text(min_size=1, max_size=200).filter(lambda s: s.strip()),
    char_offset=st.integers(min_value=0, max_value=10000),
    category=st.sampled_from([
        "Religious Sensitivity",
        "Ethnic/Racial",
        "Sexual/Explicit",
        "Political/State",
        "LGBTQ",
        "Profanity",
    ]),
    severity=st.sampled_from(["Severe", "Moderate", "Minor"]),
)

# Strategy for ImageIssueLocation
image_issue_strategy = st.builds(
    ImageIssueLocation,
    bounding_box=st.fixed_dictionaries({
        "x": st.floats(min_value=0, max_value=100),
        "y": st.floats(min_value=0, max_value=100),
        "width": st.floats(min_value=0, max_value=100),
        "height": st.floats(min_value=0, max_value=100),
    }),
    description=st.text(min_size=1, max_size=200).filter(lambda s: s.strip()),
    category=st.sampled_from([
        "Religious Sensitivity",
        "Ethnic/Racial",
        "Sexual/Explicit",
        "Political/State",
        "LGBTQ",
        "Profanity",
    ]),
    severity=st.sampled_from(["Severe", "Moderate", "Minor"]),
)

# Strategy for VideoIssueLocation
video_issue_strategy = st.builds(
    VideoIssueLocation,
    timestamp=st.from_regex(r"[0-9]{2}:[0-9]{2}", fullmatch=True),
    description=st.text(min_size=1, max_size=200).filter(lambda s: s.strip()),
    category=st.sampled_from([
        "Religious Sensitivity",
        "Ethnic/Racial",
        "Sexual/Explicit",
        "Political/State",
        "LGBTQ",
        "Profanity",
    ]),
    severity=st.sampled_from(["Severe", "Moderate", "Minor"]),
)

# Strategy for high_risk_indicators (max 10 items)
high_risk_indicators_strategy = st.lists(
    st.one_of(text_issue_strategy, image_issue_strategy, video_issue_strategy),
    min_size=0,
    max_size=10,
)


# --- Property 2: Invalid Content Type Rejection ---


class TestInvalidContentTypeRejection:
    """Property 2: Invalid Content Type Rejection.

    For any string value that is not exactly one of "text", "image", or "video"
    (including case variants like "Text", "IMAGE", empty strings, and arbitrary
    strings), the content router SHALL reject the submission with an error
    response listing the supported types.

    **Validates: Requirements 1.4, 1.6**
    """

    @given(invalid_type=invalid_content_type_strategy)
    @settings(max_examples=100, deadline=5000)
    def test_arbitrary_invalid_strings_rejected(self, invalid_type: str):
        """Any string not exactly 'text', 'image', or 'video' is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ContentSubmission(
                content="Some valid content",
                content_type=invalid_type,
                market="malaysia",
            )
        # Verify the error relates to content_type
        errors = exc_info.value.errors()
        assert any(
            "content_type" in str(err.get("loc", ""))
            for err in errors
        ), f"Expected content_type validation error, got: {errors}"

    @given(
        valid_type=st.sampled_from(VALID_CONTENT_TYPES),
        case_variant=st.sampled_from(["upper", "title", "mixed"]),
    )
    @settings(max_examples=100, deadline=5000)
    def test_case_variants_rejected(self, valid_type: str, case_variant: str):
        """Case variants of valid types (e.g., 'Text', 'IMAGE') are rejected."""
        if case_variant == "upper":
            invalid = valid_type.upper()
        elif case_variant == "title":
            invalid = valid_type.title()
        else:
            # Mixed case - capitalize random chars
            invalid = valid_type[0].upper() + valid_type[1:]

        # Only test if the case variant is actually different from the original
        assume(invalid != valid_type)

        with pytest.raises(ValidationError) as exc_info:
            ContentSubmission(
                content="Some valid content",
                content_type=invalid,
                market="malaysia",
            )
        errors = exc_info.value.errors()
        assert any(
            "content_type" in str(err.get("loc", ""))
            for err in errors
        ), f"Expected content_type validation error for '{invalid}', got: {errors}"


# --- Property 5: Whitespace Text Rejection ---


class TestWhitespaceTextRejection:
    """Property 5: Whitespace Text Rejection.

    For any string composed entirely of whitespace characters (spaces, tabs,
    newlines, or empty string), the text pipeline SHALL reject the input with
    a validation error.

    **Validates: Requirements 2.5**
    """

    @given(whitespace_content=whitespace_only_strategy)
    @settings(max_examples=100, deadline=5000)
    def test_whitespace_only_content_rejected(self, whitespace_content: str):
        """Any whitespace-only string is rejected by ContentSubmission validation."""
        with pytest.raises(ValidationError) as exc_info:
            ContentSubmission(
                content=whitespace_content,
                content_type="text",
                market="malaysia",
            )
        errors = exc_info.value.errors()
        assert any(
            "content" in str(err.get("loc", ""))
            for err in errors
        ), f"Expected content validation error for whitespace input, got: {errors}"

    @given(
        num_spaces=st.integers(min_value=0, max_value=50),
        num_tabs=st.integers(min_value=0, max_value=20),
        num_newlines=st.integers(min_value=0, max_value=20),
    )
    @settings(max_examples=100, deadline=5000)
    def test_mixed_whitespace_combinations_rejected(
        self, num_spaces: int, num_tabs: int, num_newlines: int
    ):
        """Combinations of different whitespace characters are all rejected."""
        whitespace_content = " " * num_spaces + "\t" * num_tabs + "\n" * num_newlines
        # This is always whitespace-only (or empty)
        with pytest.raises(ValidationError) as exc_info:
            ContentSubmission(
                content=whitespace_content,
                content_type="text",
                market="malaysia",
            )
        errors = exc_info.value.errors()
        assert any(
            "content" in str(err.get("loc", ""))
            for err in errors
        ), f"Expected content validation error, got: {errors}"


# --- Property 15: ComplianceResult Schema Validity ---


class TestComplianceResultSchemaValidity:
    """Property 15: ComplianceResult Schema Validity.

    For any valid combination of field values, constructing a ComplianceResult
    SHALL succeed and all fields SHALL be accessible with their original values.

    **Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5**
    """

    @given(
        content_type=valid_content_type_strategy,
        market=valid_market_strategy,
        risk_level=valid_risk_level_strategy,
        score=valid_score_strategy,
        explanation=valid_explanation_strategy,
        suggestion=valid_suggestion_strategy,
        processing_metadata=processing_metadata_strategy,
        warnings=st.lists(
            st.builds(
                PipelineWarning,
                step_name=st.text(min_size=1, max_size=50).filter(lambda s: s.strip()),
                description=st.text(min_size=1, max_size=200).filter(lambda s: s.strip()),
                result_may_be_incomplete=st.booleans(),
            ),
            min_size=0,
            max_size=3,
        ),
        high_risk_indicators=high_risk_indicators_strategy,
    )
    @settings(max_examples=100, deadline=5000)
    def test_valid_compliance_result_construction(
        self,
        content_type: ContentType,
        market: Market,
        risk_level: str,
        score: int,
        explanation: str,
        suggestion: str,
        processing_metadata: ProcessingMetadata,
        warnings: list,
        high_risk_indicators: list,
    ):
        """Any valid combination of field values constructs a ComplianceResult successfully."""
        # Filter out empty explanation/suggestion (must have at least 1 char)
        assume(len(explanation.strip()) > 0)
        assume(len(suggestion.strip()) > 0)

        result = ComplianceResult(
            content_type=content_type,
            market=market,
            risk_level=risk_level,
            score=score,
            high_risk_indicators=high_risk_indicators,
            explanation=explanation,
            suggestion=suggestion,
            processing_metadata=processing_metadata,
            warnings=warnings,
        )

        # Verify all fields are accessible with their original values
        assert result.content_type == content_type
        assert result.market == market
        assert result.risk_level == risk_level
        assert result.score == score
        assert result.explanation == explanation
        assert result.suggestion == suggestion
        assert result.processing_metadata == processing_metadata
        assert result.warnings == warnings
        assert result.high_risk_indicators == high_risk_indicators

    @given(
        content_type=valid_content_type_strategy,
        market=valid_market_strategy,
        risk_level=valid_risk_level_strategy,
        score=valid_score_strategy,
        processing_metadata=processing_metadata_strategy,
    )
    @settings(max_examples=100, deadline=5000)
    def test_compliance_result_with_empty_indicators(
        self,
        content_type: ContentType,
        market: Market,
        risk_level: str,
        score: int,
        processing_metadata: ProcessingMetadata,
    ):
        """ComplianceResult with empty high_risk_indicators is valid (clean content)."""
        result = ComplianceResult(
            content_type=content_type,
            market=market,
            risk_level=risk_level,
            score=score,
            high_risk_indicators=[],
            explanation="No issues found.",
            suggestion="Content is compliant.",
            processing_metadata=processing_metadata,
            warnings=[],
        )

        assert result.content_type == content_type
        assert result.market == market
        assert result.risk_level == risk_level
        assert result.score == score
        assert result.high_risk_indicators == []
        assert result.explanation == "No issues found."
        assert result.suggestion == "Content is compliant."
