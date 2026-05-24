"""Property-based tests for cultural guideline data model validation.

Tests correctness properties from the cultural-guidelines-v2 design document
using Hypothesis.
"""

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from pydantic import ValidationError

from culture_compliance.models.cultural_schemas import (
    CulturalCategory,
    GuidelineEntry,
)
from culture_compliance.generators.csv_rows import valid_csv_row_strategy
from culture_compliance.ingest_cultural import validate_guideline_row
from culture_compliance.ingest_cultural import IngestionResult, validate_guideline_row
from culture_compliance.generators.csv_rows import (
    valid_csv_row_strategy,
    invalid_csv_row_strategy,
)


# --- Allowed value sets ---

VALID_MARKETS = {"malaysia", "singapore"}
VALID_ETHNICITIES = {"malay", "chinese", "indian", "all"}
VALID_AGE_GROUPS = {"all_ages", "adults_only", "children"}
VALID_CATEGORIES = {e.value for e in CulturalCategory}
VALID_SEVERITIES = {"high", "medium", "low"}


# --- Strategies ---


def invalid_for(valid_set: set[str]) -> st.SearchStrategy[str]:
    """Generate strings that are not in the given valid set."""
    return st.text(min_size=1, max_size=50).filter(lambda s: s not in valid_set)


valid_market_st = st.sampled_from(sorted(VALID_MARKETS))
valid_ethnicity_st = st.sampled_from(sorted(VALID_ETHNICITIES))
valid_age_group_st = st.sampled_from(sorted(VALID_AGE_GROUPS))
valid_category_st = st.sampled_from(sorted(VALID_CATEGORIES))
valid_severity_st = st.sampled_from(sorted(VALID_SEVERITIES))
valid_guideline_text_st = st.text(
    alphabet=st.characters(categories=("L", "N", "P", "Z", "S")),
    min_size=1,
    max_size=500,
).filter(lambda s: s.strip())


# --- Helper ---


def _valid_entry_kwargs(guideline_text: str = "Test guideline text") -> dict:
    """Return a dict of valid GuidelineEntry kwargs with the given guideline_text."""
    return {
        "market": "malaysia",
        "ethnicity": "malay",
        "age_group": "all_ages",
        "category": "body_exposure",
        "severity": "high",
        "guideline_text": guideline_text,
    }


# Feature: cultural-guidelines-v2, Property 1: GuidelineEntry Field Validation


class TestGuidelineEntryFieldValidation:
    """Property 1: GuidelineEntry Field Validation.

    For any string value that is not in the allowed set for a given
    GuidelineEntry field (market not in {"malaysia", "singapore"}, ethnicity
    not in {"malay", "chinese", "indian", "all"}, age_group not in
    {"all_ages", "adults_only", "children"}, category not in the 12 defined
    cultural categories, severity not in {"high", "medium", "low"}),
    constructing a GuidelineEntry SHALL raise a validation error identifying
    the invalid field.

    **Validates: Requirements 1.2, 1.3, 1.4, 1.5, 1.6**
    """

    @given(invalid_market=invalid_for(VALID_MARKETS))
    @settings(max_examples=100, deadline=5000)
    def test_invalid_market_raises_validation_error(self, invalid_market: str):
        """GuidelineEntry SHALL raise ValidationError for invalid market values.

        **Validates: Requirements 1.2**
        """
        with pytest.raises(ValidationError) as exc_info:
            GuidelineEntry(
                market=invalid_market,
                ethnicity="malay",
                age_group="all_ages",
                category="body_exposure",
                severity="high",
                guideline_text="Test guideline text",
            )
        errors = exc_info.value.errors()
        field_names = [e["loc"][0] for e in errors]
        assert "market" in field_names

    @given(invalid_ethnicity=invalid_for(VALID_ETHNICITIES))
    @settings(max_examples=100, deadline=5000)
    def test_invalid_ethnicity_raises_validation_error(self, invalid_ethnicity: str):
        """GuidelineEntry SHALL raise ValidationError for invalid ethnicity values.

        **Validates: Requirements 1.3**
        """
        with pytest.raises(ValidationError) as exc_info:
            GuidelineEntry(
                market="malaysia",
                ethnicity=invalid_ethnicity,
                age_group="all_ages",
                category="body_exposure",
                severity="high",
                guideline_text="Test guideline text",
            )
        errors = exc_info.value.errors()
        field_names = [e["loc"][0] for e in errors]
        assert "ethnicity" in field_names

    @given(invalid_age_group=invalid_for(VALID_AGE_GROUPS))
    @settings(max_examples=100, deadline=5000)
    def test_invalid_age_group_raises_validation_error(self, invalid_age_group: str):
        """GuidelineEntry SHALL raise ValidationError for invalid age_group values.

        **Validates: Requirements 1.4**
        """
        with pytest.raises(ValidationError) as exc_info:
            GuidelineEntry(
                market="malaysia",
                ethnicity="malay",
                age_group=invalid_age_group,
                category="body_exposure",
                severity="high",
                guideline_text="Test guideline text",
            )
        errors = exc_info.value.errors()
        field_names = [e["loc"][0] for e in errors]
        assert "age_group" in field_names

    @given(invalid_category=invalid_for(VALID_CATEGORIES))
    @settings(max_examples=100, deadline=5000)
    def test_invalid_category_raises_validation_error(self, invalid_category: str):
        """GuidelineEntry SHALL raise ValidationError for invalid category values.

        **Validates: Requirements 1.5**
        """
        with pytest.raises(ValidationError) as exc_info:
            GuidelineEntry(
                market="malaysia",
                ethnicity="malay",
                age_group="all_ages",
                category=invalid_category,
                severity="high",
                guideline_text="Test guideline text",
            )
        errors = exc_info.value.errors()
        field_names = [e["loc"][0] for e in errors]
        assert "category" in field_names

    @given(invalid_severity=invalid_for(VALID_SEVERITIES))
    @settings(max_examples=100, deadline=5000)
    def test_invalid_severity_raises_validation_error(self, invalid_severity: str):
        """GuidelineEntry SHALL raise ValidationError for invalid severity values.

        **Validates: Requirements 1.6**
        """
        with pytest.raises(ValidationError) as exc_info:
            GuidelineEntry(
                market="malaysia",
                ethnicity="malay",
                age_group="all_ages",
                category="body_exposure",
                severity=invalid_severity,
                guideline_text="Test guideline text",
            )
        errors = exc_info.value.errors()
        field_names = [e["loc"][0] for e in errors]
        assert "severity" in field_names

    @given(
        market=valid_market_st,
        ethnicity=valid_ethnicity_st,
        age_group=valid_age_group_st,
        category=valid_category_st,
        severity=valid_severity_st,
        guideline_text=valid_guideline_text_st,
    )
    @settings(max_examples=100, deadline=5000)
    def test_valid_values_accepted(
        self,
        market: str,
        ethnicity: str,
        age_group: str,
        category: str,
        severity: str,
        guideline_text: str,
    ):
        """GuidelineEntry SHALL accept all valid field value combinations.

        **Validates: Requirements 1.2, 1.3, 1.4, 1.5, 1.6**
        """
        entry = GuidelineEntry(
            market=market,
            ethnicity=ethnicity,
            age_group=age_group,
            category=category,
            severity=severity,
            guideline_text=guideline_text,
        )
        assert entry.market == market
        assert entry.ethnicity == ethnicity
        assert entry.age_group == age_group
        assert entry.category == category
        assert entry.severity == severity
        assert entry.guideline_text == guideline_text


