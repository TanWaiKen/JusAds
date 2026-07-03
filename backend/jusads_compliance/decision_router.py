"""
decision_router.py
──────────────────
Pure routing function for the compliance pipeline decision logic.
Maps compliance analysis results to one of three outcomes:
PASS, CRITICAL_REGEN, or REMEDIATE.

This module is intentionally side-effect-free (no I/O, no database calls)
to enable independent property-based testing.
"""

import logging
from typing import Literal

logger = logging.getLogger(__name__)

DecisionOutcome = Literal["pass", "critical_regen", "remediate"]

_KNOWN_RISK_LEVELS = {"Low", "Moderate", "High", "Critical"}


def route_compliance_decision(
    risk_level: str,
    risk_percentage: int,
    high_risk_indicators: list[str],
) -> DecisionOutcome:
    """Pure function: maps compliance result to one of three outcomes.

    Rules:
      - PASS: risk_level == "Low" AND risk_percentage <= 30
      - CRITICAL_REGEN: risk_level == "Critical" OR risk_percentage > 85
      - REMEDIATE: everything else (High/Moderate with indicators, or unknown risk_level)

    The function NEVER triggers the Remediation Pipeline directly — it only
    returns a routing decision string.

    Args:
        risk_level: The assessed risk level (e.g. "Low", "Moderate", "High", "Critical").
        risk_percentage: Integer risk score from 0 to 100.
        high_risk_indicators: List of flagged risk indicator strings.

    Returns:
        One of "pass", "critical_regen", or "remediate".
    """
    # Warn on unexpected risk_level values
    if risk_level not in _KNOWN_RISK_LEVELS:
        logger.warning(
            "[DecisionRouter] Unexpected risk_level value received: %r. "
            "Defaulting to 'remediate'.",
            risk_level,
        )
        return "remediate"

    # PASS: Low risk and percentage within threshold
    if risk_level == "Low" and risk_percentage <= 30:
        return "pass"

    # CRITICAL_REGEN: Critical level or very high percentage
    if risk_level == "Critical" or risk_percentage > 85:
        return "critical_regen"

    # REMEDIATE: all remaining cases
    return "remediate"
