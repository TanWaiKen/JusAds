"""
Test script for the end-to-end Image Compliance + Remediation Pipeline.
"""

import json
import logging
from pprint import pprint
import time

from jusads_image_compliance.image_checker import ImageComplianceChecker
from jusads_image_compliance.image_remediator import ImageRemediator

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def test_image_pipeline(image_path: str, market: str = "malaysia", ethnicity: str = "all"):
    print(f"\n{'='*80}")
    print(f" END-TO-END IMAGE PIPELINE TEST")
    print(f" Image: {image_path}")
    print(f" Target: {market.title()} | {ethnicity.title()}")
    print(f"{'='*80}\n")

    # Step 1: Check Compliance
    print("--- [Step 1] Running Compliance Check ---")
    start = time.time()
    checker = ImageComplianceChecker()
    check_result = checker.check_compliance(
        image_path=image_path,
        market=market,
        ethnicity=ethnicity
    )
    print(f"Check completed in {time.time() - start:.2f}s")
    
    print("\n[Compliance Result]")
    print(f"Risk Level: {check_result.get('risk_level')}")
    print(f"Score: {check_result.get('score')}")
    print("High Risk Indicators:")
    for indicator in check_result.get('high_risk_indicators', []):
        print(f"  - {indicator}")
    print(f"Explanation: {check_result.get('explanation')}")
    print(f"Suggestion: {check_result.get('suggestion')}")

    if check_result.get("score", 100) >= 75:
        print("\nImage is compliant. No remediation needed.")
        return

    # Step 2: Remediate Image
    print("\n--- [Step 2] Running Image Remediation ---")
    start = time.time()
    remediator = ImageRemediator()
    remediation_result = remediator.remediate(
        image_path=image_path,
        compliance_result=check_result,
        market=market,
        ethnicity=ethnicity
    )
    print(f"Remediation completed in {time.time() - start:.2f}s")

    print("\n[Remediation Result]")
    print("Compliant Image Prompt (ready for Imagen 3 / Midjourney):")
    print(f"  {remediation_result.get('compliant_image_prompt')}")
    print("\nChanges Suggested:")
    for change in remediation_result.get('changes_suggested', []):
        print(f"  - {change}")

if __name__ == "__main__":
    # Test on the non-compliant armpit ad
    test_image_pipeline(
        image_path="backend/assets/images/noncompliant_armpit_ad.png",
        market="malaysia",
        ethnicity="malay"
    )