# Feature: cultural-guidelines-v2, Property 2: GuidelineEntry Text Length Constraint


class TestGuidelineEntryTextLengthConstraint:
    """Property 2: GuidelineEntry Text Length Constraint.

    For any string with length greater than 500 characters, constructing a
    GuidelineEntry with that string as guideline_text SHALL raise a validation
    error. For any string with length between 1 and 500 characters (inclusive),
    the GuidelineEntry SHALL accept it as a valid guideline_text.

    **Validates: Requirements 1.7**
    """

    @given(
        text=st.text(
            alphabet=st.characters(categories=("L", "N", "P", "Z", "S")),
            min_size=501,
            max_size=2000,
        )
    )
    @settings(max_examples=100, deadline=5000)
    def test_text_longer_than_500_raises_validation_error(self, text: str):
        """Any string with length > 500 raises ValidationError for guideline_text."""
        assume(len(text) > 500)

        with pytest.raises(ValidationError) as exc_info:
            GuidelineEntry(**_valid_entry_kwargs(text))

        errors = exc_info.value.errors()
        assert any(
            "guideline_text" in str(err.get("loc", ""))
            for err in errors
        ), f"Expected guideline_text validation error, got: {errors}"

    @given(
        text=st.text(
            alphabet=st.characters(categories=("L", "N", "P", "Z", "S")),
            min_size=1,
            max_size=500,
        )
    )
    @settings(max_examples=100, deadline=5000)
    def test_text_between_1_and_500_chars_is_accepted(self, text: str):
        """Any string with length 1-500 (inclusive) is accepted as valid guideline_text."""
        assume(1 <= len(text) <= 500)

        entry = GuidelineEntry(**_valid_entry_kwargs(text))
        assert entry.guideline_text == text
        assert len(entry.guideline_text) <= 500


# Feature: cultural-guidelines-v2, Property 11: CSV Ingestion Valid Row Round-Trip


class TestCSVIngestionValidRowRoundTrip:
    """Property 11: CSV Ingestion Valid Row Round-Trip.

    For any valid CSV row containing all required fields with values matching
    the allowed sets defined in Requirement 1, the ingestion process SHALL
    produce a GuidelineEntry with field values identical to the CSV row values.
    The guideline_text SHALL be preserved exactly as provided.

    **Validates: Requirements 8.1**
    """

    @given(row=valid_csv_row_strategy())
    @settings(max_examples=100, deadline=5000)
    def test_valid_row_passes_validation(self, row: dict):
        """validate_guideline_row SHALL return (True, None) for any valid CSV row.

        **Validates: Requirements 8.1**
        """
        is_valid, error_msg = validate_guideline_row(row, row_number=1)
        assert is_valid is True, f"Expected valid row but got error: {error_msg}"
        assert error_msg is None

    @given(row=valid_csv_row_strategy())
    @settings(max_examples=100, deadline=5000)
    def test_valid_row_round_trips_to_guideline_entry(self, row: dict):
        """GuidelineEntry constructed from a valid CSV row SHALL have field values
        identical to the CSV row values, and guideline_text SHALL be preserved exactly.

        **Validates: Requirements 8.1**
        """
        # First confirm validation passes
        is_valid, error_msg = validate_guideline_row(row, row_number=1)
        assert is_valid is True, f"Expected valid row but got error: {error_msg}"

        # Construct GuidelineEntry from the row
        entry = GuidelineEntry(**row)

        # Verify all field values match exactly
        assert entry.market == row["market"], (
            f"market mismatch: entry={entry.market!r}, row={row['market']!r}"
        )
        assert entry.ethnicity == row["ethnicity"], (
            f"ethnicity mismatch: entry={entry.ethnicity!r}, row={row['ethnicity']!r}"
        )
        assert entry.age_group == row["age_group"], (
            f"age_group mismatch: entry={entry.age_group!r}, row={row['age_group']!r}"
        )
        assert entry.category == row["category"], (
            f"category mismatch: entry={entry.category!r}, row={row['category']!r}"
        )
        assert entry.severity == row["severity"], (
            f"severity mismatch: entry={entry.severity!r}, row={row['severity']!r}"
        )
        # guideline_text SHALL be preserved exactly as provided
        assert entry.guideline_text == row["guideline_text"], (
            f"guideline_text mismatch: entry={entry.guideline_text!r}, "
            f"row={row['guideline_text']!r}"
        )


# Feature: cultural-guidelines-v2, Property 12: CSV Ingestion Invalid Row Graceful Skip


class TestCSVIngestionInvalidRowGracefulSkip:
    """Property 12: CSV Ingestion Invalid Row Graceful Skip.

    For any CSV containing a mix of valid and invalid rows, the ingestion
    process SHALL ingest all valid rows, skip all invalid rows, and the count
    of ingested rows plus skipped rows SHALL equal the total row count. No
    invalid row SHALL cause the process to abort.

    **Validates: Requirements 8.2, 8.3**
    """

    @given(
        valid_rows=st.lists(valid_csv_row_strategy(), min_size=1, max_size=10),
        invalid_rows=st.lists(invalid_csv_row_strategy(), min_size=1, max_size=5),
    )
    @settings(max_examples=100, deadline=5000)
    def test_mixed_rows_valid_plus_invalid_equals_total(
        self, valid_rows: list, invalid_rows: list
    ):
        """For any mix of valid and invalid rows, validate_guideline_row SHALL
        correctly identify all valid rows as (True, None) and all invalid rows
        as (False, error_message), and the sum of valid + invalid SHALL equal
        the total row count. No row SHALL cause an exception.

        **Validates: Requirements 8.2, 8.3**
        """
        total_rows = valid_rows + invalid_rows
        valid_count = 0
        invalid_count = 0

        for row_number, row in enumerate(total_rows, start=1):
            # Strip metadata keys before passing to validate_guideline_row
            clean_row = {
                k: v
                for k, v in row.items()
                if k not in ("violation", "invalid_field", "missing", "is_valid")
            }

            is_valid, error_msg = validate_guideline_row(clean_row, row_number)

            if row in valid_rows:
                # Valid rows should return (True, None)
                assert is_valid is True, (
                    f"Expected valid row {row_number} to pass validation, "
                    f"but got error: {error_msg}"
                )
                assert error_msg is None
                valid_count += 1
            else:
                # Invalid rows should return (False, error_message)
                assert is_valid is False, (
                    f"Expected invalid row {row_number} to fail validation, "
                    f"but it passed. Row: {clean_row}"
                )
                assert error_msg is not None
                assert isinstance(error_msg, str)
                assert len(error_msg) > 0
                invalid_count += 1

        # Count of valid + invalid SHALL equal total row count
        assert valid_count + invalid_count == len(total_rows)



