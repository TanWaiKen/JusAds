"""
Test script: Run remediation using saved compliance_result.json
Skips Phase 1 (compliance check) — goes straight to parse → remediate.

Tests both visual edit (Nano Banana + Veo) and audio edit (ElevenLabs TTS).

Usage: python run_remediation_test.py
"""

import asyncio
import json
import os
import sys
import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from jusads_video_compliance.models import Violation
from jusads_video_compliance.orchestrator import orchestrate_remediation


def _merge_overlapping_segments(segments: list[dict]) -> list[dict]:
    """Merge overlapping time segments into non-overlapping consolidated segments."""
    if not segments:
        return []

    sorted_segs = sorted(segments, key=lambda s: s["timestamp_start"])
    merged = [sorted_segs[0].copy()]

    for seg in sorted_segs[1:]:
        last = merged[-1]
        if seg["timestamp_start"] <= last["timestamp_end"] + 0.5:
            last["timestamp_end"] = max(last["timestamp_end"], seg["timestamp_end"])
            if seg["description"] not in last["description"]:
                combined = f"{last['description']}; {seg['description']}"
                last["description"] = combined[:200]
            severity_rank = {"Severe": 3, "Moderate": 2, "Minor": 1}
            if severity_rank.get(seg["severity"], 0) > severity_rank.get(last["severity"], 0):
                last["severity"] = seg["severity"]
        else:
            merged.append(seg.copy())

    return merged


def parse_violations_from_result(result: dict) -> list[Violation]:
    """Parse compliance_result.json into merged, non-overlapping Violation objects.
    
    Also injects a synthetic audio violation for testing audio remediation.
    """
    import re

    indicators = result.get("high_risk_indicators", [])
    score = result.get("score", 0)
    raw_violations = []

    for indicator in indicators:
        if not isinstance(indicator, str):
            continue

        range_pattern = r"\[(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})\]"
        match = re.search(range_pattern, indicator)

        if match:
            start_parts = match.group(1).split(":")
            end_parts = match.group(2).split(":")
            timestamp_start = int(start_parts[0]) * 60 + int(start_parts[1])
            timestamp_end = int(end_parts[0]) * 60 + int(end_parts[1])
            description = indicator[match.end():].strip()
        else:
            single_pattern = r"\[(\d{1,2}:\d{2})\]"
            single_match = re.search(single_pattern, indicator)
            if single_match:
                parts = single_match.group(1).split(":")
                timestamp_start = int(parts[0]) * 60 + int(parts[1])
                timestamp_end = timestamp_start + 2.0
                description = indicator[single_match.end():].strip()
            else:
                timestamp_start = 0.0
                timestamp_end = 2.0
                description = indicator

        if timestamp_end <= timestamp_start:
            timestamp_end = timestamp_start + 1.0

        text_lower = indicator.lower()
        if "(audio)" in text_lower or any(kw in text_lower for kw in ["spoken", "dialogue", "voice", "claim"]):
            violation_type = "audio"
        else:
            violation_type = "visual"

        if score < 40:
            severity = "Severe"
        elif score < 75:
            severity = "Moderate"
        else:
            severity = "Minor"

        category = "Sexual/Explicit"
        if any(kw in text_lower for kw in ["religious", "hijab", "halal", "mosque"]):
            category = "Religious Sensitivity"
        elif any(kw in text_lower for kw in ["ethnic", "racial"]):
            category = "Ethnic/Racial"

        if len(description) > 200:
            description = description[:197] + "..."

        raw_violations.append({
            "timestamp_start": float(timestamp_start),
            "timestamp_end": float(timestamp_end),
            "category": category,
            "severity": severity,
            "description": description,
            "violation_type": violation_type,
            "guideline_source": "cultural",
        })

    # Add a synthetic audio violation for testing audio remediation
    # The transcript mentions "armpits stink" which is inappropriate
    raw_violations.append({
        "timestamp_start": 0.0,
        "timestamp_end": 3.0,
        "category": "Profanity",
        "severity": "Moderate",
        "description": "Inappropriate language: 'armpits stink' is culturally insensitive",
        "violation_type": "audio",
        "guideline_source": "cultural",
    })

    # Merge overlapping segments per type
    visual_raw = [v for v in raw_violations if v["violation_type"] == "visual"]
    audio_raw = [v for v in raw_violations if v["violation_type"] == "audio"]

    merged_visual = _merge_overlapping_segments(visual_raw)
    merged_audio = _merge_overlapping_segments(audio_raw)

    violations = []
    for v in merged_visual + merged_audio:
        try:
            violation = Violation(
                timestamp_start=v["timestamp_start"],
                timestamp_end=v["timestamp_end"],
                category=v["category"],
                severity=v["severity"],
                description=v["description"],
                violation_type=v["violation_type"],
                guideline_source=v["guideline_source"],
            )
            violations.append(violation)
        except ValueError as e:
            logger.warning(f"Skipping invalid violation: {e}")

    return violations


