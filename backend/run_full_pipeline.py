"""
Full Pipeline: Check → Parse → Remediate
Usage: python run_full_pipeline.py

Runs the complete video compliance pipeline:
  Phase 1: Check compliance (video_checker.py)
  Phase 2: Parse violations from result
  Phase 3: Remediate violations (orchestrator.py)
  Phase 4: Output final video + process log
"""

import asyncio
import json
import os
import sys
import logging
import time

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Ensure backend/ is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from jusads_video_compliance.video_checker import VideoComplianceChecker
from jusads_video_compliance.models import Violation
from jusads_video_compliance.orchestrator import orchestrate_remediation


# --- Phase 2: Parse violations from compliance result ---

def parse_violations(result: dict) -> list[Violation]:
    """Convert high_risk_indicators from compliance result into Violation objects.

    Parses timestamp ranges like "[00:03-00:04] description (Visual)"
    into structured Violation objects, then merges overlapping visual
    segments into consolidated violations.

    Args:
        result: The compliance check result dict.

    Returns:
        List of Violation objects ready for remediation (non-overlapping).
    """
    import re

    indicators = result.get("high_risk_indicators", [])
    score = result.get("score", 0)
    raw_violations = []

    for indicator in indicators:
        if not isinstance(indicator, str):
            continue

        # Parse timestamp range: [MM:SS-MM:SS]
        range_pattern = r"\[(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})\]"
        match = re.search(range_pattern, indicator)

        if match:
            start_parts = match.group(1).split(":")
            end_parts = match.group(2).split(":")
            timestamp_start = int(start_parts[0]) * 60 + int(start_parts[1])
            timestamp_end = int(end_parts[0]) * 60 + int(end_parts[1])
            description = indicator[match.end():].strip()
        else:
            # Single timestamp or no timestamp
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

        # Ensure valid range
        if timestamp_end <= timestamp_start:
            timestamp_end = timestamp_start + 1.0

        # Determine violation type from indicator text
        text_lower = indicator.lower()
        if "(audio)" in text_lower or any(kw in text_lower for kw in ["spoken", "dialogue", "voice", "claim"]):
            violation_type = "audio"
        else:
            violation_type = "visual"

        # Determine severity from score
        if score < 40:
            severity = "Severe"
        elif score < 75:
            severity = "Moderate"
        else:
            severity = "Minor"

        # Determine category
        category = "Sexual/Explicit"  # default
        if any(kw in text_lower for kw in ["religious", "hijab", "halal", "mosque"]):
            category = "Religious Sensitivity"
        elif any(kw in text_lower for kw in ["ethnic", "racial"]):
            category = "Ethnic/Racial"

        # Truncate description
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

    # Merge overlapping visual violations into consolidated segments
    visual_raw = [v for v in raw_violations if v["violation_type"] == "visual"]
    audio_raw = [v for v in raw_violations if v["violation_type"] == "audio"]

    merged_visual = _merge_overlapping_segments(visual_raw)
    merged_audio = _merge_overlapping_segments(audio_raw)

    # Convert to Violation objects
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


def _merge_overlapping_segments(segments: list[dict]) -> list[dict]:
    """Merge overlapping time segments into non-overlapping consolidated segments.

    Segments that overlap or are adjacent are merged. The merged segment
    takes the earliest start, latest end, highest severity, and combines
    descriptions.

    Args:
        segments: List of violation dicts with timestamp_start/end.

    Returns:
        List of merged, non-overlapping violation dicts.
    """
    if not segments:
        return []

    # Sort by start time
    sorted_segs = sorted(segments, key=lambda s: s["timestamp_start"])

    merged = [sorted_segs[0].copy()]

    for seg in sorted_segs[1:]:
        last = merged[-1]
        # If overlapping or adjacent (within 0.5s gap), merge
        if seg["timestamp_start"] <= last["timestamp_end"] + 0.5:
            # Extend the end time
            last["timestamp_end"] = max(last["timestamp_end"], seg["timestamp_end"])
            # Combine descriptions
            if seg["description"] not in last["description"]:
                combined = f"{last['description']}; {seg['description']}"
                last["description"] = combined[:200]
            # Take highest severity
            severity_rank = {"Severe": 3, "Moderate": 2, "Minor": 1}
            if severity_rank.get(seg["severity"], 0) > severity_rank.get(last["severity"], 0):
                last["severity"] = seg["severity"]
        else:
            merged.append(seg.copy())

    return merged