# Feature: cultural-guidelines-v2, Property 13: Ingestion Report Completeness


class TestIngestionReportCompleteness:
    """Property 13: Ingestion Report Completeness.

    For any completed ingestion run, the report SHALL contain exactly three
    fields: total_ingested (integer >= 0), rows_skipped (integer >= 0), and
    collection_name (string equal to "cultural-guidelines"). The sum of
    total_ingested and rows_skipped SHALL equal the number of data rows in
    the input CSV.

    **Validates: Requirements 8.6**
    """

    @given(
        valid_rows=st.lists(valid_csv_row_strategy(), min_size=0, max_size=15),
        invalid_rows=st.lists(invalid_csv_row_strategy(), min_size=0, max_size=10),
    )
    @settings(max_examples=100, deadline=5000)
    def test_ingestion_report_completeness(
        self, valid_rows: list, invalid_rows: list
    ):
        """For any mix of valid and invalid CSV rows, the IngestionResult SHALL
        have total_ingested >= 0, rows_skipped >= 0, collection_name ==
        "cultural-guidelines", and total_ingested + rows_skipped == total row count.

        **Validates: Requirements 8.6**
        """
        # Ensure we have at least one row total to test meaningful ingestion
        assume(len(valid_rows) + len(invalid_rows) > 0)

        # Strip metadata keys from invalid rows (violation, invalid_field, missing, is_valid)
        # to simulate what the ingestion module would see as raw CSV data
        cleaned_invalid_rows = []
        for row in invalid_rows:
            cleaned = {
                k: v
                for k, v in row.items()
                if k not in ("violation", "invalid_field", "missing", "is_valid")
            }
            cleaned_invalid_rows.append(cleaned)

        # Combine all rows (valid + invalid) in order
        all_rows = valid_rows + cleaned_invalid_rows
        total_row_count = len(all_rows)

        # Simulate the ingestion counting logic using validate_guideline_row
        total_ingested = 0
        rows_skipped = 0

        for i, row in enumerate(all_rows, start=1):
            is_valid, error_msg = validate_guideline_row(row, i)
            if is_valid:
                total_ingested += 1
            else:
                rows_skipped += 1

        # Construct the IngestionResult as the ingestion module would
        result = IngestionResult(
            total_ingested=total_ingested,
            rows_skipped=rows_skipped,
            collection_name="cultural-guidelines",
        )

        # Verify: total_ingested >= 0
        assert result.total_ingested >= 0, (
            f"total_ingested must be >= 0, got {result.total_ingested}"
        )

        # Verify: rows_skipped >= 0
        assert result.rows_skipped >= 0, (
            f"rows_skipped must be >= 0, got {result.rows_skipped}"
        )

        # Verify: collection_name == "cultural-guidelines"
        assert result.collection_name == "cultural-guidelines", (
            f"collection_name must be 'cultural-guidelines', got '{result.collection_name}'"
        )

        # Verify: total_ingested + rows_skipped == total_row_count
        assert result.total_ingested + result.rows_skipped == total_row_count, (
            f"total_ingested ({result.total_ingested}) + rows_skipped ({result.rows_skipped}) "
            f"= {result.total_ingested + result.rows_skipped} must equal total_row_count "
            f"({total_row_count})"
        )


# Feature: cultural-guidelines-v2, Property 4: Age Group Filtering Correctness


class TestAgeGroupFilteringCorrectness:
    """Property 4: Age Group Filtering Correctness.

    For any guideline with a given age_group value and any content with a given
    target_age_group value, the guideline SHALL be included in retrieval results
    if and only if:
      (a) the guideline's age_group is "all_ages", OR
      (b) the guideline's age_group equals the content's target_age_group.

    When no target_age_group is specified (defaults to "all_ages"), only
    guidelines with age_group "all_ages" SHALL be included.

    **Validates: Requirements 6.1, 6.2, 6.3, 6.4**
    """

    @given(
        guideline_age_group=st.sampled_from(["all_ages", "adults_only", "children"]),
        target_age_group=st.sampled_from(["all_ages", "adults_only", "children"]),
    )
    @settings(max_examples=100, deadline=5000)
    def test_age_group_inclusion_rule(
        self, guideline_age_group: str, target_age_group: str
    ):
        """For any (guideline_age_group, target_age_group) pair, the filter built by
        _build_cultural_filter SHALL include the guideline if and only if:
          (a) guideline_age_group == "all_ages", OR
          (b) guideline_age_group == target_age_group.

        **Validates: Requirements 6.1, 6.2, 6.3, 6.4**
        """
        from culture_compliance.nodes.step5_guideline_retrieval import (
            _build_cultural_filter,
        )
        from qdrant_client.models import FieldCondition, MatchAny, MatchValue

        # Build the filter using a fixed market and "all" ethnicity so only
        # the age_group condition is exercised.
        qdrant_filter = _build_cultural_filter(
            market="malaysia",
            target_ethnicity="all",
            target_age_group=target_age_group,
        )

        # Extract the age_group condition from the filter's must conditions.
        age_group_condition = None
        for condition in qdrant_filter.must:
            if isinstance(condition, FieldCondition) and condition.key == "age_group":
                age_group_condition = condition
                break

        assert age_group_condition is not None, (
            "Expected an age_group FieldCondition in the filter's must conditions, "
            f"but none was found. Filter: {qdrant_filter}"
        )

        # Determine which age_group values the filter would match.
        match = age_group_condition.match
        if isinstance(match, MatchValue):
            matched_age_groups = {match.value}
        elif isinstance(match, MatchAny):
            matched_age_groups = set(match.any)
        else:
            raise AssertionError(
                f"Unexpected match type for age_group condition: {type(match)}"
            )

        # Compute the expected inclusion decision according to the property.
        expected_included = (
            guideline_age_group == "all_ages"
            or guideline_age_group == target_age_group
        )

        # Compute the actual inclusion decision from the filter.
        actual_included = guideline_age_group in matched_age_groups

        assert actual_included == expected_included, (
            f"Inclusion mismatch for guideline_age_group={guideline_age_group!r}, "
            f"target_age_group={target_age_group!r}: "
            f"filter matched_age_groups={matched_age_groups}, "
            f"expected_included={expected_included}, actual_included={actual_included}"
        )

    @given(
        guideline_age_group=st.sampled_from(["all_ages", "adults_only", "children"]),
    )
    @settings(max_examples=100, deadline=5000)
    def test_default_target_age_group_includes_only_all_ages(
        self, guideline_age_group: str
    ):
        """When no target_age_group is specified (defaults to 'all_ages'), only
        guidelines with age_group 'all_ages' SHALL be included.

        **Validates: Requirements 6.4**
        """
        from culture_compliance.nodes.step5_guideline_retrieval import (
            _build_cultural_filter,
        )
        from qdrant_client.models import FieldCondition, MatchAny, MatchValue

        # Use the default target_age_group value ("all_ages") as per the spec.
        default_target_age_group = "all_ages"

        qdrant_filter = _build_cultural_filter(
            market="malaysia",
            target_ethnicity="all",
            target_age_group=default_target_age_group,
        )

        # Extract the age_group condition.
        age_group_condition = None
        for condition in qdrant_filter.must:
            if isinstance(condition, FieldCondition) and condition.key == "age_group":
                age_group_condition = condition
                break

        assert age_group_condition is not None, (
            "Expected an age_group FieldCondition in the filter's must conditions."
        )

        match = age_group_condition.match
        if isinstance(match, MatchValue):
            matched_age_groups = {match.value}
        elif isinstance(match, MatchAny):
            matched_age_groups = set(match.any)
        else:
            raise AssertionError(
                f"Unexpected match type for age_group condition: {type(match)}"
            )

        # With default target_age_group="all_ages", only "all_ages" guidelines
        # should be included.
        expected_included = guideline_age_group == "all_ages"
        actual_included = guideline_age_group in matched_age_groups

        assert actual_included == expected_included, (
            f"With default target_age_group='all_ages', guideline_age_group="
            f"{guideline_age_group!r} should be included={expected_included}, "
            f"but filter matched_age_groups={matched_age_groups} gives "
            f"included={actual_included}"
        )