async def main():
    # Load saved compliance result
    result_file = "compliance_result.json"
    if not os.path.isfile(result_file):
        print(f"ERROR: {result_file} not found. Run run_video_check.py first.")
        sys.exit(1)

    with open(result_file, "r", encoding="utf-8") as f:
        result = json.load(f)

    video_path = result.get("video_path", "assets/Test Video.mp4")
    market = result.get("market", "malaysia")
    ethnicity = result.get("ethnicity", "malay")
    age_group = result.get("age_group", "all_ages")
    language = "ms"
    output_dir = os.path.join("assets", "remediated")

    if not os.path.isfile(video_path):
        print(f"ERROR: Video file not found: {video_path}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  Remediation Test (from compliance_result.json)")
    print(f"{'='*60}")
    print(f"  Video    : {video_path}")
    print(f"  Score    : {result.get('score')}/100")
    print(f"  Risk     : {result.get('risk_level')}")
    print(f"  Market   : {market}")
    print(f"  Output   : {output_dir}")
    print(f"{'='*60}\n")

    # Parse violations (with merge + synthetic audio violation)
    print("━━━ Parsing Violations ━━━")
    violations = parse_violations_from_result(result)
    visual_count = sum(1 for v in violations if v.violation_type == "visual")
    audio_count = sum(1 for v in violations if v.violation_type == "audio")
    print(f"  Total: {len(violations)} ({visual_count} visual, {audio_count} audio)")
    print()

    for i, v in enumerate(violations, 1):
        print(f"  {i}. [{v.timestamp_start:.1f}s-{v.timestamp_end:.1f}s] "
              f"{v.violation_type.upper()} | {v.category}")
        print(f"     {v.description[:80]}")
    print()

    # Run remediation
    print("━━━ Running Remediation ━━━")
    start_time = time.time()

    remediation_result = await orchestrate_remediation(
        video_path=video_path,
        violations=violations,
        market=market,
        ethnicity=ethnicity,
        age_group=age_group,
        language=language,
        output_dir=output_dir,
    )

    elapsed = time.time() - start_time

    # Display results
    print(f"\n{'='*60}")
    print(f"  REMEDIATION COMPLETE")
    print(f"{'='*60}")
    print(f"  Final Video   : {remediation_result.final_video_path}")
    print(f"  Fixed         : {remediation_result.violations_fixed}/{len(violations)}")
    print(f"  Failed        : {remediation_result.violations_failed}/{len(violations)}")
    print(f"  Total Time    : {elapsed:.1f}s")
    print(f"  Processing    : {remediation_result.total_processing_time_ms}ms")
    print(f"{'='*60}\n")

    # Process log
    if remediation_result.process_log:
        print("  PROCESS LOG:")
        print(f"  {'-'*55}")
        for entry in remediation_result.process_log:
            status = "✓" if entry.success else "✗"
            print(f"  {status} [{entry.action:18s}] {entry.duration_ms:>6}ms | "
                  f"{'OK' if entry.success else entry.details.get('error', 'failed')[:40]}")
        print()

    # Save result
    output_file = "remediation_result.json"
    output_data = {
        "final_video_path": remediation_result.final_video_path,
        "violations_fixed": remediation_result.violations_fixed,
        "violations_failed": remediation_result.violations_failed,
        "total_processing_time_ms": remediation_result.total_processing_time_ms,
        "elapsed_seconds": round(elapsed, 1),
        "process_log": [
            {
                "timestamp": e.timestamp,
                "action": e.action,
                "details": e.details,
                "duration_ms": e.duration_ms,
                "success": e.success,
            }
            for e in remediation_result.process_log
        ],
    }
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f"  Result saved to: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
