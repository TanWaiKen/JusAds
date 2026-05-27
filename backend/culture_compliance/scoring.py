"""Scoring configuration and calculation for content compliance.

Defines market-specific scoring categories with weights, severity multipliers,
and functions to calculate compliance scores and map them to risk levels.
"""

from pydantic import BaseModel

from .models.schemas import Market


class ScoringCategory(BaseModel):
    """A single scoring category with weight."""

    name: str
    weight: int


# --- Market-Specific Scoring Configurations ---

MALAYSIA_SCORING: list[ScoringCategory] = [
    ScoringCategory(name="Religious Sensitivity", weight=30),
    ScoringCategory(name="Ethnic/Racial", weight=20),
    ScoringCategory(name="Sexual/Explicit", weight=15),
    ScoringCategory(name="Political/State", weight=15),
    ScoringCategory(name="LGBTQ", weight=10),
    ScoringCategory(name="Profanity", weight=10),
]

SINGAPORE_SCORING: list[ScoringCategory] = [
    ScoringCategory(name="Racial/Religious Harmony", weight=30),
    ScoringCategory(name="Public Morals", weight=20),
    ScoringCategory(name="National Interest", weight=15),
    ScoringCategory(name="Consumer Protection", weight=15),
    ScoringCategory(name="Decency", weight=10),
    ScoringCategory(name="Social Responsibility", weight=10),
]

# --- Severity Multipliers ---

SEVERITY_MULTIPLIERS: dict[str, float] = {
    "none": 0.0,
    "Minor": 0.25,
    "Moderate": 0.6,
    "Severe": 1.0,
}


def get_scoring_config(market: Market) -> list[ScoringCategory]:
    """Return the scoring categories for the given market.

    Args:
        market: The target regulatory market.

    Returns:
        List of ScoringCategory objects with names and weights for the market.
    """
    if market == Market.MALAYSIA:
        return MALAYSIA_SCORING
    elif market == Market.SINGAPORE:
        return SINGAPORE_SCORING
    else:
        raise ValueError(f"Unsupported market: {market}")


def calculate_score(violations: list[tuple[str, str]], market: Market) -> int:
    """Calculate the compliance score based on violations.

    Applies the formula: max(0, round(100 - sum(weight × multiplier)))

    Each violation is a tuple of (category_name, severity). The weight is
    looked up from the market's scoring configuration, and the multiplier
    from SEVERITY_MULTIPLIERS.

    Args:
        violations: List of (category_name, severity) tuples representing
            detected violations.
        market: The target regulatory market for weight lookup.

    Returns:
        Integer compliance score between 0 and 100.
    """
    scoring_config = get_scoring_config(market)
    weight_map = {cat.name: cat.weight for cat in scoring_config}

    total_penalty = 0.0
    for category_name, severity in violations:
        weight = weight_map.get(category_name, 0)
        multiplier = SEVERITY_MULTIPLIERS.get(severity, 0.0)
        total_penalty += weight * multiplier

    return max(0, round(100 - total_penalty))


def score_to_risk_level(score: int) -> str:
    """Map a compliance score to a risk level.

    Args:
        score: Integer compliance score (0-100).

    Returns:
        Risk level string: "Low" (score >= 75), "Medium" (40 <= score < 75),
        or "High" (score < 40).
    """
    if score >= 75:
        return "Low"
    elif score >= 40:
        return "Medium"
    else:
        return "High"


def map_cultural_severity(cultural_severity: str) -> str:
    """Map a cultural guideline severity to a compliance violation severity.

    Args:
        cultural_severity: Cultural severity value ("high", "medium", or "low").

    Returns:
        Compliance severity string: "Severe", "Moderate", or "Minor".

    Raises:
        ValueError: If cultural_severity is not one of the valid values.
    """
    mapping = {
        "high": "Severe",
        "medium": "Moderate",
        "low": "Minor",
    }
    if cultural_severity not in mapping:
        raise ValueError(
            f"Invalid cultural severity: '{cultural_severity}'. "
            f"Must be one of: {sorted(mapping.keys())}"
        )
    return mapping[cultural_severity]
