import json
import logging
from typing import Any

from jusads_video_compliance.video_checker import VideoComplianceChecker

# Suppress logging to keep the console output clean
logging.getLogger("jusads_video_compliance").setLevel(logging.CRITICAL)
logging.getLogger("jusads_transcription").setLevel(logging.CRITICAL)

def run_video_test_case(name: str, video_path: str, market: str = "malaysia", ethnicity: str = "malay", age_group: str = "all_ages") -> None:
    print(f"\n{'='*60}")
    print(f" TEST CASE: {name.upper()}")
    print(f" Video: {video_path}")
    print(f" Target: {market.title()} | {ethnicity.title()} | {age_group}")
    print(f"{'='*60}")
    
    try:
        checker = VideoComplianceChecker()
        result = checker.check_compliance(
            video_path=video_path,
            market=market,
            ethnicity=ethnicity,
            age_group=age_group
        )
        
        # Remove massive byte payloads for clean output
        print("OUTPUT FORMAT (JSON):")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"Error during evaluation: {e}")

def main():
    print("Testing Video Compliance Checker with AWS Transcribe + Gemini 3.1 Flash Lite...")
    
    # Test Case 1: Video Ad
    run_video_test_case(
        "Commercial Video Test", 
        "backend/assets/Test Video.mp4",
        market="malaysia",
        ethnicity="all"
    )

if __name__ == "__main__":
    main()
