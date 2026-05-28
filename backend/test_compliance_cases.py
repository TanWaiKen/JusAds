"""
test_compliance_cases.py
────────────────────────
Tests the TextComplianceChecker against three distinct scenarios (Best, Moderate, Worst)
and outputs the exact JSON payload the agent expects.
"""

import json
import logging
from typing import Dict, Any

from jusads_text_compliance.tools import check_text_compliance

# Suppress logging to keep the console output clean
logging.getLogger("jusads_text_compliance").setLevel(logging.CRITICAL)

# ── TEST SCRIPTS ─────────────────────────────────────────────────────────────

BEST_CASE = """
Welcome to the grand opening of our new community center! 
We are excited to offer free skill-building workshops, health screenings, and 
family-friendly activities for everyone. Come join us this weekend to celebrate 
unity and progress together. Refreshments will be served (strictly Halal certified). 
We look forward to seeing you there!
"""

MODERATE_CASE = """
Looking for the fastest way to lose weight? Try our new dietary supplement! 
It might help you shed those extra kilos in just a few weeks. 
Available now at your local pharmacy. Consult your doctor before use.
"""

WORST_CASE = """
Feeling lucky? Come down to our casino tonight and win big! 
We have the absolute best slot machines in the entire country. 
Plus, enjoy our all-you-can-eat pork buffet and free-flowing beer while you play. 
Don't miss out on the greatest party in town!
"""

# ─────────────────────────────────────────────────────────────────────────────

def run_test_case(name: str, text: str) -> None:
    print(f"\n{'='*60}")
    print(f" TEST CASE: {name.upper()}")
    print(f"{'='*60}")
    print(f"Input Text:\n{text.strip()}\n")
    print("-" * 60)
    
    try:
        # The ReAct agent natively calls the tool like this
        json_output = check_text_compliance.invoke({
            "text": text,
            "market": "malaysia",
            "ethnicity": "malay",
            "age_group": "all_ages"
        })
        
        print("OUTPUT FORMAT (JSON):")
        print(json_output)
        
    except Exception as e:
        print(f"Error during evaluation: {e}")


def main():
    print("Testing LangChain ReAct Tools...")
    run_test_case("Best Case (Fully Compliant)", BEST_CASE)
    run_test_case("Moderate Case (Borderline Claims)", MODERATE_CASE)
    run_test_case("Worst Case (Severe Violations)", WORST_CASE)


if __name__ == "__main__":
    main()
