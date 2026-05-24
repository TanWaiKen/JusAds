"""Property-based tests for scoring logic.

Feature: content-compliance
Tests Properties 3, 4, and 12 from the design document.
"""

from hypothesis import given, settings, strategies as st

from culture_compliance.scoring import (
    MALAYSIA_SCORING,
    SEVERITY_MULTIPLIERS,
    SINGAPORE_SCORING,
    calculate_score,
    get_scoring_config,
    score_to_risk_level,
)
from culture_compliance.models.schemas import Market


# --- Strategies ---

MALAYSIA_CATEGORIES = [cat.name for cat in MALAYSIA_SCORING]
SINGAPORE_CATEGORIES = [cat.name for cat in SINGAPORE_SCORING]
SEVERITY_LEVELS = ["none", "Minor", "Moderate", "Severe"]


def malaysia_violations_strategy():
    """Generate a list of (category, severity) pairs for Malaysia market."""
    return st.lists(
        st.tuples(
            st.sampled_from(MALAYSIA_CATEGORIES),
            st.sampled_from(SEVERITY_LEVELS),
        ),
        min_size=0,
        max_size=20,
    )


def singapore_violations_strategy():
    """Generate a list of (category, severity) pairs for Singapore market."""
    return st.lists(
        st.tuples(
            st.sampled_from(SINGAPORE_CATEGORIES),
            st.sampled_from(SEVERITY_LEVELS),
        ),
        min_size=0,
        max_size=20,
    )


# --- Property 3: Scoring Formula Correctness ---
# **Validates: Requirements 2.3, 5.5**


@settings(max_examples=100, deadline=5000)
@given(violations=malaysia_violations_strategy())
def test_property_3_scoring_formula_malaysia(violations):
    """Property 3: Scoring Formula Correctness (Malaysia market).

    For any set of (category, severity) violation pairs drawn from the valid
    categories and severity levels, the compliance score SHALL equal
    max(0, round(100 - sum(weight × multiplier))) where weight is the category
    weight and multiplier is the severity multiplier (None=0, Minor=0.25,
    Moderate=0.6, Severe=1.0).

    **Validates: Requirements 2.3, 5.5**
    """
    market = Market.MALAYSIA
    weight_map = {cat.name: cat.weight for cat in MALAYSIA_SCORING}

    # Compute expected score using the formula directly
    total_penalty = 0.0
    for category_name, severity in violations:
        weight = weight_map[category_name]
        multiplier = SEVERITY_MULTIPLIERS[severity]
        total_penalty += weight * multiplier

    expected_score = max(0, round(100 - total_penalty))

    # Compute actual score from the module
    actual_score = calculate_score(violations, market)

    assert actual_score == expected_score, (
        f"Score mismatch: expected {expected_score}, got {actual_score} "
        f"for violations={violations}"
    )


@settings(max_examples=100, deadline=5000)
@given(violations=singapore_violations_strategy())
def test_property_3_scoring_formula_singapore(violations):
    """Property 3: Scoring Formula Correctness (Singapore market).

    For any set of (category, severity) violation pairs drawn from the valid
    categories and severity levels, the compliance score SHALL equal
    max(0, round(100 - sum(weight × multiplier))) where weight is the category
    weight and multiplier is the severity multiplier (None=0, Minor=0.25,
    Moderate=0.6, Severe=1.0).

    **Validates: Requirements 2.3, 5.5**
    """
    market = Market.SINGAPORE
    weight_map = {cat.name: cat.weight for cat in SINGAPORE_SCORING}

    # Compute expected score using the formula directly
    total_penalty = 0.0
    for category_name, severity in violations:
        weight = weight_map[category_name]
        multiplier = SEVERITY_MULTIPLIERS[severity]
        total_penalty += weight * multiplier

    expected_score = max(0, round(100 - total_penalty))

    # Compute actual score from the module
    actual_score = calculate_score(violations, market)

    assert actual_score == expected_score, (
        f"Score mismatch: expected {expected_score}, got {actual_score} "
        f"for violations={violations}"
    )