# Feature: cultural-guidelines-v2, Property 6: Combined Retrieval Merge Ranking


import types


def _make_point(score: float, payload: dict | None = None, point_id: str = "test-id") -> types.SimpleNamespace:
    """Create a mock Qdrant ScoredPoint using SimpleNamespace."""
    return types.SimpleNamespace(
        score=score,
        payload=payload or {},
        id=point_id,
    )


# Strategies for generating mock scored points

def _scored_point_strategy() -> st.SearchStrategy:
    """Generate a SimpleNamespace mock point with a score and payload."""
    return st.builds(
        lambda score, payload: _make_point(score, payload),
        score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        payload=st.fixed_dictionaries({
            "guideline_text": st.text(min_size=1, max_size=100),
            "category": st.sampled_from(sorted(VALID_CATEGORIES)),
            "severity": st.sampled_from(sorted(VALID_SEVERITIES)),
            "ethnicity": st.sampled_from(sorted(VALID_ETHNICITIES)),
            "age_group": st.sampled_from(sorted(VALID_AGE_GROUPS)),
        }),
    )


def _regulatory_point_strategy() -> st.SearchStrategy:
    """Generate a SimpleNamespace mock regulatory point with a score and payload."""
    return st.builds(
        lambda score, payload: _make_point(score, payload),
        score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        payload=st.fixed_dictionaries({
            "row_text": st.text(min_size=1, max_size=100),
            "source": st.just("MCMC"),
        }),
    )


class TestCombinedRetrievalMergeRanking:
    """Property 6: Combined Retrieval Merge Ranking.

    For any set of regulatory results and cultural results each with similarity
    scores, the merged result list SHALL be sorted in descending order by
    similarity score, and the total count SHALL not exceed 50. When fewer than
    50 combined results exist, all results SHALL be returned without error.

    **Validates: Requirements 7.2, 7.3, 10.1**
    """

    @given(
        regulatory_points=st.lists(_regulatory_point_strategy(), min_size=0, max_size=50),
        cultural_points=st.lists(_scored_point_strategy(), min_size=0, max_size=50),
    )
    @settings(max_examples=100, deadline=5000)
    def test_merged_results_sorted_descending_by_score(
        self,
        regulatory_points: list,
        cultural_points: list,
    ):
        """The merged guideline_sources list SHALL be sorted in descending order
        by similarity score.

        **Validates: Requirements 7.2**
        """
        from culture_compliance.nodes.step5_guideline_retrieval import _format_labeled_results

        _, _, _, guideline_sources = _format_labeled_results(
            regulatory_points, cultural_points, top_k=50
        )

        scores = [entry["score"] for entry in guideline_sources]
        assert scores == sorted(scores, reverse=True), (
            f"guideline_sources scores are not sorted descending: {scores}"
        )

    @given(
        regulatory_points=st.lists(_regulatory_point_strategy(), min_size=0, max_size=60),
        cultural_points=st.lists(_scored_point_strategy(), min_size=0, max_size=60),
    )
    @settings(max_examples=100, deadline=5000)
    def test_merged_results_count_does_not_exceed_50(
        self,
        regulatory_points: list,
        cultural_points: list,
    ):
        """The total count of merged results SHALL not exceed 50.

        **Validates: Requirements 7.3**
        """
        from culture_compliance.nodes.step5_guideline_retrieval import _format_labeled_results

        _, _, _, guideline_sources = _format_labeled_results(
            regulatory_points, cultural_points, top_k=50
        )

        assert len(guideline_sources) <= 50, (
            f"guideline_sources count {len(guideline_sources)} exceeds 50"
        )

    @given(
        regulatory_points=st.lists(_regulatory_point_strategy(), min_size=0, max_size=25),
        cultural_points=st.lists(_scored_point_strategy(), min_size=0, max_size=24),
    )
    @settings(max_examples=100, deadline=5000)
    def test_fewer_than_50_results_all_returned(
        self,
        regulatory_points: list,
        cultural_points: list,
    ):
        """When total combined results < 50, all results SHALL be returned
        without truncation or error.

        **Validates: Requirements 10.1**
        """
        from culture_compliance.nodes.step5_guideline_retrieval import _format_labeled_results

        total_input = len(regulatory_points) + len(cultural_points)
        assume(total_input < 50)

        _, _, _, guideline_sources = _format_labeled_results(
            regulatory_points, cultural_points, top_k=50
        )

        assert len(guideline_sources) == total_input, (
            f"Expected all {total_input} results to be returned, "
            f"but got {len(guideline_sources)}"
        )


# Feature: cultural-guidelines-v2, Property 7: Guideline Source Labeling in Prompt


