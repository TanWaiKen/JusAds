"""Media-specific evidence agent for compliance findings."""

from __future__ import annotations

import re

from jusads_compliance.compliance_tools import segment_violations_clipseg
from jusads_compliance.progress_tracker import ProgressTracker
from shared.models import Compliance_State

_tracker = ProgressTracker()


def _invoke(tool, payload: dict) -> dict:
    return tool.invoke(payload) if hasattr(tool, "invoke") else tool(**payload)


def _text_annotations(text: str, indicators: list[str]) -> list[dict]:
    annotations: list[dict] = []
    normalized = text.lower()
    for indicator in indicators:
        keywords = [word for word in re.findall(r"[A-Za-z]{4,}", indicator.lower())]
        index = next((normalized.find(word) for word in keywords if normalized.find(word) >= 0), -1)
        if index >= 0:
            annotations.append({
                "start": index,
                "end": index + len(next(word for word in keywords if normalized.find(word) == index)),
                "text": text[index:index + 160],
                "reason": indicator,
                "render": "underline",
            })
    return annotations


def _timestamp_seconds(value: str) -> float:
    parts = [float(part) for part in value.strip().split(":")]
    return parts[0] if len(parts) == 1 else parts[-1] + (parts[-2] * 60)


def _indicator_ranges(indicators: list[str]) -> list[dict]:
    ranges: list[dict] = []
    for indicator in indicators:
        match = re.match(r"^\s*\[([^\]-]+)\s*[-–]\s*([^\]]+)]\s*(.*)$", indicator)
        if not match:
            continue
        try:
            ranges.append({
                "start_seconds": _timestamp_seconds(match.group(1)),
                "end_seconds": _timestamp_seconds(match.group(2)),
                "indicator": match.group(3).strip(),
            })
        except ValueError:
            continue
    return ranges


def _timeline_with_evidence(timeline: list, indicators: list[str]) -> list[dict]:
    """Replace placeholder video timings with ranges cited by the same analysis."""
    evidence_ranges = _indicator_ranges(indicators)
    normalised: list[dict] = []
    for index, raw_item in enumerate(timeline):
        item = dict(raw_item) if isinstance(raw_item, dict) else {"description": str(raw_item)}
        start = float(item.get("start_seconds", item.get("start", 0)) or 0)
        end = float(item.get("end_seconds", item.get("end", 0)) or 0)
        if end <= start and evidence_ranges:
            description_words = set(re.findall(r"[a-z]{4,}", item.get("description", "").lower()))
            ranked = sorted(
                evidence_ranges,
                key=lambda candidate: len(description_words & set(re.findall(r"[a-z]{4,}", candidate["indicator"].lower()))),
                reverse=True,
            )
            best_score = len(description_words & set(re.findall(r"[a-z]{4,}", ranked[0]["indicator"].lower()))) if ranked else 0
            chosen = ranked[0] if best_score else evidence_ranges[min(index, len(evidence_ranges) - 1)]
            if chosen:
                start, end = chosen["start_seconds"], chosen["end_seconds"]
                item["timing_source"] = "high_risk_indicator"
        item["start_seconds"] = start
        item["end_seconds"] = end
        normalised.append(item)
    return normalised


def media_evidence_agent(state: Compliance_State) -> dict:
    """Produce frontend-ready evidence for text, image, video, and audio."""
    task_id = state["task_id"]
    step_name = "media_evidence_agent"
    _tracker.start_step(task_id, step_name)
    result = state.get("result", {}) or {}
    indicators = result.get("high_risk_indicator", [])
    media_type = state["media_type"]

    try:
        if media_type == "text":
            result["text_annotations"] = _text_annotations(state.get("text_input", ""), indicators)
        elif media_type == "image" and indicators:
            result["segmentation"] = _invoke(segment_violations_clipseg, {
                "image_path": state["input_path"], "high_risk_indicators": indicators,
            })
        elif media_type == "video":
            timeline = _timeline_with_evidence(result.get("violations_timeline") or [], indicators)
            if not timeline:
                timeline = [
                    {"start_seconds": item["start_seconds"], "end_seconds": item["end_seconds"], "type": "visual", "description": item["indicator"]}
                    for item in _indicator_ranges(indicators)
                ]
            result["violations_timeline"] = timeline
        elif media_type == "audio":
            transcript = result.get("_transcript", {})
            result["audio_annotations"] = {
                "segments": transcript.get("segments", []),
                "violations": result.get("violations_timeline") or [],
            }
        _tracker.complete_step(task_id, step_name, f"Prepared {media_type} evidence")
        return {"result": result}
    except Exception as exc:
        _tracker.fail_step(task_id, step_name, str(exc))
        result["evidence_error"] = str(exc)
        return {"result": result}
