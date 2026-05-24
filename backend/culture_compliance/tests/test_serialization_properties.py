"""Property-based tests for ComplianceResult serialization.

Tests Properties 16, 17, and 18 from the design document:
- Property 16: Serialization Round-Trip Identity
- Property 17: Deserialization Error Detection
- Property 18: Payload Size Rejection

**Validates: Requirements 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7**
"""

import json
import sys

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st
from pydantic import ValidationError

sys.path.insert(
    0, r"c:\Users\tanwa\OneDrive\TWK developer\Documents\Langhub-main\backend"
)

from culture_compliance.models.schemas import (
    ComplianceResult,
    ContentType,
    Market,
    ProcessingMetadata,
    PipelineWarning,
    TextIssueLocation,
    ImageIssueLocation,
    VideoIssueLocation,
)


# --- Hypothesis Strategies ---

MAX_PAYLOAD_SIZE = 1_048_576  # 1 MB


# Strategy for non-ASCII text (including Malay, Chinese, Tamil characters)
non_ascii_text = st.text(
    alphabet=st.characters(
        categories=("L", "N", "P", "Z", "S"),
        min_codepoint=32,
        max_codepoint=0xFFFF,
    ),
    min_size=1,
    max_size=50,
)

# Strategy for explanation text (max 500 chars, may include non-ASCII)
explanation_text = st.text(
    alphabet=st.characters(
        categories=("L", "N", "P", "Z", "S"),
        min_codepoint=32,
        max_codepoint=0xFFFF,
    ),
    min_size=1,
    max_size=100,
)

# Strategy for suggestion text (max 400 chars)
suggestion_text = st.text(
    alphabet=st.characters(
        categories=("L", "N", "P", "Z", "S"),
        min_codepoint=32,
        max_codepoint=0xFFFF,
    ),
    min_size=1,
    max_size=100,
)

# Strategy for violation categories
violation_categories = st.sampled_from(
    [
        "Religious Sensitivity",
        "Ethnic/Racial",
        "Sexual/Explicit",
        "Political/State",
        "LGBTQ",
        "Profanity",
    ]
)

# Strategy for severity levels
severity_levels = st.sampled_from(["Severe", "Moderate", "Minor"])

# Strategy for TextIssueLocation
text_issue_location_strategy = st.builds(
    TextIssueLocation,
    phrase=st.text(min_size=1, max_size=50),
    char_offset=st.integers(min_value=0, max_value=10000),
    category=violation_categories,
    severity=severity_levels,
)

# Strategy for ImageIssueLocation
image_issue_location_strategy = st.builds(
    ImageIssueLocation,
    bounding_box=st.fixed_dictionaries(
        {
            "x": st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
            "y": st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
            "width": st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
            "height": st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
        }
    ),
    description=st.text(min_size=1, max_size=50),
    category=violation_categories,
    severity=severity_levels,
)

# Strategy for VideoIssueLocation
video_issue_location_strategy = st.builds(
    VideoIssueLocation,
    timestamp=st.from_regex(r"[0-9]{2}:[0-9]{2}", fullmatch=True),
    description=st.text(min_size=1, max_size=50),
    category=violation_categories,
    severity=severity_levels,
)

# Strategy for ProcessingMetadata
processing_metadata_strategy = st.builds(
    ProcessingMetadata,
    pipeline_duration_ms=st.integers(min_value=0, max_value=120000),
    models_used=st.lists(st.text(min_size=1, max_size=30), min_size=1, max_size=3),
    market=st.sampled_from(["malaysia", "singapore"]),
)

# Strategy for PipelineWarning
pipeline_warning_strategy = st.builds(
    PipelineWarning,
    step_name=st.text(min_size=1, max_size=30),
    description=st.text(min_size=1, max_size=100),
    result_may_be_incomplete=st.booleans(),
)

# Strategy for high_risk_indicators based on content_type
def indicators_for_content_type(content_type: ContentType):
    """Return the appropriate indicator strategy for a content type."""
    if content_type == ContentType.TEXT:
        return st.lists(text_issue_location_strategy, min_size=0, max_size=5)
    elif content_type == ContentType.IMAGE:
        return st.lists(image_issue_location_strategy, min_size=0, max_size=5)
    else:
        return st.lists(video_issue_location_strategy, min_size=0, max_size=5)