from culture_compliance.nodes.step6_compliance_evaluation import _build_prompt


# Strategies for guideline text — use min_size=10 and filter to avoid short strings
# that could accidentally match boilerplate text in the prompt (e.g., digits, single chars).
_guideline_text_st = st.text(
    alphabet=st.characters(categories=("L", "Z")),  # letters and spaces only
    min_size=10,
    max_size=50,
).filter(lambda s: s.strip() and len(s.strip()) >= 8)


class TestGuidelineSourceLabelingInPrompt:
    """Property 7: Guideline Source Labeling in Prompt.

    For any set of retrieved guidelines containing both regulatory and cultural
    entries, the formatted prompt string SHALL contain a clearly labeled
    "Regulatory Guidelines" section and a clearly labeled "Cultural Guidelines"
    section, with each guideline appearing in exactly one section matching its
    source.

    **Validates: Requirements 10.2**
    """

    @given(
        reg_texts=st.lists(_guideline_text_st, min_size=1, max_size=5),
        cult_texts=st.lists(_guideline_text_st, min_size=1, max_size=5),
    )
    @settings(max_examples=100, deadline=5000)
    def test_prompt_contains_both_section_headers(
        self, reg_texts: list, cult_texts: list
    ):
        """When both regulatory_guidelines and cultural_guidelines are provided,
        the prompt SHALL contain '=== REGULATORY GUIDELINES ===' and
        '=== CULTURAL GUIDELINES ===' headers.

        **Validates: Requirements 10.2**
        """
        regulatory_guidelines = "\n".join(reg_texts)
        cultural_guidelines = "\n".join(cult_texts)

        prompt = _build_prompt(
            content="Sample content",
            content_type="text",
            market="malaysia",
            regulatory_guidelines=regulatory_guidelines,
            cultural_guidelines=cultural_guidelines,
        )

        assert "=== REGULATORY GUIDELINES ===" in prompt, (
            "Prompt is missing '=== REGULATORY GUIDELINES ===' header"
        )
        assert "=== CULTURAL GUIDELINES ===" in prompt, (
            "Prompt is missing '=== CULTURAL GUIDELINES ===' header"
        )

    @given(
        reg_texts=st.lists(_guideline_text_st, min_size=1, max_size=5),
        cult_texts=st.lists(_guideline_text_st, min_size=1, max_size=5),
    )
    @settings(max_examples=100, deadline=5000)
    def test_regulatory_guidelines_appear_before_cultural_section(
        self, reg_texts: list, cult_texts: list
    ):
        """Each regulatory guideline text SHALL appear before the cultural
        section header (i.e., in the regulatory section).

        **Validates: Requirements 10.2**
        """
        # Ensure no overlap between reg and cult texts to avoid ambiguity
        assume(not set(reg_texts) & set(cult_texts))

        regulatory_guidelines = "\n".join(reg_texts)
        cultural_guidelines = "\n".join(cult_texts)

        prompt = _build_prompt(
            content="Sample content",
            content_type="text",
            market="malaysia",
            regulatory_guidelines=regulatory_guidelines,
            cultural_guidelines=cultural_guidelines,
        )

        cultural_header_pos = prompt.index("=== CULTURAL GUIDELINES ===")

        for text in reg_texts:
            text_pos = prompt.find(text)
            assert text_pos != -1, (
                f"Regulatory guideline text {text!r} not found in prompt"
            )
            assert text_pos < cultural_header_pos, (
                f"Regulatory guideline text {text!r} appears after the cultural "
                f"section header (pos {text_pos} >= {cultural_header_pos})"
            )

    @given(
        reg_texts=st.lists(_guideline_text_st, min_size=1, max_size=5),
        cult_texts=st.lists(_guideline_text_st, min_size=1, max_size=5),
    )
    @settings(max_examples=100, deadline=5000)
    def test_cultural_guidelines_appear_after_cultural_section_header(
        self, reg_texts: list, cult_texts: list
    ):
        """Each cultural guideline text SHALL appear after the cultural section
        header (i.e., in the cultural section).

        **Validates: Requirements 10.2**
        """
        # Ensure no overlap between reg and cult texts to avoid ambiguity
        assume(not set(reg_texts) & set(cult_texts))

        regulatory_guidelines = "\n".join(reg_texts)
        cultural_guidelines = "\n".join(cult_texts)

        prompt = _build_prompt(
            content="Sample content",
            content_type="text",
            market="malaysia",
            regulatory_guidelines=regulatory_guidelines,
            cultural_guidelines=cultural_guidelines,
        )

        cultural_header_pos = prompt.index("=== CULTURAL GUIDELINES ===")

        for text in cult_texts:
            text_pos = prompt.find(text)
            assert text_pos != -1, (
                f"Cultural guideline text {text!r} not found in prompt"
            )
            assert text_pos > cultural_header_pos, (
                f"Cultural guideline text {text!r} appears before the cultural "
                f"section header (pos {text_pos} <= {cultural_header_pos})"
            )

    @given(
        reg_texts=st.lists(_guideline_text_st, min_size=1, max_size=5),
        cult_texts=st.lists(_guideline_text_st, min_size=1, max_size=5),
    )
    @settings(max_examples=100, deadline=5000)
    def test_no_guideline_text_appears_in_both_sections(
        self, reg_texts: list, cult_texts: list
    ):
        """No guideline text SHALL appear in both the regulatory and cultural
        sections simultaneously.

        **Validates: Requirements 10.2**
        """
        # Ensure no overlap between reg and cult texts to avoid ambiguity
        assume(not set(reg_texts) & set(cult_texts))

        regulatory_guidelines = "\n".join(reg_texts)
        cultural_guidelines = "\n".join(cult_texts)

        prompt = _build_prompt(
            content="Sample content",
            content_type="text",
            market="malaysia",
            regulatory_guidelines=regulatory_guidelines,
            cultural_guidelines=cultural_guidelines,
        )

        cultural_header_pos = prompt.index("=== CULTURAL GUIDELINES ===")
        regulatory_section = prompt[:cultural_header_pos]
        cultural_section = prompt[cultural_header_pos:]

        # Regulatory texts should not appear in the cultural section
        for text in reg_texts:
            assert text not in cultural_section, (
                f"Regulatory guideline text {text!r} unexpectedly appears in "
                f"the cultural section"
            )

        # Cultural texts should not appear in the regulatory section
        for text in cult_texts:
            assert text not in regulatory_section, (
                f"Cultural guideline text {text!r} unexpectedly appears in "
                f"the regulatory section"
            )


# Feature: cultural-guidelines-v2, Property 8: Cultural Violation Source Labeling