async def run_pipeline():
    """Run the full pipeline: Check → Parse → Remediate."""

    video_path = os.path.join("assets", "Test Video.mp4")
    market = "malaysia"
    ethnicity = "malay"
    age_group = "all_ages"
    language = "ms"

    # Create a numbered run folder: assets/remediated/1, /2, etc.
    base_output_dir = os.path.join("assets", "remediated")
    os.makedirs(base_output_dir, exist_ok=True)

    # Find next run number
    existing_runs = [
        int(d) for d in os.listdir(base_output_dir)
        if os.path.isdir(os.path.join(base_output_dir, d)) and d.isdigit()
    ]
    run_number = max(existing_runs, default=0) + 1
    output_dir = os.path.join(base_output_dir, str(run_number))

    if not os.path.isfile(video_path):
        print(f"ERROR: Video file not found: {video_path}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  JusAds Full Pipeline: Check → Remediate (Run #{run_number})")
    print(f"{'='*60}")
    print(f"  Video    : {video_path}")
    print(f"  Market   : {market}")
    print(f"  Ethnicity: {ethnicity}")
    print(f"  Age Group: {age_group}")
    print(f"  Language : {language}")
    print(f"  Output   : {output_dir}")
    print(f"{'='*60}\n")

    pipeline_start = time.time()

    # ━━━ PHASE 1: Compliance Check ━━━
    print("━━━ PHASE 1: Compliance Check ━━━")
    checker = VideoComplianceChecker()
    result = checker.check_compliance(
        video_path=video_path,
        market=market,
        ethnicity=ethnicity,
        age_group=age_group,
    )

    risk_level = result.get("risk_level", "Unknown")
    score = result.get("score", 0)
    indicators = result.get("high_risk_indicators", [])

    print(f"  Risk Level: {risk_level}")
    print(f"  Score: {score}/100")
    print(f"  Violations: {len(indicators)}")
    print()

    # Save compliance result
    with open("compliance_result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    # ━━━ PHASE 2: Parse Violations ━━━
    print("━━━ PHASE 2: Parse Violations ━━━")
    violations = parse_violations(result)
    visual_count = sum(1 for v in violations if v.violation_type == "visual")
    audio_count = sum(1 for v in violations if v.violation_type == "audio")
    print(f"  Parsed: {len(violations)} violations ({visual_count} visual, {audio_count} audio)")

    for i, v in enumerate(violations, 1):
        print(f"  {i}. [{v.timestamp_start:.1f}s-{v.timestamp_end:.1f}s] "
              f"{v.violation_type.upper()} | {v.category} | {v.description[:60]}")
    print()

    # Check if remediation is needed
    if score >= 75:
        print("  ✅ Video is compliant (score >= 75). No remediation needed.")
        return

    # ━━━ PHASE 3: Remediation ━━━
    print("━━━ PHASE 3: Remediation ━━━")
    print(f"  Starting remediation of {len(violations)} violations...")
    print()

    os.makedirs(output_dir, exist_ok=True)

    remediation_result = await orchestrate_remediation(
        video_path=video_path,
        violations=violations,
        market=market,
        ethnicity=ethnicity,
        age_group=age_group,
        language=language,
        output_dir=output_dir,
    )

    # ━━━ PHASE 4: Results ━━━
    total_time = time.time() - pipeline_start
    print(f"\n{'='*60}")
    print(f"  PIPELINE COMPLETE")
    print(f"{'='*60}")
    print(f"  Final Video   : {remediation_result.final_video_path}")
    print(f"  Fixed         : {remediation_result.violations_fixed}/{len(violations)}")
    print(f"  Failed        : {remediation_result.violations_failed}/{len(violations)}")
    print(f"  Total Time    : {total_time:.1f}s")
    print(f"  Processing    : {remediation_result.total_processing_time_ms}ms")
    print(f"{'='*60}\n")

    # Display process log
    if remediation_result.process_log:
        print("  PROCESS LOG:")
        print(f"  {'-'*50}")
        for entry in remediation_result.process_log:
            status = "✓" if entry.success else "✗"
            print(f"  {status} [{entry.action}] {entry.duration_ms}ms")
            if not entry.success and "error" in entry.details:
                print(f"    Error: {entry.details['error'][:80]}")
        print()

    # Save full pipeline result inside the run folder
    pipeline_output = {
        "run": run_number,
        "output_dir": output_dir,
        "video_path": video_path,
        "compliance_check": {
            "risk_level": result.get("risk_level"),
            "score": result.get("score"),
            "high_risk_indicators": result.get("high_risk_indicators"),
        },
        "violations_parsed": len(violations),
        "remediation": {
            "final_video_path": remediation_result.final_video_path,
            "violations_fixed": remediation_result.violations_fixed,
            "violations_failed": remediation_result.violations_failed,
            "total_processing_time_ms": remediation_result.total_processing_time_ms,
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
        },
        "total_pipeline_time_seconds": round(total_time, 1),
    }

    # Save result in the run folder
    output_file = os.path.join(output_dir, "result.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(pipeline_output, f, indent=2, ensure_ascii=False)
    print(f"  Full pipeline result saved to: {output_file}")


if __name__ == "__main__":
    asyncio.run(run_pipeline())