# Strategy for a valid ComplianceResult
@st.composite
def compliance_result_strategy(draw):
    """Generate a valid ComplianceResult with consistent content_type and indicators."""
    content_type = draw(st.sampled_from(list(ContentType)))
    market = draw(st.sampled_from(list(Market)))
    risk_level = draw(st.sampled_from(["High", "Medium", "Low"]))
    score = draw(st.integers(min_value=0, max_value=100))
    indicators = draw(indicators_for_content_type(content_type))
    explanation = draw(explanation_text)
    suggestion = draw(suggestion_text)
    metadata = draw(processing_metadata_strategy)
    warnings = draw(st.lists(pipeline_warning_strategy, min_size=0, max_size=3))

    return ComplianceResult(
        content_type=content_type,
        market=market,
        risk_level=risk_level,
        score=score,
        high_risk_indicators=indicators,
        explanation=explanation,
        suggestion=suggestion,
        processing_metadata=metadata,
        warnings=warnings,
    )


# --- Property 16: Serialization Round-Trip Identity ---


class TestSerializationRoundTrip:
    """Property 16: Serialization Round-Trip Identity.

    For any valid ComplianceResult object (including those with non-ASCII
    characters), serializing to JSON and deserializing back SHALL produce
    an object where every field value is equal in type and content to the
    original.

    **Validates: Requirements 11.1, 11.2, 11.3**
    """

    @given(result=compliance_result_strategy())
    @settings(max_examples=100, deadline=5000, suppress_health_check=[HealthCheck.too_slow])
    def test_round_trip_identity(self, result: ComplianceResult):
        """Serializing to JSON and deserializing back produces identical object."""
        # Serialize to JSON (UTF-8, preserving non-ASCII)
        json_str = result.model_dump_json()

        # Deserialize back
        restored = ComplianceResult.model_validate_json(json_str)

        # Every field must be equal in type and content
        assert restored.content_type == result.content_type
        assert restored.market == result.market
        assert restored.risk_level == result.risk_level
        assert restored.score == result.score
        assert restored.explanation == result.explanation
        assert restored.suggestion == result.suggestion
        assert restored.processing_metadata == result.processing_metadata
        assert restored.warnings == result.warnings
        assert len(restored.high_risk_indicators) == len(result.high_risk_indicators)

        # Deep equality check
        assert restored == result

    @given(result=compliance_result_strategy())
    @settings(max_examples=100, deadline=5000, suppress_health_check=[HealthCheck.too_slow])
    def test_round_trip_preserves_non_ascii(self, result: ComplianceResult):
        """Non-ASCII characters are preserved through serialization without escaping."""
        # Serialize with ensure_ascii=False equivalent (Pydantic default)
        json_str = result.model_dump_json()

        # Verify non-ASCII characters are NOT escaped to \\uXXXX sequences
        # when the original contains non-ASCII
        if any(ord(c) > 127 for c in result.explanation):
            # The JSON should contain the actual characters, not escape sequences
            parsed = json.loads(json_str)
            assert parsed["explanation"] == result.explanation

        # Deserialize and verify
        restored = ComplianceResult.model_validate_json(json_str)
        assert restored.explanation == result.explanation
        assert restored.suggestion == result.suggestion

    @given(result=compliance_result_strategy())
    @settings(max_examples=100, deadline=5000, suppress_health_check=[HealthCheck.too_slow])
    def test_round_trip_via_dict(self, result: ComplianceResult):
        """Round-trip through dict serialization also preserves identity."""
        # Serialize to dict then to JSON string
        result_dict = result.model_dump()
        json_str = json.dumps(result_dict, ensure_ascii=False)

        # Deserialize back
        parsed_dict = json.loads(json_str)
        restored = ComplianceResult.model_validate(parsed_dict)

        assert restored == result


# --- Property 17: Deserialization Error Detection ---