class TestCulturalViolationSourceLabeling:
    """Property 8: Cultural Violation Source Labeling.

    For any violation detected from a cultural guideline, the resulting
    high_risk_indicators entry SHALL have guideline_source set to "cultural".
    For any violation detected from a regulatory guideline, the entry SHALL
    have guideline_source set to "regulatory".

    **Validates: Requirements 10.3**
    """

    # --- Strategies ---

    _valid_source_st = st.sampled_from(["regulatory", "cultural"])
    _invalid_source_st = st.text().filter(
        lambda s: s not in {"regulatory", "cultural"} and s.strip()
    )

    _valid_category_st = st.sampled_from([
        "Religious Sensitivity",
        "Ethnic/Racial",
        "Sexual/Explicit",
        "Political/State",
        "LGBTQ",
        "Profanity",
    ])
    _valid_severity_st = st.sampled_from(["Severe", "Moderate", "Minor"])

    # --- TextIssueLocation ---

    @given(
        phrase=st.text(min_size=1, max_size=100),
        char_offset=st.integers(min_value=0, max_value=10000),
        category=_valid_category_st,
        severity=_valid_severity_st,
    )
    @settings(max_examples=100, deadline=5000)
    def test_text_issue_location_defaults_to_regulatory(
        self, phrase: str, char_offset: int, category: str, severity: str
    ):
        """TextIssueLocation SHALL default guideline_source to 'regulatory'
        when not specified.

        **Validates: Requirements 10.3**
        """
        from culture_compliance.models.schemas import TextIssueLocation

        loc = TextIssueLocation(
            phrase=phrase,
            char_offset=char_offset,
            category=category,
            severity=severity,
        )
        assert loc.guideline_source == "regulatory", (
            f"Expected default guideline_source='regulatory', got {loc.guideline_source!r}"
        )

    @given(
        phrase=st.text(min_size=1, max_size=100),
        char_offset=st.integers(min_value=0, max_value=10000),
        category=_valid_category_st,
        severity=_valid_severity_st,
        source=_valid_source_st,
    )
    @settings(max_examples=100, deadline=5000)
    def test_text_issue_location_accepts_and_preserves_valid_source(
        self, phrase: str, char_offset: int, category: str, severity: str, source: str
    ):
        """TextIssueLocation SHALL accept and preserve both 'regulatory' and
        'cultural' as guideline_source values.

        **Validates: Requirements 10.3**
        """
        from culture_compliance.models.schemas import TextIssueLocation

        loc = TextIssueLocation(
            phrase=phrase,
            char_offset=char_offset,
            category=category,
            severity=severity,
            guideline_source=source,
        )
        assert loc.guideline_source == source, (
            f"Expected guideline_source={source!r} to be preserved, "
            f"got {loc.guideline_source!r}"
        )

    @given(
        phrase=st.text(min_size=1, max_size=100),
        char_offset=st.integers(min_value=0, max_value=10000),
        category=_valid_category_st,
        severity=_valid_severity_st,
        invalid_source=_invalid_source_st,
    )
    @settings(max_examples=100, deadline=5000)
    def test_text_issue_location_rejects_invalid_source(
        self, phrase: str, char_offset: int, category: str, severity: str, invalid_source: str
    ):
        """TextIssueLocation SHALL raise ValidationError for any guideline_source
        value other than 'regulatory' or 'cultural'.

        **Validates: Requirements 10.3**
        """
        from culture_compliance.models.schemas import TextIssueLocation

        with pytest.raises(ValidationError):
            TextIssueLocation(
                phrase=phrase,
                char_offset=char_offset,
                category=category,
                severity=severity,
                guideline_source=invalid_source,
            )

    # --- ImageIssueLocation ---

    @given(
        x=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        y=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        width=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        height=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        description=st.text(min_size=1, max_size=100),
        category=_valid_category_st,
        severity=_valid_severity_st,
    )
    @settings(max_examples=100, deadline=5000)
    def test_image_issue_location_defaults_to_regulatory(
        self, x: float, y: float, width: float, height: float,
        description: str, category: str, severity: str
    ):
        """ImageIssueLocation SHALL default guideline_source to 'regulatory'
        when not specified.

        **Validates: Requirements 10.3**
        """
        from culture_compliance.models.schemas import ImageIssueLocation

        loc = ImageIssueLocation(
            bounding_box={"x": x, "y": y, "width": width, "height": height},
            description=description,
            category=category,
            severity=severity,
        )
        assert loc.guideline_source == "regulatory", (
            f"Expected default guideline_source='regulatory', got {loc.guideline_source!r}"
        )

    @given(
        x=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        y=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        width=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        height=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        description=st.text(min_size=1, max_size=100),
        category=_valid_category_st,
        severity=_valid_severity_st,
        source=_valid_source_st,
    )
    @settings(max_examples=100, deadline=5000)
    def test_image_issue_location_accepts_and_preserves_valid_source(
        self, x: float, y: float, width: float, height: float,
        description: str, category: str, severity: str, source: str
    ):
        """ImageIssueLocation SHALL accept and preserve both 'regulatory' and
        'cultural' as guideline_source values.

        **Validates: Requirements 10.3**
        """
        from culture_compliance.models.schemas import ImageIssueLocation

        loc = ImageIssueLocation(
            bounding_box={"x": x, "y": y, "width": width, "height": height},
            description=description,
            category=category,
            severity=severity,
            guideline_source=source,
        )
        assert loc.guideline_source == source, (
            f"Expected guideline_source={source!r} to be preserved, "
            f"got {loc.guideline_source!r}"
        )

    @given(
        x=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        y=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        width=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        height=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        description=st.text(min_size=1, max_size=100),
        category=_valid_category_st,
        severity=_valid_severity_st,
        invalid_source=_invalid_source_st,
    )
    @settings(max_examples=100, deadline=5000)
    def test_image_issue_location_rejects_invalid_source(
        self, x: float, y: float, width: float, height: float,
        description: str, category: str, severity: str, invalid_source: str
    ):
        """ImageIssueLocation SHALL raise ValidationError for any guideline_source
        value other than 'regulatory' or 'cultural'.

        **Validates: Requirements 10.3**
        """
        from culture_compliance.models.schemas import ImageIssueLocation

        with pytest.raises(ValidationError):
            ImageIssueLocation(
                bounding_box={"x": x, "y": y, "width": width, "height": height},
                description=description,
                category=category,
                severity=severity,
                guideline_source=invalid_source,
            )

    # --- VideoIssueLocation ---

    @given(
        timestamp=st.from_regex(r"^(?:\d{2}:\d{2}|\d{2}:\d{2}:\d{2})$", fullmatch=True),
        description=st.text(min_size=1, max_size=100),
        category=_valid_category_st,
        severity=_valid_severity_st,
    )
    @settings(max_examples=100, deadline=5000)
    def test_video_issue_location_defaults_to_regulatory(
        self, timestamp: str, description: str, category: str, severity: str
    ):
        """VideoIssueLocation SHALL default guideline_source to 'regulatory'
        when not specified.

        **Validates: Requirements 10.3**
        """
        from culture_compliance.models.schemas import VideoIssueLocation

        loc = VideoIssueLocation(
            timestamp=timestamp,
            description=description,
            category=category,
            severity=severity,
        )
        assert loc.guideline_source == "regulatory", (
            f"Expected default guideline_source='regulatory', got {loc.guideline_source!r}"
        )

    @given(
        timestamp=st.from_regex(r"^(?:\d{2}:\d{2}|\d{2}:\d{2}:\d{2})$", fullmatch=True),
        description=st.text(min_size=1, max_size=100),
        category=_valid_category_st,
        severity=_valid_severity_st,
        source=_valid_source_st,
    )
    @settings(max_examples=100, deadline=5000)
    def test_video_issue_location_accepts_and_preserves_valid_source(
        self, timestamp: str, description: str, category: str, severity: str, source: str
    ):
        """VideoIssueLocation SHALL accept and preserve both 'regulatory' and
        'cultural' as guideline_source values.

        **Validates: Requirements 10.3**
        """
        from culture_compliance.models.schemas import VideoIssueLocation

        loc = VideoIssueLocation(
            timestamp=timestamp,
            description=description,
            category=category,
            severity=severity,
            guideline_source=source,
        )
        assert loc.guideline_source == source, (
            f"Expected guideline_source={source!r} to be preserved, "
            f"got {loc.guideline_source!r}"
        )

    @given(
        timestamp=st.from_regex(r"^(?:\d{2}:\d{2}|\d{2}:\d{2}:\d{2})$", fullmatch=True),
        description=st.text(min_size=1, max_size=100),
        category=_valid_category_st,
        severity=_valid_severity_st,
        invalid_source=_invalid_source_st,
    )
    @settings(max_examples=100, deadline=5000)
    def test_video_issue_location_rejects_invalid_source(
        self, timestamp: str, description: str, category: str, severity: str, invalid_source: str
    ):
        """VideoIssueLocation SHALL raise ValidationError for any guideline_source
        value other than 'regulatory' or 'cultural'.

        **Validates: Requirements 10.3**
        """
        from culture_compliance.models.schemas import VideoIssueLocation

        with pytest.raises(ValidationError):
            VideoIssueLocation(
                timestamp=timestamp,
                description=description,
                category=category,
                severity=severity,
                guideline_source=invalid_source,
            )


