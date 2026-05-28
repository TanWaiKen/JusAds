"""JusAds Text Compliance Tool - Main Entry Point

This module provides a tool-like interface for text compliance checking.
Can be used as a standalone function or integrated into larger systems.

Usage as standalone:
    python backend/jusads_text_compliance/main.py

Usage as imported tool:
    from jusads_text_compliance.main import check_text_compliance

    result = check_text_compliance(
        ad_text="Try our new whitening cream!",
        market="malaysia",
        ethnicity="malay"
    )
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Optional

from .text_checker import TextComplianceChecker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def check_text_compliance(
    ad_text: str,
    market: str = "malaysia",
    ethnicity: str = "all",
    age_group: str = "all_ages",
    return_full_details: bool = False,
) -> dict[str, Any]:
    """Check text compliance as a tool function.

    This is the main tool interface for text compliance checking.

    Args:
        ad_text: The advertisement text to evaluate.
        market: Target market ('malaysia' or 'singapore').
        ethnicity: Target ethnicity ('malay', 'chinese', 'indian', 'all').
        age_group: Target age group ('all_ages', 'adults_only', 'children').
        return_full_details: If True, return full details including retrieved rules.

    Returns:
        Compliance result dict with:
        - risk_level: 'Low', 'Medium', 'High'
        - score: 0-100 (100 = fully compliant)
        - violations: List of violation descriptions
        - explanation: Summary of findings
        - suggestion: Recommendation to fix issues
        - [optional] Full details if return_full_details=True

    Example:
        >>> result = check_text_compliance("Win big at our casino!", "malaysia", "malay")
        >>> print(result["risk_level"])  # "High"
        >>> print(result["score"])  # 25
    """
    logger.info(
        "Checking text compliance: market=%s, ethnicity=%s, age_group=%s",
        market,
        ethnicity,
        age_group,
    )

    try:
        # Initialize checker
        checker = TextComplianceChecker()

        # Run compliance check
        full_result = checker.check_compliance(
            ad_text=ad_text,
            market=market,
            ethnicity=ethnicity,
            age_group=age_group,
        )

        # Return either compact or full result
        if return_full_details:
            return full_result

        # Return compact result (most common use case)
        return {
            "ad_text": ad_text,
            "market": market,
            "ethnicity": ethnicity,
            "age_group": age_group,
            "risk_level": full_result["risk_level"],
            "score": full_result["score"],
            "violations": [v["description"] for v in full_result["violations"]],
            "explanation": full_result["explanation"],
            "suggestion": full_result["suggestion"],
            "processing_time_ms": full_result["processing_time_ms"],
        }

    except Exception as e:
        logger.error("Text compliance check failed: %s", str(e), exc_info=True)
        return {
            "ad_text": ad_text,
            "market": market,
            "ethnicity": ethnicity,
            "age_group": age_group,
            "risk_level": "Unknown",
            "score": 0,
            "violations": [],
            "explanation": f"Error during compliance check: {str(e)}",
            "suggestion": "Please check configuration and retry.",
            "processing_time_ms": 0,
        }


def print_result(result: dict[str, Any]) -> None:
    """Pretty-print a compliance result."""
    print("\n" + "=" * 70)
    print("  JUSADS TEXT COMPLIANCE RESULT")
    print("=" * 70)
    print(f"\nAd Text:      {result['ad_text'][:60]}{'...' if len(result['ad_text']) > 60 else ''}")
    print(f"Market:       {result['market'].upper()}")
    print(f"Ethnicity:    {result['ethnicity']}")
    print(f"Age Group:    {result['age_group']}")
    print(f"\nRisk Level:   {result['risk_level']}")
    print(f"Score:        {result['score']}/100")
    print(f"Processing:   {result['processing_time_ms']}ms")

    print("\n" + "-" * 70)
    print("VIOLATIONS")
    print("-" * 70)
    if result["violations"]:
        for i, violation in enumerate(result["violations"], 1):
            print(f"{i}. {violation}")
    else:
        print("* No violations detected")

    print("\n" + "-" * 70)
    print("EXPLANATION")
    print("-" * 70)
    print(result["explanation"])

    if result.get("suggestion"):
        print("\n" + "-" * 70)
        print("SUGGESTION")
        print("-" * 70)
        print(result["suggestion"])

    print("\n" + "=" * 70 + "\n")


def main():
    """Main entry point for standalone usage."""
    import argparse

    parser = argparse.ArgumentParser(
        description="JusAds Text Compliance Tool - Evaluate ad text for compliance"
    )
    parser.add_argument(
        "--text",
        required=True,
        help="Advertisement text to evaluate",
    )
    parser.add_argument(
        "--market",
        default="malaysia",
        choices=["malaysia", "singapore"],
        help="Target market (default: malaysia)",
    )
    parser.add_argument(
        "--ethnicity",
        default="all",
        choices=["malay", "chinese", "indian", "all"],
        help="Target ethnicity (default: all)",
    )
    parser.add_argument(
        "--age-group",
        default="all_ages",
        choices=["all_ages", "adults_only", "children"],
        help="Target age group (default: all_ages)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Return full details including retrieved rules",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging (DEBUG level)",
    )

    args = parser.parse_args()

    # Setup logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Run compliance check
    result = check_text_compliance(
        ad_text=args.text,
        market=args.market,
        ethnicity=args.ethnicity,
        age_group=args.age_group,
        return_full_details=args.full,
    )

    # Output result
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_result(result)

    # Exit with appropriate code
    risk_level = result.get("risk_level", "Unknown")
    if risk_level == "High":
        sys.exit(2)
    elif risk_level == "Medium":
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