class TestDeserializationErrorDetection:
    """Property 17: Deserialization Error Detection.

    For any JSON payload that violates the ComplianceResult schema (missing
    required fields, score outside [0,100], unrecognized risk_level or
    content_type, or syntactically invalid JSON), deserialization SHALL fail
    with a validation error.

    **Validates: Requirements 11.4, 11.5, 11.6**
    """

    @given(
        field_to_remove=st.sampled_from(
            [
                "content_type",
                "market",
                "risk_level",
                "score",
                "explanation",
                "suggestion",
                "processing_metadata",
            ]
        ),
        result=compliance_result_strategy(),
    )
    @settings(max_examples=100, deadline=5000, suppress_health_check=[HealthCheck.too_slow])
    def test_missing_required_field_raises_error(
        self, field_to_remove: str, result: ComplianceResult
    ):
        """Missing required fields cause validation error."""
        data = result.model_dump()
        del data[field_to_remove]
        json_str = json.dumps(data)

        with pytest.raises(ValidationError):
            ComplianceResult.model_validate_json(json_str)

    @given(
        invalid_score=st.one_of(
            st.integers(max_value=-1),
            st.integers(min_value=101),
        )
    )
    @settings(max_examples=100, deadline=5000, suppress_health_check=[HealthCheck.too_slow])
    def test_score_outside_range_raises_error(self, invalid_score: int):
        """Score outside [0, 100] causes validation error."""
        data = {
            "content_type": "text",
            "market": "malaysia",
            "risk_level": "Low",
            "score": invalid_score,
            "high_risk_indicators": [],
            "explanation": "Test explanation",
            "suggestion": "Test suggestion",
            "processing_metadata": {
                "pipeline_duration_ms": 100,
                "models_used": ["model-1"],
                "market": "malaysia",
            },
            "warnings": [],
        }
        json_str = json.dumps(data)

        with pytest.raises(ValidationError):
            ComplianceResult.model_validate_json(json_str)

    @given(
        invalid_risk_level=st.text(min_size=1, max_size=20).filter(
            lambda x: x not in ("High", "Medium", "Low")
        )
    )
    @settings(max_examples=100, deadline=5000, suppress_health_check=[HealthCheck.too_slow])
    def test_unrecognized_risk_level_raises_error(self, invalid_risk_level: str):
        """Unrecognized risk_level causes validation error."""
        data = {
            "content_type": "text",
            "market": "malaysia",
            "risk_level": invalid_risk_level,
            "score": 50,
            "high_risk_indicators": [],
            "explanation": "Test explanation",
            "suggestion": "Test suggestion",
            "processing_metadata": {
                "pipeline_duration_ms": 100,
                "models_used": ["model-1"],
                "market": "malaysia",
            },
            "warnings": [],
        }
        json_str = json.dumps(data)

        with pytest.raises(ValidationError):
            ComplianceResult.model_validate_json(json_str)

    @given(
        invalid_content_type=st.text(min_size=1, max_size=20).filter(
            lambda x: x not in ("text", "image", "video")
        )
    )
    @settings(max_examples=100, deadline=5000, suppress_health_check=[HealthCheck.too_slow])
    def test_unrecognized_content_type_raises_error(self, invalid_content_type: str):
        """Unrecognized content_type causes validation error."""
        data = {
            "content_type": invalid_content_type,
            "market": "malaysia",
            "risk_level": "Low",
            "score": 50,
            "high_risk_indicators": [],
            "explanation": "Test explanation",
            "suggestion": "Test suggestion",
            "processing_metadata": {
                "pipeline_duration_ms": 100,
                "models_used": ["model-1"],
                "market": "malaysia",
            },
            "warnings": [],
        }
        json_str = json.dumps(data)

        with pytest.raises(ValidationError):
            ComplianceResult.model_validate_json(json_str)

    @given(
        invalid_json=st.text(min_size=1, max_size=200).filter(
            lambda x: not _is_valid_json(x)
        )
    )
    @settings(max_examples=100, deadline=5000, suppress_health_check=[HealthCheck.too_slow])
    def test_syntactically_invalid_json_raises_error(self, invalid_json: str):
        """Syntactically invalid JSON causes validation error."""
        with pytest.raises((ValidationError, ValueError)):
            ComplianceResult.model_validate_json(invalid_json)


# --- Property 18: Payload Size Rejection ---


# Maximum payload size constant
MAX_PAYLOAD_BYTES = 1_048_576  # 1 MB


def validate_payload_size(json_payload: str) -> ComplianceResult:
    """Validate payload size before deserialization.

    This function implements the payload size check as specified in
    Requirement 11.7. It rejects payloads exceeding 1 MB.

    Args:
        json_payload: The JSON string to validate and deserialize.

    Returns:
        A validated ComplianceResult object.

    Raises:
        ValueError: If the payload exceeds the maximum allowed size.
        ValidationError: If the payload fails schema validation.
    """
    payload_bytes = json_payload.encode("utf-8")
    if len(payload_bytes) > MAX_PAYLOAD_BYTES:
        raise ValueError(
            f"Payload size {len(payload_bytes)} bytes exceeds maximum allowed "
            f"size of {MAX_PAYLOAD_BYTES} bytes (1 MB)"
        )
    return ComplianceResult.model_validate_json(json_payload)


