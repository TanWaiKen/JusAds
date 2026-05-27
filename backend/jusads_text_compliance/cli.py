"""CLI for JusAds Text Compliance Checker

Simple command-line interface to test text compliance locally.

Usage:
    python -m jusads_text_compliance.cli --text "Your ad copy here"
    python -m jusads_text_compliance.cli --text "Your ad copy" --ethnicity malay --verbose
"""

import argparse
import json
import logging
import sys

from .text_checker import TextComplianceChecker


def setup_logging(verbose: bool = False):
    """Configure logging based on verbosity level."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )


def print_result(result: dict, show_rules: bool = False):
    """Pretty-print the compliance result."""
    print("\n" + "=" * 70)
    print("  JUSADS TEXT COMPLIANCE RESULT")
    print("=" * 70)
    print(f"\nMarket:       {result['market'].upper()}")
    print(f"Ethnicity:    {result['ethnicity']}")
    print(f"Age Group:    {result['age_group']}")
    print(f"\nRisk Level:   {result['risk_level']}")
    print(f"Score:        {result['score']}/100")
    print(f"\nProcessing:   {result['processing_time_ms']}ms")
    print(f"Rules Used:   {result['regulatory_rules_count']} regulatory + {result['cultural_rules_count']} cultural")

    print("\n" + "-" * 70)
    print("VIOLATIONS")
    print("-" * 70)
    if result["violations"]:
        for i, violation in enumerate(result["violations"], 1):
            print(f"{i}. {violation['description']}")
    else:
        print("✓ No violations detected")

    print("\n" + "-" * 70)
    print("EXPLANATION")
    print("-" * 70)
    print(result["explanation"])

    if result["suggestion"]:
        print("\n" + "-" * 70)
        print("SUGGESTION")
        print("-" * 70)
        print(result["suggestion"])

    if show_rules:
        print("\n" + "-" * 70)
        print("REGULATORY RULES USED")
        print("-" * 70)
        for rule in result["regulatory_rules"][:5]:  # Show top 5
            print(f"- [{rule['category']}] {rule['guideline_text'][:100]}...")

        print("\n" + "-" * 70)
        print("CULTURAL GUIDELINES USED")
        print("-" * 70)
        for guideline in result["cultural_rules"][:5]:  # Show top 5
            print(f"- [{guideline['category']}] {guideline['guideline_text'][:100]}...")

    print("\n" + "=" * 70 + "\n")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="JusAds Text Compliance Checker - Evaluate ad copy for compliance"
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
        "--show-rules",
        action="store_true",
        help="Display the top retrieved rules in output",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON instead of pretty-print",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging (DEBUG level)",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(verbose=args.verbose)

    # Initialize checker
    try:
        checker = TextComplianceChecker()
    except Exception as e:
        print(f"ERROR: Failed to initialize checker: {e}", file=sys.stderr)
        print("\nMake sure QDRANT_URL, QDRANT_API_KEY, and GOOGLE_API_KEY are set in .env")
        sys.exit(1)

    # Run compliance check
    result = checker.check_compliance(
        ad_text=args.text,
        market=args.market,
        ethnicity=args.ethnicity,
        age_group=args.age_group,
    )

    # Output result
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_result(result, show_rules=args.show_rules)

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
