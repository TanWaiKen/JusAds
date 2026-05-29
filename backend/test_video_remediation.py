"""
Test script for the end-to-end Video Compliance + Remediation Pipeline.
"""

import json
import logging
import time

from jusads_video_compliance.video_checker import VideoComplianceChecker
from jusads_video_compliance.video_remediator import VideoRemediator

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def test_video_pipeline(video_path: str, market: str = "malaysia", ethnicity: str = "all"):
    print(f"\n{'='*80}")
    print(f" END-TO-END VIDEO PIPELINE TEST")
    print(f" Video: {video_path}")
    print(f" Target: {market.title()} | {ethnicity.title()}")
    print(f"{'='*80}\n")

    # Step 1: Check Compliance
    print("--- [Step 1] Running Compliance Check ---")
    start = time.time()
    checker = VideoComplianceChecker()
    check_result = checker.check_compliance(
        video_path=video_path,
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
        print("\nVideo is compliant. No remediation needed.")
        return

    # Step 2: Remediate Video
    print("\n--- [Step 2] Running Video Remediation ---")
    start = time.time()
    remediator = VideoRemediator()
    remediation_result = remediator.remediate(
        video_path=video_path,
        compliance_result=check_result,
        market=market,
        ethnicity=ethnicity
    )
    print(f"Remediation completed in {time.time() - start:.2f}s")

    print("\n[Remediation Result]")
    print("Rewritten Script:")
    print(f"{remediation_result.get('rewritten_script')}")
    print("\nVisual Edit Guide:")
    for edit in remediation_result.get('visual_edit_guide', []):
        print(f"  [{edit.get('timestamp')}]")
        print(f"    Current: {edit.get('current')}")
        print(f"    Change : {edit.get('change_to')}")
        print(f"    Reason : {edit.get('reason')}")
    print("\nChanges Made:")
    for change in remediation_result.get('changes_made', []):
        print(f"  - {change}")

if __name__ == "__main__":
    # Test on the test video
    test_video_pipeline(
        video_path="backend/assets/Test Video.mp4",
        market="malaysia",
        ethnicity="all"
    )
