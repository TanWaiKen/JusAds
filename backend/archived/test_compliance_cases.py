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

def run_test_case(name: str, text: str, market: str = "malaysia", ethnicity: str = "malay", age_group: str = "all_ages") -> None:
    print(f"\n{'='*60}")
    print(f" TEST CASE: {name.upper()}")
    print(f" Target: {market.title()} | {ethnicity.title()} | {age_group}")
    print(f"{'='*60}")
    print(f"Input Text:\n{text.strip()}\n")
    print("-" * 60)
    
    try:
        # The ReAct agent natively calls the tool like this
        json_output = check_text_compliance.invoke({
            "text": text,
            "market": market,
            "ethnicity": ethnicity,
            "age_group": age_group
        })
        
        print("OUTPUT FORMAT (JSON):")
        print(json_output)
        
    except Exception as e:
        print(f"Error during evaluation: {e}")

SINGAPORE_GEN_Z_CASE = """
Hey besties! Ready for the ultimate deal? Our new bubble tea shop is opening! 
We're launching our exclusive 'Deadly Good' series. Buy 4 drinks for just $4.44! 
Don't be basic, come down and chope your seats early or you'll miss out on the aesthetic vibes. 
Warning: It's so good it's almost a sin! #kiasu #shiok
"""

def main():
    print("Testing LangChain ReAct Tools...")
    run_test_case("Best Case (Fully Compliant)", BEST_CASE)
    run_test_case("Moderate Case (Borderline Claims)", MODERATE_CASE)
    run_test_case("Worst Case (Severe Violations)", WORST_CASE)
    
    # Test the new Singapore Chinese Gen Z persona logic
    run_test_case("Singapore Gen Z (Taboo Test)", SINGAPORE_GEN_Z_CASE, market="singapore", ethnicity="chinese", age_group="gen_z")


if __name__ == "__main__":
    main()
