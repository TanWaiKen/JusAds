"""Hypothesis strategies for generating ComplianceResult and related output models.

Provides strategies for creating valid instances of ComplianceResult,
ProcessingMetadata, PipelineWarning, and issue location models for
property-based testing.

Validates: Requirements 10.3
"""

import string

from hypothesis import strategies as st

from culture_compliance.models.schemas import (
    ComplianceResult,
    ContentType,
    ImageIssueLocation,
    Market,
    PipelineWarning,
    ProcessingMetadata,
    TextIssueLocation,
    VideoIssueLocation,
)


# --- Shared constants ---

VIOLATION_CATEGORIES = [
    "Religious Sensitivity",
    "Ethnic/Racial",
    "Sexual/Explicit",
    "Political/State",
    "LGBTQ",
    "Profanity",
]

SEVERITY_LEVELS = ["Severe", "Moderate", "Minor"]

RISK_LEVELS = ["High", "Medium", "Low"]

GUIDELINE_SOURCES = ["regulatory", "cultural"]


# --- Issue Location strategies ---


def guideline_source_strategy():
    """Strategy for valid guideline_source values.

    Returns:
        A Hypothesis strategy producing either "regulatory" or "cultural".
    """
    return st.sampled_from(GUIDELINE_SOURCES)


def text_issue_location_strategy(guideline_source=None):
    """Strategy for generating valid TextIssueLocation objects.

    Args:
        guideline_source: Optional override for guideline_source field.
    """
    return st.builds(
        TextIssueLocation,
        phrase=st.text(
            alphabet=st.characters(categories=("L", "N", "P", "Z")),
            min_size=1,
            max_size=200,
        ).filter(lambda s: s.strip()),
        char_offset=st.integers(min_value=0, max_value=10000),
        category=st.sampled_from(VIOLATION_CATEGORIES),
        severity=st.sampled_from(SEVERITY_LEVELS),
        guideline_source=guideline_source or guideline_source_strategy(),
    )


def image_issue_location_strategy(guideline_source=None):
    """Strategy for generating valid ImageIssueLocation objects.

    Args:
        guideline_source: Optional override for guideline_source field.
    """
    return st.builds(
        ImageIssueLocation,
        bounding_box=st.fixed_dictionaries({
            "x": st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            "y": st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            "width": st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            "height": st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        }),
        description=st.text(
            alphabet=st.characters(categories=("L", "N", "P", "Z")),
            min_size=1,
            max_size=200,
        ).filter(lambda s: s.strip()),
        category=st.sampled_from(VIOLATION_CATEGORIES),
        severity=st.sampled_from(SEVERITY_LEVELS),
        guideline_source=guideline_source or guideline_source_strategy(),
    )


def video_issue_location_strategy(guideline_source=None):
    """Strategy for generating valid VideoIssueLocation objects.

    Args:
        guideline_source: Optional override for guideline_source field.
    """
    return st.builds(
        VideoIssueLocation,
        timestamp=st.from_regex(r"[0-9]{2}:[0-9]{2}", fullmatch=True),
        description=st.text(
            alphabet=st.characters(categories=("L", "N", "P", "Z")),
            min_size=1,
            max_size=200,
        ).filter(lambda s: s.strip()),
        category=st.sampled_from(VIOLATION_CATEGORIES),
        severity=st.sampled_from(SEVERITY_LEVELS),
        guideline_source=guideline_source or guideline_source_strategy(),
    )


# --- Supporting model strategies ---


def processing_metadata_strategy():
    """Strategy for generating valid ProcessingMetadata objects."""
    return st.builds(
        ProcessingMetadata,
        pipeline_duration_ms=st.integers(min_value=0, max_value=300000),
        models_used=st.lists(
            st.text(
                alphabet=string.ascii_letters + string.digits + "-.",
                min_size=1,
                max_size=50,
            ),
            min_size=1,
            max_size=5,
        ),
        market=st.sampled_from(["malaysia", "singapore"]),
    )


def pipeline_warning_strategy():
    """Strategy for generating valid PipelineWarning objects."""
    return st.builds(
        PipelineWarning,
        step_name=st.text(
            alphabet=string.ascii_lowercase + "_",
            min_size=1,
            max_size=50,
        ).filter(lambda s: s.strip()),
        description=st.text(
            alphabet=st.characters(categories=("L", "N", "P", "Z")),
            min_size=1,
            max_size=200,
        ).filter(lambda s: s.strip()),
        result_may_be_incomplete=st.booleans(),
    )


# --- ComplianceResult strategy ---


def _high_risk_indicators_strategy():
    """Strategy for generating a list of mixed issue location objects (max 10)."""
    return st.lists(
        st.one_of(
            text_issue_location_strategy(),
            image_issue_location_strategy(),
            video_issue_location_strategy(),
        ),
        min_size=0,
        max_size=10,
    )


def compliance_result_strategy(
    content_type=None,
    market=None,
    risk_level=None,
    score=None,
):
    """Strategy for generating valid ComplianceResult objects.

    Args:
        content_type: Optional fixed content type.
        market: Optional fixed market.
        risk_level: Optional fixed risk level.
        score: Optional fixed score.

    Returns:
        A Hypothesis strategy producing ComplianceResult instances.
    """
    return st.builds(
        ComplianceResult,
        content_type=content_type or st.sampled_from(list(ContentType)),
        market=market or st.sampled_from(list(Market)),
        risk_level=risk_level or st.sampled_from(RISK_LEVELS),
        score=score or st.integers(min_value=0, max_value=100),
        high_risk_indicators=_high_risk_indicators_strategy(),
        explanation=st.text(
            alphabet=st.characters(categories=("L", "N", "P", "Z", "S")),
            min_size=1,
            max_size=500,
        ).filter(lambda s: s.strip()),
        suggestion=st.text(
            alphabet=st.characters(categories=("L", "N", "P", "Z", "S")),
            min_size=1,
            max_size=400,
        ).filter(lambda s: s.strip()),
        processing_metadata=processing_metadata_strategy(),
        warnings=st.lists(pipeline_warning_strategy(), min_size=0, max_size=3),
    )
