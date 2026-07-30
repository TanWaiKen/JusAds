"""Non-authoritative, synthetic-data-only text risk triage proof of concept.

This module is deliberately small and transparent. It is not a compliance
classifier, does not make legal determinations, and must never change an LLM,
rules, remediation, or recheck decision. It exists solely to demonstrate a
future learning-layer interface and explainability payload.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass


MODEL_VERSION = "demo-keyword-linear-v1"
_TOKEN_RE = re.compile(r"[a-z0-9']+")

# Synthetic demonstration weights. They are intentionally not calibrated to
# real-world policy, jurisdictions, customers, or production outcomes.
_WEIGHTS: dict[str, float] = {
    "guaranteed": 1.30,
    "cure": 1.45,
    "instant": 0.55,
    "risk-free": 0.90,
    "miracle": 1.20,
    "limited": 0.25,
    "offer": 0.10,
    "save": -0.20,
    "ingredients": -0.35,
    "terms": -0.20,
    "results": -0.15,
}
_INTERCEPT = -0.45


@dataclass(frozen=True)
class AdvisoryTriageResult:
    """A transparent advisory signal; never a policy verdict."""

    label: str
    risk_score: float
    confidence: float
    top_features: list[dict[str, float | str]]
    model_version: str = MODEL_VERSION
    advisory_only: bool = True
    synthetic_demo_model: bool = True

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def classify_text(text: str) -> AdvisoryTriageResult:
    """Return an explainable heuristic score for non-empty text.

    ``risk_score`` is a demonstration model probability, not a legal or
    compliance probability. ``confidence`` expresses only the distance from
    the model's decision boundary.
    """
    tokens = _TOKEN_RE.findall(text.lower())
    contributions = [
        {"feature": token, "contribution": weight}
        for token in tokens
        if (weight := _WEIGHTS.get(token)) is not None
    ]
    logit = _INTERCEPT + sum(float(item["contribution"]) for item in contributions)
    risk_score = 1.0 / (1.0 + math.exp(-max(-20.0, min(20.0, logit))))
    contributions.sort(key=lambda item: abs(float(item["contribution"])), reverse=True)
    return AdvisoryTriageResult(
        label="higher_review_priority" if risk_score >= 0.50 else "lower_review_priority",
        risk_score=round(risk_score, 4),
        confidence=round(abs(risk_score - 0.50) * 2, 4),
        top_features=contributions[:5],
    )