# --- Property 4: Score-to-Risk-Level Mapping ---
# **Validates: Requirements 2.4**


@settings(max_examples=100, deadline=5000)
@given(score=st.integers(min_value=0, max_value=100))
def test_property_4_score_to_risk_level_mapping(score):
    """Property 4: Score-to-Risk-Level Mapping.

    For any integer score in the range [0, 100], the risk level mapping SHALL
    produce "Low" when score >= 75, "Medium" when 40 <= score < 75, and "High"
    when score < 40.

    **Validates: Requirements 2.4**
    """
    risk_level = score_to_risk_level(score)

    if score >= 75:
        expected = "Low"
    elif score >= 40:
        expected = "Medium"
    else:
        expected = "High"

    assert risk_level == expected, (
        f"Risk level mismatch for score {score}: "
        f"expected '{expected}', got '{risk_level}'"
    )


@settings(max_examples=100, deadline=5000)
@given(score=st.integers(min_value=0, max_value=100))
def test_property_4_exhaustive_and_mutually_exclusive(score):
    """Property 4: Score-to-Risk-Level Mapping - exhaustive and mutually exclusive.

    The three ranges SHALL be exhaustive and mutually exclusive: every score
    in [0, 100] maps to exactly one risk level.

    **Validates: Requirements 2.4**
    """
    risk_level = score_to_risk_level(score)

    # Must be one of the three valid levels
    assert risk_level in {"Low", "Medium", "High"}, (
        f"Invalid risk level '{risk_level}' for score {score}"
    )

    # Verify mutual exclusivity by checking only one condition is true
    conditions = [score >= 75, 40 <= score < 75, score < 40]
    assert sum(conditions) == 1, (
        f"Score {score} matches {sum(conditions)} conditions (expected exactly 1)"
    )


# --- Property 12: Market Scoring Configuration ---
# **Validates: Requirements 5.5**


@settings(max_examples=100, deadline=5000)
@given(market=st.sampled_from([Market.MALAYSIA, Market.SINGAPORE]))
def test_property_12_market_scoring_configuration(market):
    """Property 12: Market Scoring Configuration.

    For any valid market value, the scoring configuration returned SHALL
    contain exactly 6 categories whose weights sum to 100.

    **Validates: Requirements 5.5**
    """
    config = get_scoring_config(market)

    # Exactly 6 categories
    assert len(config) == 6, (
        f"Expected 6 categories for {market.value}, got {len(config)}"
    )

    # Weights sum to 100
    total_weight = sum(cat.weight for cat in config)
    assert total_weight == 100, (
        f"Expected weights to sum to 100 for {market.value}, got {total_weight}"
    )


@settings(max_examples=100, deadline=5000)
@given(market=st.sampled_from([Market.MALAYSIA, Market.SINGAPORE]))
def test_property_12_market_scoring_correct_weights(market):
    """Property 12: Market Scoring Configuration - correct weight values.

    For any valid market value, the scoring configuration SHALL match the
    defined weights for that market.

    **Validates: Requirements 5.5**
    """
    config = get_scoring_config(market)
    weight_map = {cat.name: cat.weight for cat in config}

    if market == Market.MALAYSIA:
        expected = {
            "Religious Sensitivity": 30,
            "Ethnic/Racial": 20,
            "Sexual/Explicit": 15,
            "Political/State": 15,
            "LGBTQ": 10,
            "Profanity": 10,
        }
    else:  # Singapore
        expected = {
            "Racial/Religious Harmony": 30,
            "Public Morals": 20,
            "National Interest": 15,
            "Consumer Protection": 15,
            "Decency": 10,
            "Social Responsibility": 10,
        }

    assert weight_map == expected, (
        f"Weight mismatch for {market.value}: expected {expected}, got {weight_map}"
    )
