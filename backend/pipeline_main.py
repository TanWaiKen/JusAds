"""
pipeline_main.py
────────────────
Entry point for the multimodal compliance pipeline.
Takes an audio/video file, transcribes it, and runs text compliance on the transcript.
"""

import argparse
import json
import logging
import sys

from jusads_transcription.transcriber import VideoTranscriber
from jusads_text_compliance.text_checker import TextComplianceChecker

# Set up logging for the CLI output
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pipeline_main")


def main():
    parser = argparse.ArgumentParser(description="JusAds Audio/Video Compliance Pipeline")
    parser.add_argument(
        "--media",
        required=True,
        help="Path to the video or audio file (e.g., ad_video.mp4)",
    )
    parser.add_argument(
        "--market",
        default="malaysia",
        help="Target market: 'malaysia' or 'singapore' (default: malaysia)",
    )
    parser.add_argument(
        "--ethnicity",
        default="all",
        help="Target ethnicity: 'malay', 'chinese', 'indian', or 'all' (default: all)",
    )
    parser.add_argument(
        "--age_group",
        default="all_ages",
        help="Target age group: 'all_ages', 'adults_only', 'children' (default: all_ages)",
    )
    parser.add_argument(
        "--no-ffmpeg",
        action="store_true",
        help="Disable ffmpeg audio extraction and upload the raw video directly.",
    )
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("  JUSADS MEDIA COMPLIANCE PIPELINE")
    print("=" * 70)

    # 1. Transcription
    print("\n[STEP 1: TRANSCRIPTION]")
    transcriber = VideoTranscriber(use_ffmpeg=not args.no_ffmpeg)
    
    try:
        transcript = transcriber.transcribe_media(args.media)
    except Exception as e:
        print(f"\n[ERROR] Transcription failed: {e}")
        sys.exit(1)

    print("\n--- TRANSCRIPT ---")
    print(transcript.strip())
    print("------------------\n")

    # 2. Compliance Check
    print("[STEP 2: COMPLIANCE CHECK]")
    checker = TextComplianceChecker()
    
    try:
        result = checker.check_compliance(
            ad_text=transcript,
            market=args.market,
            ethnicity=args.ethnicity,
            age_group=args.age_group,
        )
    except Exception as e:
        print(f"\n[ERROR] Compliance check failed: {e}")
        sys.exit(1)

    # Output results
    print("\n" + "=" * 70)
    print("  FINAL RESULT")
    print("=" * 70)
    print(f"Media File:   {args.media}")
    print(f"Market:       {result['market'].upper()}")
    print(f"Ethnicity:    {result['ethnicity']}")
    print(f"Age Group:    {result['age_group']}")
    print()
    print(f"Risk Level:   {result['risk_level']}")
    print(f"Score:        {result['score']}/100")
    print()

    if result["violations"]:
        print("-" * 70)
        print("VIOLATIONS")
        print("-" * 70)
        for i, v in enumerate(result["violations"], 1):
            print(f"{i}. {v}")
        print()

    print("-" * 70)
    print("EXPLANATION")
    print("-" * 70)
    print(result["explanation"])
    print()

    if result.get("suggestion"):
        print("-" * 70)
        print("SUGGESTION")
        print("-" * 70)
        print(result["suggestion"])
        print()
    
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