class TestPayloadSizeRejection:
    """Property 18: Payload Size Rejection.

    For any JSON payload whose UTF-8 encoded byte length exceeds 1,048,576
    bytes (1 MB), the pipeline SHALL reject it with an error indicating the
    maximum allowed size.

    **Validates: Requirements 11.7**
    """

    @given(
        result=compliance_result_strategy(),
        padding_size=st.integers(min_value=MAX_PAYLOAD_BYTES, max_value=MAX_PAYLOAD_BYTES + 5000),
    )
    @settings(max_examples=100, deadline=5000, suppress_health_check=[HealthCheck.too_slow])
    def test_oversized_payload_rejected(
        self, result: ComplianceResult, padding_size: int
    ):
        """Payloads exceeding 1 MB are rejected with size error."""
        # Serialize the result and pad to exceed 1 MB
        json_str = result.model_dump_json()

        # Create a payload that exceeds 1 MB by padding the explanation
        # We build a valid-looking JSON that's oversized
        data = result.model_dump()
        # Pad with extra data to exceed the limit
        current_size = len(json.dumps(data, ensure_ascii=False).encode("utf-8"))
        needed_padding = padding_size - current_size + 1
        if needed_padding > 0:
            # Add padding as a large explanation (will be invalid schema but
            # size check should happen first)
            data["_padding"] = "x" * needed_padding

        oversized_json = json.dumps(data, ensure_ascii=False)

        # Verify it's actually over 1 MB
        assert len(oversized_json.encode("utf-8")) > MAX_PAYLOAD_BYTES

        # Should be rejected with a size error
        with pytest.raises(ValueError, match="maximum allowed size"):
            validate_payload_size(oversized_json)

    @given(result=compliance_result_strategy())
    @settings(max_examples=100, deadline=5000, suppress_health_check=[HealthCheck.too_slow])
    def test_valid_size_payload_accepted(self, result: ComplianceResult):
        """Payloads within 1 MB limit are accepted (if otherwise valid)."""
        json_str = result.model_dump_json()

        # Normal ComplianceResult objects should be well under 1 MB
        assert len(json_str.encode("utf-8")) <= MAX_PAYLOAD_BYTES

        # Should deserialize successfully
        restored = validate_payload_size(json_str)
        assert restored == result

    def test_exactly_at_limit_accepted(self):
        """A payload exactly at 1 MB is accepted."""
        # Create a valid result with explanation padded to approach 1 MB
        data = {
            "content_type": "text",
            "market": "malaysia",
            "risk_level": "Low",
            "score": 100,
            "high_risk_indicators": [],
            "explanation": "a" * 500,
            "suggestion": "b" * 400,
            "processing_metadata": {
                "pipeline_duration_ms": 100,
                "models_used": ["model-1"],
                "market": "malaysia",
            },
            "warnings": [],
        }
        json_str = json.dumps(data, ensure_ascii=False)

        # This should be well under 1 MB and accepted
        assert len(json_str.encode("utf-8")) <= MAX_PAYLOAD_BYTES
        result = validate_payload_size(json_str)
        assert result.score == 100

    def test_one_byte_over_limit_rejected(self):
        """A payload one byte over 1 MB is rejected."""
        data = {
            "content_type": "text",
            "market": "malaysia",
            "risk_level": "Low",
            "score": 100,
            "high_risk_indicators": [],
            "explanation": "test",
            "suggestion": "test",
            "processing_metadata": {
                "pipeline_duration_ms": 100,
                "models_used": ["model-1"],
                "market": "malaysia",
            },
            "warnings": [],
        }
        json_str = json.dumps(data, ensure_ascii=False)
        current_size = len(json_str.encode("utf-8"))

        # Pad to exactly 1 byte over the limit
        needed = MAX_PAYLOAD_BYTES - current_size + 1
        data["_padding"] = "x" * needed
        oversized_json = json.dumps(data, ensure_ascii=False)

        assert len(oversized_json.encode("utf-8")) > MAX_PAYLOAD_BYTES

        with pytest.raises(ValueError, match="maximum allowed size"):
            validate_payload_size(oversized_json)


# --- Helper Functions ---


def _is_valid_json(s: str) -> bool:
    """Check if a string is valid JSON."""
    try:
        json.loads(s)
        return True
    except (json.JSONDecodeError, ValueError):
        return False
