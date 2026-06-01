"""
Test script: Run VideoComplianceChecker on the test video.
Usage: python run_video_check.py
"""

import json
import sys
import os
import logging

# Set up logging to see pipeline progress
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Ensure backend/ is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from jusads_video_compliance.video_checker import VideoComplianceChecker


def main():
    video_path = os.path.join("assets", "Test Video.mp4")

    if not os.path.isfile(video_path):
        print(f"ERROR: Video file not found at: {video_path}")
        sys.exit(1)

    print(f"{'='*60}")
    print(f"  JusAds Video Compliance Checker — Test Run")
    print(f"{'='*60}")
    print(f"  Video: {video_path}")
    print(f"  Market: malaysia")
    print(f"  Ethnicity: malay")
    print(f"  Age Group: all_ages")
    print(f"{'='*60}\n")

    checker = VideoComplianceChecker()

    print("Running compliance check...\n")
    result = checker.check_compliance(
        video_path=video_path,
        market="malaysia",
        ethnicity="malay",
        age_group="all_ages",
    )

    # Display results
    print(f"\n{'='*60}")
    print(f"  RESULTS")
    print(f"{'='*60}")
    print(f"  Risk Level : {result.get('risk_level', 'N/A')}")
    print(f"  Score      : {result.get('score', 'N/A')}/100")
    print(f"  Processing : {result.get('processing_time_ms', 'N/A')}ms")
    print(f"{'='*60}\n")

    # Display violations
    indicators = result.get("high_risk_indicators", [])
    if indicators:
        print(f"  HIGH RISK INDICATORS ({len(indicators)}):")
        print(f"  {'-'*50}")
        for i, indicator in enumerate(indicators, 1):
            print(f"  {i}. {indicator}")
        print()
    else:
        print("  No violations found — video is compliant!\n")

    # Display explanation
    explanation = result.get("explanation", "")
    if explanation:
        print(f"  EXPLANATION:")
        print(f"  {'-'*50}")
        print(f"  {explanation[:500]}")
        print()

    # Display suggestion
    suggestion = result.get("suggestion", "")
    if suggestion:
        print(f"  SUGGESTION:")
        print(f"  {'-'*50}")
        print(f"  {suggestion[:500]}")
        print()

    # Save full result to JSON
    output_file = "compliance_result.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"  Full result saved to: {output_file}")


if __name__ == "__main__":
    main()
