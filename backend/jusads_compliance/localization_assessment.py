"""Deterministic presentation of the model's audience-localization score.

Localization quality is intentionally distinct from legal or platform compliance.
It describes how well language, tone, presentation, and cultural references fit
the *selected* market/persona; it must never be used as a proxy for the value
of a culture or for a legal rejection.
"""

from typing import Any


def build_localization_assessment(score: Any) -> dict[str, Any]:
    """Normalise a 0–100 cultural-fit score into a transparent UI assessment."""
    try:
        normalized_score = max(0, min(100, int(score)))
    except (TypeError, ValueError):
        return {
            "score": None,
            "priority": "not_assessed",
            "label": "Not assessed",
            "description": "Localization fit was not available for this review.",
        }

    if normalized_score >= 85:
        priority, label = "low", "Strong fit"
        description = "The assessed language, tone, and presentation fit the selected audience well."
    elif normalized_score >= 70:
        priority, label = "advisory", "Minor localization review"
        description = "The creative is broadly suitable, with minor language, tone, or presentation improvements worth considering."
    elif normalized_score >= 45:
        priority, label = "moderate", "Needs localization"
        description = "Adapt language, tone, or presentation before relying on this creative for the selected audience."
    else:
        priority, label = "high", "High localization mismatch"
        description = "The creative is a poor fit for the selected audience and should be substantially adapted or replaced."

    return {
        "score": normalized_score,
        "priority": priority,
        "label": label,
        "description": description,
    }
