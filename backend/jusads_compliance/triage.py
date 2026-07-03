"""
triage.py
─────────
Pure-logic triage decider for the image remix pipeline.

Determines which of three outcomes applies to an image compliance result:
  - COMPLIANT: no action needed
  - EDIT: localized inpainting fix possible
  - CANNOT_FIX: redirect to frontend with actionable guidance

This module makes ZERO AI API calls. All functions are synchronous `def`.
"""

import logging
from typing import Optional

from shared.models import TriageOutcome, TriageResult

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

VALID_PLATFORMS = {"tiktok", "meta", "instagram", "general"}
VALID_MARKETS = {"malaysia", "singapore"}

PLATFORM_BANS: dict[str, dict[str, list[str]]] = {
    "tiktok": {
        "malaysia": ["lingerie", "underwear", "alcohol", "gambling"],
        "singapore": ["lingerie", "underwear", "alcohol", "gambling"],
    },
    "meta": {"malaysia": [], "singapore": []},
    "instagram": {"malaysia": [], "singapore": []},
    "general": {"malaysia": [], "singapore": []},
}

PRODUCT_VIOLATION_KEYWORDS = [
    "product itself", "cannot advertise", "prohibited product",
    "the concept", "entire image", "core subject",
    "lingerie", "underwear", "alcohol", "gambling",
    "cannot be shown", "banned category",
]


# ─────────────────────────────────────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────────────────────────────────────


def _extract_product_type(violations: list[str], localization_plan: str = "") -> Optional[str]:
    """Extract the product type from violation strings using keyword matching.

    Scans violations and the localization_plan for known product categories.
    Returns the first matched category, or None if none found.
    """
    known_categories = [
        "lingerie", "underwear", "alcohol", "gambling",
        "tobacco", "cannabis", "weapons", "firearms",
    ]
    combined = " ".join(violations).lower() + " " + localization_plan.lower()
    for category in known_categories:
        if category in combined:
            return category
    return None


def _is_platform_banned(product_type: Optional[str], platform: str, market: str) -> bool:
    """Check if the product type is banned on the given platform/market.

    Returns False if product_type is None or if the platform/market combination
    has no ban list (graceful degradation).
    """
    if not product_type:
        return False
    try:
        banned_list = PLATFORM_BANS.get(platform, {}).get(market, [])
        return product_type.lower() in [b.lower() for b in banned_list]
    except Exception:
        # Platform rules unavailable — skip check (Requirement 2.4)
        logger.warning("[TriageDecider] Platform rules lookup failed — skipping ban check")
        return False


def _product_is_violation(violations: list[str], localization_plan: str) -> bool:
    """Determine if the product/concept itself is the compliance violation.

    Uses keyword matching only — no AI call.
    Returns True if ≥ 2 keywords from PRODUCT_VIOLATION_KEYWORDS match
    in the combined violations + localization_plan text.
    """
    combined = " ".join(violations).lower() + " " + localization_plan.lower()
    matches = sum(1 for kw in PRODUCT_VIOLATION_KEYWORDS if kw in combined)
    return matches >= 2


def _build_cannot_fix_guidance(
    violations: list[str], localization_plan: str, market: str
) -> str:
    """Build actionable guidance text for CANNOT_FIX outcomes.

    Returns a human-readable guidance string of at least 10 characters.
    """
    violation_summary = "; ".join(violations[:3]) if violations else "compliance issues"
    return (
        f"The core concept of this advertisement violates regulations for {market}. "
        f"Issues: {violation_summary}. "
        f"Consider redesigning the creative with a different concept, or consult "
        f"the compliance team for alternative approaches."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Main triage function
# ─────────────────────────────────────────────────────────────────────────────


def triage_decide(
    risk_percentage: int,
    violations: list[str],
    segmentation: Optional[dict],
    localization_plan: str,
    platform: str,
    market: str,
) -> TriageResult:
    """Determine remix outcome without calling AI models.

    Pure-logic triage: returns exactly one of COMPLIANT, EDIT, CANNOT_FIX.
    Raises ValueError for invalid inputs.

    Args:
        risk_percentage: Integer in [0, 100].
        violations: List of compliance violation strings (may be empty).
        segmentation: Segmentation result dict from compliance pipeline (may be None).
        localization_plan: Localization guidance string.
        platform: One of {"tiktok", "meta", "instagram", "general"}.
        market: One of {"malaysia", "singapore"}.

    Returns:
        TriageResult with outcome, reasoning, guidance, and platform_ban fields.

    Raises:
        ValueError: If risk_percentage is outside [0, 100], or platform/market
                     is not in the allowed set.
    """
    # ── Input validation ──────────────────────────────────────────────────
    if not isinstance(risk_percentage, int) or risk_percentage < 0 or risk_percentage > 100:
        raise ValueError(
            f"risk_percentage must be an integer in [0, 100], got {risk_percentage!r}"
        )
    if platform not in VALID_PLATFORMS:
        raise ValueError(
            f"platform must be one of {VALID_PLATFORMS}, got {platform!r}"
        )
    if market not in VALID_MARKETS:
        raise ValueError(
            f"market must be one of {VALID_MARKETS}, got {market!r}"
        )

    # ── Step 1: Check if already compliant ────────────────────────────────
    if risk_percentage < 20 and len(violations) == 0:
        return TriageResult(
            outcome=TriageOutcome.COMPLIANT,
            reasoning="Risk below threshold with no violations",
            guidance="",
            platform_ban=False,
        )

    # ── Step 2: Check platform-level product ban (early exit) ─────────────
    product_type = _extract_product_type(violations, localization_plan)
    if _is_platform_banned(product_type, platform, market):
        return TriageResult(
            outcome=TriageOutcome.CANNOT_FIX,
            reasoning=f"{product_type} cannot be advertised on {platform} in {market}",
            guidance=(
                f"This product category ({product_type}) is prohibited on "
                f"{platform} in {market}. Consider a different platform or "
                f"redesign the creative without showing the product directly."
            ),
            platform_ban=True,
        )

    # ── Step 3: Check if product itself is the violation ──────────────────
    if _product_is_violation(violations, localization_plan):
        return TriageResult(
            outcome=TriageOutcome.CANNOT_FIX,
            reasoning="The product/concept itself violates regulations",
            guidance=_build_cannot_fix_guidance(violations, localization_plan, market),
            platform_ban=False,
        )

    # ── Step 4: Violations are localized and fixable ──────────────────────
    return TriageResult(
        outcome=TriageOutcome.EDIT,
        reasoning="Violations are localized to specific regions",
        guidance="",
        platform_ban=False,
    )
