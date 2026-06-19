"""
JusAds Video Compliance Orchestrator
======================================
Full pipeline to check and remediate a video ad:

  Step 1: Compliance Check        (Gemini + Qdrant RAG)
  Step 2: Parse Violations        (Extract timestamps + categories)
  Step 3: Visual Remediation      (Gemini Flash Image + Veo 3.1 Lite)
  Step 4: Audio Remediation       (ElevenLabs TTS)
  Step 5: Compose Final Video     (FFmpeg)

Usage:
    python -m jusads_video_compliance.orchestrator
    python -m jusads_video_compliance.orchestrator --video "assets/Test Video.mp4" --market malaysia
"""

import argparse
import asyncio
import json
import os
import sys
import time
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jusads_video_compliance.step1_compliance_check import check_compliance
from jusads_video_compliance.step2_parse_violations import parse_violations
from jusads_video_compliance.step3_visual_remediation import remediate_visual
from jusads_video_compliance.step4_audio_remediation import remediate_audio
from jusads_video_compliance.step5_compose_final import compose_final

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def run_pipeline(video_path, market, ethnicity, age_group, language):
    """Full pipeline: check → parse → remediate visual → remediate audio → compose."""

    # Create numbered run folder
    base_output_dir = os.path.join("assets", "remediated")
    os.makedirs(base_output_dir, exist_ok=True)
    existing_runs = [
        int(d) for d in os.listdir(base_output_dir)
        if os.path.isdir(os.path.join(base_output_dir, d)) and d.isdigit()
    ]
    run_number = max(existing_runs, default=0) + 1
    output_dir = os.path.join(base_output_dir, str(run_number))
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  JusAds Video Compliance Pipeline (Run #{run_number})")
    print(f"{'='*60}")
    print(f"  Video    : {video_path}")
    print(f"  Market   : {market}")
    print(f"  Ethnicity: {ethnicity}")
    print(f"  Language : {language}")
    print(f"  Output   : {output_dir}")
    print(f"{'='*60}\n")

    pipeline_start = time.time()

    # ━━━ STEP 1: Compliance Check ━━━
    print(f"{'='*60}")
    print("  STEP 1: Compliance Check")
    print(f"{'='*60}")
    result = check_compliance(video_path, market, ethnicity, age_group)

    score = result.get("score", 0)
    print(f"  Risk Level: {result.get('risk_level')}")
    print(f"  Score: {score}/100")
    print(f"  Indicators: {len(result.get('high_risk_indicators', []))}")
    print()

    if score >= 75:
        print("  ✅ Video is compliant. No remediation needed.")
        return True

    # ━━━ STEP 2: Parse Violations ━━━
    print(f"{'='*60}")
    print("  STEP 2: Parse Violations")
    print(f"{'='*60}")
    violations = parse_violations(result)

    visual = [v for v in violations if v["type"] == "visual"]
    audio = [v for v in violations if v["type"] == "audio"]
    print(f"  Found: {len(visual)} visual, {len(audio)} audio")
    for i, v in enumerate(violations, 1):
        print(f"  {i}. [{v['start']:.1f}s-{v['end']:.1f}s] {v['type'].upper()} | {v['description'][:50]}")
    print()

    # ━━━ STEP 3: Visual Remediation ━━━
    print(f"{'='*60}")
    print("  STEP 3: Visual Remediation (Gemini Flash Image + Veo)")
    print(f"{'='*60}")
    visual_results = await remediate_visual(video_path, visual, output_dir)

    fixed_visual = sum(1 for r in visual_results if r["success"])
    print(f"  Visual: {fixed_visual}/{len(visual)} fixed")
    print()

    # ━━━ STEP 4: Audio Remediation ━━━
    print(f"{'='*60}")
    print("  STEP 4: Audio Remediation (ElevenLabs TTS)")
    print(f"{'='*60}")
    audio_results = await remediate_audio(video_path, audio, output_dir, market, ethnicity, language)

    fixed_audio = sum(1 for r in audio_results if r["success"])
    print(f"  Audio: {fixed_audio}/{len(audio)} fixed")
    print()

    # ━━━ STEP 5: Compose Final ━━━
    print(f"{'='*60}")
    print("  STEP 5: Compose Final Video")
    print(f"{'='*60}")
    final_path = compose_final(video_path, visual_results, audio_results, output_dir)
    print(f"  Output: {final_path}")
    print()

    # ━━━ DONE ━━━
    total_time = time.time() - pipeline_start
    print(f"{'='*60}")
    print(f"  DONE! (Run #{run_number})")
    print(f"{'='*60}")
    print(f"  Final Video : {final_path}")
    print(f"  Fixed       : {fixed_visual + fixed_audio}/{len(violations)}")
    print(f"  Total Time  : {total_time:.1f}s")
    print(f"{'='*60}\n")

    # Save result
    pipeline_output = {
        "run": run_number,
        "video_path": video_path,
        "score": score,
        "violations": len(violations),
        "fixed": fixed_visual + fixed_audio,
        "final_video": final_path,
        "time_seconds": round(total_time, 1),
        "visual_results": visual_results,
        "audio_results": audio_results,
    }
    with open(os.path.join(output_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(pipeline_output, f, indent=2, ensure_ascii=False)

    return True


def main():
    parser = argparse.ArgumentParser(description="JusAds Video Compliance Pipeline")
    parser.add_argument("--video", default="assets/Test Video.mp4", help="Video file path")
    parser.add_argument("--market", default="malaysia", help="Target market")
    parser.add_argument("--ethnicity", default="malay", help="Target ethnicity")
    parser.add_argument("--age-group", default="all_ages", help="Target age group")
    parser.add_argument("--language", default="ms", help="Language code")

    args = parser.parse_args()

    if not os.path.isfile(args.video):
        print(f"ERROR: Video not found: {args.video}")
        sys.exit(1)

    asyncio.run(run_pipeline(args.video, args.market, args.ethnicity, args.age_group, args.language))


if __name__ == "__main__":
    main()
