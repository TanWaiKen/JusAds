"""
Step 2: Parse Violations
==========================
Extracts structured violations from the compliance check result.
Parses timestamps, categories, and merges overlapping segments.
"""

import re


def parse_violations(result: dict) -> list[dict]:
    """
    Parse high_risk_indicators into structured violation dicts.

    Args:
        result: Compliance check result from Step 1.

    Returns:
        List of dicts with: start, end, type, category, description, severity.
    """
    indicators = result.get("high_risk_indicators", [])
    score = result.get("score", 0)
    violations = []

    for indicator in indicators:
        if not isinstance(indicator, str):
            continue

        # Parse timestamp range: [MM:SS-MM:SS]
        match = re.search(r"\[(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})\]", indicator)
        if match:
            start_parts = match.group(1).split(":")
            end_parts = match.group(2).split(":")
            start = int(start_parts[0]) * 60 + int(start_parts[1])
            end = int(end_parts[0]) * 60 + int(end_parts[1])
            description = indicator[match.end():].strip()
        else:
            # Single timestamp
            single = re.search(r"\[(\d{1,2}:\d{2})\]", indicator)
            if single:
                parts = single.group(1).split(":")
                start = int(parts[0]) * 60 + int(parts[1])
                end = start + 2.0
                description = indicator[single.end():].strip()
            else:
                start = 0.0
                end = 2.0
                description = indicator

        if end <= start:
            end = start + 1.0

        # Determine type
        text_lower = indicator.lower()
        if "(audio)" in text_lower or any(kw in text_lower for kw in ["spoken", "dialogue", "voice", "claim"]):
            vtype = "audio"
        else:
            vtype = "visual"

        # Determine severity
        if score < 40:
            severity = "Severe"
        elif score < 75:
            severity = "Moderate"
        else:
            severity = "Minor"

        # Determine category
        category = "Sexual/Explicit"
        if any(kw in text_lower for kw in ["religious", "hijab", "halal", "mosque"]):
            category = "Religious Sensitivity"
        elif any(kw in text_lower for kw in ["ethnic", "racial"]):
            category = "Ethnic/Racial"

        violations.append({
            "start": float(start),
            "end": float(end),
            "type": vtype,
            "category": category,
            "severity": severity,
            "description": description[:200],
        })

    # Merge overlapping visual segments
    visual = sorted([v for v in violations if v["type"] == "visual"], key=lambda v: v["start"])
    audio = [v for v in violations if v["type"] == "audio"]

    merged_visual = _merge_overlapping(visual)
    return merged_visual + audio


def _merge_overlapping(segments: list[dict]) -> list[dict]:
    """Merge overlapping time segments."""
    if not segments:
        return []

    merged = [segments[0].copy()]
    for seg in segments[1:]:
        last = merged[-1]
        if seg["start"] <= last["end"] + 0.5:
            last["end"] = max(last["end"], seg["end"])
            if seg["description"] not in last["description"]:
                last["description"] = f"{last['description']}; {seg['description']}"[:200]
        else:
            merged.append(seg.copy())

    return merged