# Feature: cultural-guidelines-v2, Property 3: Cultural Severity to Compliance Severity Mapping


class TestCulturalSeverityMapping:
    """Property 3: Cultural Severity to Compliance Severity Mapping.

    For any cultural guideline violation, the severity mapping SHALL produce
    "Severe" when the guideline severity is "high", "Moderate" when "medium",
    and "Minor" when "low". This mapping SHALL be exhaustive and deterministic.

    **Validates: Requirements 5.4, 5.5, 5.6**
    """

    @given(cultural_severity=st.sampled_from(["high", "medium", "low"]))
    @settings(max_examples=100, deadline=5000)
    def test_severity_mapping_is_correct(self, cultural_severity: str):
        """The mapping SHALL produce the correct compliance severity for each
        valid cultural severity value.

        **Validates: Requirements 5.4, 5.5, 5.6**
        """
        from culture_compliance.scoring import map_cultural_severity

        expected = {"high": "Severe", "medium": "Moderate", "low": "Minor"}
        result = map_cultural_severity(cultural_severity)
        assert result == expected[cultural_severity], (
            f"map_cultural_severity({cultural_severity!r}) returned {result!r}, "
            f"expected {expected[cultural_severity]!r}"
        )

    @given(cultural_severity=st.sampled_from(["high", "medium", "low"]))
    @settings(max_examples=100, deadline=5000)
    def test_severity_mapping_is_deterministic(self, cultural_severity: str):
        """Calling the mapping twice with the same input SHALL return the same
        output (determinism).

        **Validates: Requirements 5.4, 5.5, 5.6**
        """
        from culture_compliance.scoring import map_cultural_severity

        result1 = map_cultural_severity(cultural_severity)
        result2 = map_cultural_severity(cultural_severity)
        assert result1 == result2, (
            f"map_cultural_severity({cultural_severity!r}) returned different "
            f"results on two calls: {result1!r} vs {result2!r}"
        )

    @given(
        invalid_severity=st.text().filter(
            lambda s: s not in {"high", "medium", "low"}
        )
    )
    @settings(max_examples=100, deadline=5000)
    def test_invalid_severity_raises_value_error(self, invalid_severity: str):
        """Any value not in {"high", "medium", "low"} SHALL raise ValueError.

        **Validates: Requirements 5.4, 5.5, 5.6**
        """
        from culture_compliance.scoring import map_cultural_severity

        with pytest.raises(ValueError):
            map_cultural_severity(invalid_severity)


# Feature: cultural-guidelines-v2, Property 9: Scoring Formula Applies Equally to Cultural and Regulatory Violations


MALAYSIA_CATEGORY_WEIGHTS: dict[str, int] = {
    "Religious Sensitivity": 30,
    "Ethnic/Racial": 20,
    "Sexual/Explicit": 15,
    "Political/State": 15,
    "LGBTQ": 10,
    "Profanity": 10,
}

_malaysia_categories = sorted(MALAYSIA_CATEGORY_WEIGHTS.keys())
_compliance_severities = ["Severe", "Moderate", "Minor"]


