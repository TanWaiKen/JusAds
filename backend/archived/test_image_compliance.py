import json
import logging
from typing import Any

from jusads_image_compliance.image_checker import ImageComplianceChecker

# Suppress logging to keep the console output clean
logging.getLogger("jusads_image_compliance").setLevel(logging.CRITICAL)

def run_image_test_case(name: str, image_path: str, market: str = "malaysia", ethnicity: str = "malay", age_group: str = "all_ages") -> None:
    print(f"\n{'='*60}")
    print(f" TEST CASE: {name.upper()}")
    print(f" Image: {image_path}")
    print(f" Target: {market.title()} | {ethnicity.title()} | {age_group}")
    print(f"{'='*60}")
    
    try:
        checker = ImageComplianceChecker()
        result = checker.check_compliance(
            image_path=image_path,
            market=market,
            ethnicity=ethnicity,
            age_group=age_group
        )
        
        # Remove massive image bytes/paths for clean output
        print("OUTPUT FORMAT (JSON):")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"Error during evaluation: {e}")

def main():
    print("Testing Image Compliance Checker with Gemini 3.1 Flash Lite...")
    
    # Test Case 1: Fully Compliant Image
    run_image_test_case(
        "Compliant Malay Ad", 
        "backend/assets/images/compliant_malay_ad.png",
        market="malaysia",
        ethnicity="malay"
    )
    
    # Test Case 2: Non-compliant Armpit Taboo Image
    run_image_test_case(
        "Non-Compliant Modesty Violation (Armpit)", 
        "backend/assets/images/noncompliant_armpit_ad.png",
        market="malaysia",
        ethnicity="malay"
    )

if __name__ == "__main__":
    main()
