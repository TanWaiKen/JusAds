"""Hypothesis strategies for generating GuidelineEntry objects.

Provides strategies for creating valid and invalid GuidelineEntry instances
for property-based testing of cultural guideline validation, ingestion,
and retrieval.

Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7
"""

from hypothesis import strategies as st

from culture_compliance.models.cultural_schemas import (
    AgeGroup,
    CulturalCategory,
    Ethnicity,
    GuidelineEntry,
    Severity,
)


# --- Valid value sets ---

VALID_MARKETS = ["malaysia", "singapore"]
VALID_ETHNICITIES = [e.value for e in Ethnicity]
VALID_AGE_GROUPS = [ag.value for ag in AgeGroup]
VALID_CATEGORIES = [c.value for c in CulturalCategory]
VALID_SEVERITIES = [s.value for s in Severity]

# --- Invalid value sets ---

INVALID_MARKETS = ["indonesia", "thailand", "usa", "uk", "", "Malaysia", "SINGAPORE"]
INVALID_ETHNICITIES = ["european", "african", "mixed", "", "Malay", "CHINESE"]
INVALID_AGE_GROUPS = ["teens", "elderly", "young_adults", "", "All_Ages", "CHILDREN"]
INVALID_CATEGORIES = [
    "violence",
    "politics",
    "profanity",
    "",
    "Body_Exposure",
    "FOOD_TABOOS",
]
INVALID_SEVERITIES = ["critical", "warning", "info", "", "High", "MEDIUM"]


# --- Base field strategies ---


def valid_market_strategy():
    """Strategy for valid market values."""
    return st.sampled_from(VALID_MARKETS)


def valid_ethnicity_strategy():
    """Strategy for valid ethnicity values."""
    return st.sampled_from(VALID_ETHNICITIES)


def valid_age_group_strategy():
    """Strategy for valid age_group values."""
    return st.sampled_from(VALID_AGE_GROUPS)


def valid_category_strategy():
    """Strategy for valid cultural category values."""
    return st.sampled_from(VALID_CATEGORIES)


def valid_severity_strategy():
    """Strategy for valid severity values."""
    return st.sampled_from(VALID_SEVERITIES)


def valid_guideline_text_strategy():
    """Strategy for valid guideline_text (1-500 characters, non-empty).

    Generates readable text strings between 1 and 500 characters.
    """
    return st.text(
        alphabet=st.characters(categories=("L", "N", "P", "Z", "S")),
        min_size=1,
        max_size=500,
    ).filter(lambda s: s.strip())


def invalid_guideline_text_strategy():
    """Strategy for invalid guideline_text (>500 characters)."""
    return st.text(
        alphabet=st.characters(categories=("L", "N", "P", "Z")),
        min_size=501,
        max_size=1000,
    )


# --- GuidelineEntry strategies ---


def valid_guideline_entry_strategy():
    """Strategy for generating valid GuidelineEntry instances.

    All fields are drawn from their respective valid value sets.
    The guideline_text is between 1 and 500 characters.

    Returns:
        A Hypothesis strategy producing GuidelineEntry instances.
    """
    return st.builds(
        GuidelineEntry,
        market=valid_market_strategy(),
        ethnicity=valid_ethnicity_strategy(),
        age_group=valid_age_group_strategy(),
        category=valid_category_strategy(),
        severity=valid_severity_strategy(),
        guideline_text=valid_guideline_text_strategy(),
    )


def valid_guideline_entry_dict_strategy():
    """Strategy for generating valid GuidelineEntry as dict kwargs.

    Useful for testing construction and serialization without
    instantiating the model directly.

    Returns:
        A Hypothesis strategy producing dicts with GuidelineEntry field values.
    """
    return st.fixed_dictionaries({
        "market": valid_market_strategy(),
        "ethnicity": valid_ethnicity_strategy(),
        "age_group": valid_age_group_strategy(),
        "category": valid_category_strategy(),
        "severity": valid_severity_strategy(),
        "guideline_text": valid_guideline_text_strategy(),
    })


def invalid_guideline_entry_strategy():
    """Strategy for generating GuidelineEntry dicts with at least one invalid field.

    Each generated dict has exactly one field set to an invalid value,
    with all other fields valid. This ensures targeted validation testing.

    Returns:
        A Hypothesis strategy producing dicts with one invalid field and
        a 'violation' key indicating which field is invalid.
    """
    # Invalid market
    invalid_market = st.fixed_dictionaries({
        "market": st.sampled_from(INVALID_MARKETS),
        "ethnicity": valid_ethnicity_strategy(),
        "age_group": valid_age_group_strategy(),
        "category": valid_category_strategy(),
        "severity": valid_severity_strategy(),
        "guideline_text": valid_guideline_text_strategy(),
        "violation": st.just("market"),
    })

    # Invalid ethnicity
    invalid_ethnicity = st.fixed_dictionaries({
        "market": valid_market_strategy(),
        "ethnicity": st.sampled_from(INVALID_ETHNICITIES),
        "age_group": valid_age_group_strategy(),
        "category": valid_category_strategy(),
        "severity": valid_severity_strategy(),
        "guideline_text": valid_guideline_text_strategy(),
        "violation": st.just("ethnicity"),
    })

    # Invalid age_group
    invalid_age_group = st.fixed_dictionaries({
        "market": valid_market_strategy(),
        "ethnicity": valid_ethnicity_strategy(),
        "age_group": st.sampled_from(INVALID_AGE_GROUPS),
        "category": valid_category_strategy(),
        "severity": valid_severity_strategy(),
        "guideline_text": valid_guideline_text_strategy(),
        "violation": st.just("age_group"),
    })

    # Invalid category
    invalid_category = st.fixed_dictionaries({
        "market": valid_market_strategy(),
        "ethnicity": valid_ethnicity_strategy(),
        "age_group": valid_age_group_strategy(),
        "category": st.sampled_from(INVALID_CATEGORIES),
        "severity": valid_severity_strategy(),
        "guideline_text": valid_guideline_text_strategy(),
        "violation": st.just("category"),
    })

    # Invalid severity
    invalid_severity = st.fixed_dictionaries({
        "market": valid_market_strategy(),
        "ethnicity": valid_ethnicity_strategy(),
        "age_group": valid_age_group_strategy(),
        "category": valid_category_strategy(),
        "severity": st.sampled_from(INVALID_SEVERITIES),
        "guideline_text": valid_guideline_text_strategy(),
        "violation": st.just("severity"),
    })

    # Invalid guideline_text (too long)
    invalid_text = st.fixed_dictionaries({
        "market": valid_market_strategy(),
        "ethnicity": valid_ethnicity_strategy(),
        "age_group": valid_age_group_strategy(),
        "category": valid_category_strategy(),
        "severity": valid_severity_strategy(),
        "guideline_text": invalid_guideline_text_strategy(),
        "violation": st.just("guideline_text"),
    })

    return st.one_of(
        invalid_market,
        invalid_ethnicity,
        invalid_age_group,
        invalid_category,
        invalid_severity,
        invalid_text,
    )