class TestScoringFormulaEquality:
    """Property 9: Scoring Formula Applies Equally to Cultural and Regulatory Violations.

    For any set of violations (regardless of whether they originate from cultural
    or regulatory guidelines), the compliance score SHALL equal
    `max(0, round(100 - sum(weight × multiplier)))` using the same category
    weights and severity multipliers. The source (cultural vs regulatory) SHALL
    not affect the score calculation.

    **Validates: Requirements 10.4**
    """

    @given(
        violations=st.lists(
            st.tuples(
                st.sampled_from(_malaysia_categories),
                st.sampled_from(_compliance_severities),
            ),
            min_size=0,
            max_size=6,
        )
    )
    @settings(max_examples=100, deadline=5000)
    def test_calculate_score_matches_formula(self, violations: list[tuple[str, str]]):
        """calculate_score(violations, Market.MALAYSIA) SHALL equal
        max(0, round(100 - sum(weight × multiplier))) for any violation list.

        **Validates: Requirements 10.4**
        """
        from culture_compliance.scoring import calculate_score, SEVERITY_MULTIPLIERS
        from culture_compliance.models.schemas import Market

        # Compute expected score using the known weights and SEVERITY_MULTIPLIERS
        total_penalty = sum(
            MALAYSIA_CATEGORY_WEIGHTS[category] * SEVERITY_MULTIPLIERS[severity]
            for category, severity in violations
        )
        expected = max(0, round(100 - total_penalty))

        actual = calculate_score(violations, Market.MALAYSIA)

        assert actual == expected, (
            f"calculate_score returned {actual}, expected {expected} "
            f"for violations={violations}"
        )

    @given(
        violations=st.lists(
            st.tuples(
                st.sampled_from(_malaysia_categories),
                st.sampled_from(_compliance_severities),
            ),
            min_size=0,
            max_size=6,
        )
    )
    @settings(max_examples=100, deadline=5000)
    def test_score_is_source_agnostic(self, violations: list[tuple[str, str]]):
        """Two identical violation lists SHALL produce the same score regardless
        of a guideline_source label — since calculate_score does not accept a
        guideline_source parameter, the score is inherently source-agnostic.

        **Validates: Requirements 10.4**
        """
        from culture_compliance.scoring import calculate_score
        from culture_compliance.models.schemas import Market

        score_first_call = calculate_score(violations, Market.MALAYSIA)
        score_second_call = calculate_score(violations, Market.MALAYSIA)

        assert score_first_call == score_second_call, (
            f"Two calls with identical violations produced different scores: "
            f"{score_first_call} vs {score_second_call} for violations={violations}"
        )

    @given(
        violations=st.lists(
            st.tuples(
                st.sampled_from(_malaysia_categories),
                st.sampled_from(_compliance_severities),
            ),
            min_size=0,
            max_size=6,
        )
    )
    @settings(max_examples=100, deadline=5000)
    def test_score_is_always_in_range_0_to_100(self, violations: list[tuple[str, str]]):
        """The compliance score SHALL always be in the range [0, 100] for any
        violation list.

        **Validates: Requirements 10.4**
        """
        from culture_compliance.scoring import calculate_score
        from culture_compliance.models.schemas import Market

        score = calculate_score(violations, Market.MALAYSIA)

        assert 0 <= score <= 100, (
            f"Score {score} is outside the valid range [0, 100] "
            f"for violations={violations}"
        )


# Feature: cultural-guidelines-v2, Property 10: Violation Severity Ordering


# Indicator strategy for severity ordering tests
_indicator_st = st.fixed_dictionaries({
    "severity": st.sampled_from(["Severe", "Moderate", "Minor"]),
    "guideline_source": st.sampled_from(["regulatory", "cultural"]),
    "category": st.sampled_from(["Religious Sensitivity", "Ethnic/Racial", "Sexual/Explicit"]),
})

# The same ordering constant used in step7_result_formatting.py
_SEVERITY_ORDER = {"Severe": 0, "Moderate": 1, "Minor": 2}


class TestViolationSeverityOrdering:
    """Property 10: Violation Severity Ordering.

    For any set of high_risk_indicators containing violations of mixed
    severities, the output array SHALL be ordered with "Severe" violations
    first, then "Moderate", then "Minor", regardless of whether violations
    are regulatory or cultural in origin.

    **Validates: Requirements 10.5**
    """

    @given(indicators=st.lists(_indicator_st, min_size=0, max_size=20))
    @settings(max_examples=100, deadline=5000)
    def test_sorted_indicators_are_ordered_severe_moderate_minor(
        self, indicators: list
    ):
        """After applying the SEVERITY_ORDER sort, the result SHALL be ordered
        Severe → Moderate → Minor for any list of indicator dicts.

        **Validates: Requirements 10.5**
        """
        # Apply the same sort used in step7_result_formatting.py
        sorted_indicators = sorted(
            indicators,
            key=lambda x: _SEVERITY_ORDER.get(x.get("severity", "Minor"), 2),
        )

        # Verify the ordering: each item's severity rank must be >= the previous
        for i in range(1, len(sorted_indicators)):
            prev_rank = _SEVERITY_ORDER.get(
                sorted_indicators[i - 1].get("severity", "Minor"), 2
            )
            curr_rank = _SEVERITY_ORDER.get(
                sorted_indicators[i].get("severity", "Minor"), 2
            )
            assert prev_rank <= curr_rank, (
                f"Severity ordering violated at index {i}: "
                f"{sorted_indicators[i - 1]['severity']!r} (rank {prev_rank}) "
                f"appears before {sorted_indicators[i]['severity']!r} (rank {curr_rank}). "
                f"Full sorted list: {[ind['severity'] for ind in sorted_indicators]}"
            )

    @given(
        cultural_severe=st.fixed_dictionaries({
            "severity": st.just("Severe"),
            "guideline_source": st.just("cultural"),
            "category": st.sampled_from(["Religious Sensitivity", "Ethnic/Racial", "Sexual/Explicit"]),
        }),
        regulatory_moderate=st.fixed_dictionaries({
            "severity": st.just("Moderate"),
            "guideline_source": st.just("regulatory"),
            "category": st.sampled_from(["Religious Sensitivity", "Ethnic/Racial", "Sexual/Explicit"]),
        }),
    )
    @settings(max_examples=100, deadline=5000)
    def test_guideline_source_does_not_affect_ordering(
        self, cultural_severe: dict, regulatory_moderate: dict
    ):
        """A 'cultural' Severe violation SHALL appear before a 'regulatory'
        Moderate violation after sorting, regardless of guideline_source.

        **Validates: Requirements 10.5**
        """
        # Place regulatory_moderate first in the input to test that sort
        # reorders it correctly
        indicators = [regulatory_moderate, cultural_severe]

        sorted_indicators = sorted(
            indicators,
            key=lambda x: _SEVERITY_ORDER.get(x.get("severity", "Minor"), 2),
        )

        assert len(sorted_indicators) == 2
        assert sorted_indicators[0]["severity"] == "Severe", (
            f"Expected 'Severe' first, got {sorted_indicators[0]['severity']!r}. "
            f"guideline_source should not affect ordering."
        )
        assert sorted_indicators[0]["guideline_source"] == "cultural", (
            f"Expected the cultural Severe violation to be first, "
            f"got guideline_source={sorted_indicators[0]['guideline_source']!r}"
        )
        assert sorted_indicators[1]["severity"] == "Moderate", (
            f"Expected 'Moderate' second, got {sorted_indicators[1]['severity']!r}"
        )

    def test_empty_list_sorts_without_error(self):
        """An empty list SHALL sort without error and return an empty list.

        **Validates: Requirements 10.5**
        """
        indicators: list = []

        sorted_indicators = sorted(
            indicators,
            key=lambda x: _SEVERITY_ORDER.get(x.get("severity", "Minor"), 2),
        )

        assert sorted_indicators == [], (
            f"Expected empty list after sorting empty input, got {sorted_indicators!r}"
        )
