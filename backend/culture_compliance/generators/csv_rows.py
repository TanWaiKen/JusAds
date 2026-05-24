"""Hypothesis strategies for generating CSV row data for cultural guideline ingestion.

Provides strategies for creating valid and invalid CSV row dicts, as well as
mixed CSV content (lists of valid + invalid rows) for property-based testing
of the cultural guideline ingestion pipeline.

Validates: Requirements 8.1, 8.2, 8.3
"""

from hypothesis import strategies as st

from culture_compliance.generators.cultural_guidelines import (
    INVALID_AGE_GROUPS,
    INVALID_CATEGORIES,
    INVALID_ETHNICITIES,
    INVALID_MARKETS,
    INVALID_SEVERITIES,
    valid_age_group_strategy,
    valid_category_strategy,
    valid_ethnicity_strategy,
    valid_guideline_text_strategy,
    valid_market_strategy,
    valid_severity_strategy,
)


# --- CSV field names ---

CSV_FIELDS = ["market", "ethnicity", "age_group", "category", "severity", "guideline_text"]


# --- Valid CSV row strategies ---


def valid_csv_row_strategy():
    """Strategy for generating a valid CSV row dict.

    All fields are present and contain valid values matching the
    GuidelineEntry schema.

    Returns:
        A Hypothesis strategy producing dicts with all CSV_FIELDS keys
        and valid values.
    """
    return st.fixed_dictionaries({
        "market": valid_market_strategy(),
        "ethnicity": valid_ethnicity_strategy(),
        "age_group": valid_age_group_strategy(),
        "category": valid_category_strategy(),
        "severity": valid_severity_strategy(),
        "guideline_text": valid_guideline_text_strategy(),
    })


# --- Invalid CSV row strategies ---


def _missing_field_row_strategy():
    """Strategy for CSV rows with one or more missing fields.

    Generates a valid row then removes 1-3 random fields.
    """
    @st.composite
    def _build(draw):
        row = draw(valid_csv_row_strategy())
        # Remove 1 to 3 fields
        fields_to_remove = draw(
            st.lists(
                st.sampled_from(CSV_FIELDS),
                min_size=1,
                max_size=3,
                unique=True,
            )
        )
        for field in fields_to_remove:
            del row[field]
        return {**row, "violation": "missing_fields", "missing": fields_to_remove}

    return _build()


def _invalid_value_row_strategy():
    """Strategy for CSV rows with an invalid field value.

    All fields are present but one has an invalid value.
    """
    invalid_market_row = st.fixed_dictionaries({
        "market": st.sampled_from(INVALID_MARKETS),
        "ethnicity": valid_ethnicity_strategy(),
        "age_group": valid_age_group_strategy(),
        "category": valid_category_strategy(),
        "severity": valid_severity_strategy(),
        "guideline_text": valid_guideline_text_strategy(),
        "violation": st.just("invalid_value"),
        "invalid_field": st.just("market"),
    })

    invalid_ethnicity_row = st.fixed_dictionaries({
        "market": valid_market_strategy(),
        "ethnicity": st.sampled_from(INVALID_ETHNICITIES),
        "age_group": valid_age_group_strategy(),
        "category": valid_category_strategy(),
        "severity": valid_severity_strategy(),
        "guideline_text": valid_guideline_text_strategy(),
        "violation": st.just("invalid_value"),
        "invalid_field": st.just("ethnicity"),
    })

    invalid_age_group_row = st.fixed_dictionaries({
        "market": valid_market_strategy(),
        "ethnicity": valid_ethnicity_strategy(),
        "age_group": st.sampled_from(INVALID_AGE_GROUPS),
        "category": valid_category_strategy(),
        "severity": valid_severity_strategy(),
        "guideline_text": valid_guideline_text_strategy(),
        "violation": st.just("invalid_value"),
        "invalid_field": st.just("age_group"),
    })

    invalid_category_row = st.fixed_dictionaries({
        "market": valid_market_strategy(),
        "ethnicity": valid_ethnicity_strategy(),
        "age_group": valid_age_group_strategy(),
        "category": st.sampled_from(INVALID_CATEGORIES),
        "severity": valid_severity_strategy(),
        "guideline_text": valid_guideline_text_strategy(),
        "violation": st.just("invalid_value"),
        "invalid_field": st.just("category"),
    })

    invalid_severity_row = st.fixed_dictionaries({
        "market": valid_market_strategy(),
        "ethnicity": valid_ethnicity_strategy(),
        "age_group": valid_age_group_strategy(),
        "category": valid_category_strategy(),
        "severity": st.sampled_from(INVALID_SEVERITIES),
        "guideline_text": valid_guideline_text_strategy(),
        "violation": st.just("invalid_value"),
        "invalid_field": st.just("severity"),
    })

    return st.one_of(
        invalid_market_row,
        invalid_ethnicity_row,
        invalid_age_group_row,
        invalid_category_row,
        invalid_severity_row,
    )


def invalid_csv_row_strategy():
    """Strategy for generating an invalid CSV row dict.

    Generates rows that are invalid due to either missing fields or
    invalid field values.

    Returns:
        A Hypothesis strategy producing dicts with a 'violation' key
        indicating the type of invalidity.
    """
    return st.one_of(
        _missing_field_row_strategy(),
        _invalid_value_row_strategy(),
    )


# --- Mixed CSV content strategies ---


@st.composite
def mixed_csv_content_strategy(draw, min_valid=1, max_valid=10, min_invalid=1, max_invalid=5):
    """Strategy for generating mixed CSV content with valid and invalid rows.

    Produces a list of row dicts where some are valid and some are invalid,
    simulating realistic CSV files with data quality issues.

    Args:
        min_valid: Minimum number of valid rows.
        max_valid: Maximum number of valid rows.
        min_invalid: Minimum number of invalid rows.
        max_invalid: Maximum number of invalid rows.

    Returns:
        A dict with:
        - 'rows': list of all row dicts (mixed order)
        - 'valid_count': number of valid rows
        - 'invalid_count': number of invalid rows
    """
    valid_rows = draw(
        st.lists(valid_csv_row_strategy(), min_size=min_valid, max_size=max_valid)
    )
    invalid_rows = draw(
        st.lists(invalid_csv_row_strategy(), min_size=min_invalid, max_size=max_invalid)
    )

    # Tag rows for tracking
    tagged_valid = [{"is_valid": True, **row} for row in valid_rows]
    tagged_invalid = [{"is_valid": False, **row} for row in invalid_rows]

    # Combine and shuffle
    all_rows = tagged_valid + tagged_invalid
    shuffled = draw(st.permutations(all_rows))

    return {
        "rows": list(shuffled),
        "valid_count": len(valid_rows),
        "invalid_count": len(invalid_rows),
    }
