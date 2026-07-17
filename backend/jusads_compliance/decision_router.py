"""
decision_router.py
──────────────────
Pure routing function for the compliance pipeline decision logic.
Maps compliance analysis results to one of three outcomes:
PASS, CRITICAL_REGEN, or REMEDIATE.

This module is intentionally side-effect-free (no I/O, no database calls)
to enable independent property-based testing.

Absolute ban enforcement is driven by rules stored in the database
(ad_policy_rules where enforcement = 'hard_ban'), NOT by a hardcoded list.
The legal_research_agent injects those rules into the AI prompt via
{research_context}, so the AI naturally assigns risk_level=Critical.
This router then checks risk_level/risk_percentage — no separate ban list needed.
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
    compliance_verdict: str = "",
) -> DecisionOutcome:
    """Pure function: maps compliance result to one of three outcomes.

    Rules (in priority order):
      1. INCOMPLETE: evaluation_status incomplete → remediate (not a pass)
      2. CRITICAL_REGEN: risk_level == "Critical" OR risk_percentage > 85
         OR compliance_verdict == "rejected"
      3. PASS: risk_level == "Low" AND risk_percentage <= 30
         AND compliance_verdict != "rejected"
      4. REMEDIATE: everything else

    The function NEVER triggers the Remediation Pipeline directly — it only
    returns a routing decision string.

    Note on absolute bans:
      Hard bans (gambling, alcohol to Muslim demographics, etc.) are stored
      in the `ad_policy_rules` table with enforcement='hard_ban'. The
      legal_research_agent fetches these at runtime and injects them into the
      AI prompt, so the AI itself assigns risk_level="Critical". This router
      then correctly routes those to critical_regen without needing a separate
      hardcoded list — keeping the AI verdict and the routing decision in sync.

    Args:
        risk_level: The assessed risk level (e.g. "Low", "Moderate", "High", "Critical").
        risk_percentage: Integer risk score from 0 to 100.
        high_risk_indicators: List of flagged risk indicator strings.
        compliance_verdict: Optional verdict string from AI ("accepted" / "needs_remediation" / "rejected" / "incomplete_evaluation").

    Returns:
        One of "pass", "critical_regen", or "remediate".
    """
    # Incomplete evaluation — never pass silently
    if compliance_verdict == "incomplete_evaluation":
        logger.warning("[DecisionRouter] Incomplete evaluation received — routing to remediate.")
        return "remediate"

    # Warn on unexpected risk_level values
    if risk_level not in _KNOWN_RISK_LEVELS:
        logger.warning(
            "[DecisionRouter] Unexpected risk_level value received: %r. "
            "Defaulting to 'remediate'.",
            risk_level,
        )
        return "remediate"

    # CRITICAL_REGEN: AI explicitly rejected OR high risk score
    if compliance_verdict == "rejected" or risk_level == "Critical" or risk_percentage > 85:
        return "critical_regen"

    # PASS: Low risk and percentage within threshold and not rejected
    if risk_level == "Low" and risk_percentage <= 30:
        return "pass"

    # REMEDIATE: all remaining cases
    return "remediate"
