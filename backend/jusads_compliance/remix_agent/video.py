"""Gemini Omni video-to-video remediation with timeline-aware assembly."""

import json
import os
import shutil
import subprocess
import tempfile
import urllib.request


def _range(item: dict) -> tuple[float, float] | None:
    try:
        start = float(item.get("start_seconds", item.get("start")))
        end = float(item.get("end_seconds", item.get("end")))
    except (TypeError, ValueError):
        return None
    return (start, end) if end > start else None


def _duration(path: str) -> float:
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, timeout=20,
    )
    return float(probe.stdout.strip())


def _media_profile(path: str) -> tuple[int, int, str, int]:
    """Read the original profile used to make every concatenated part compatible."""
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-of", "json", "-show_streams", path],
        capture_output=True, text=True, timeout=20, check=True,
    )
    streams = json.loads(probe.stdout).get("streams", [])
    video = next(stream for stream in streams if stream.get("codec_type") == "video")
    audio = next(stream for stream in streams if stream.get("codec_type") == "audio")
    return int(video["width"]), int(video["height"]), video.get("r_frame_rate", "30/1"), int(audio.get("sample_rate", 44100))


def _extract(source: str, start: float, end: float, destination: str) -> None:
    command = [
        "ffmpeg", "-y", "-ss", f"{start:.3f}", "-i", source,
        "-t", f"{end - start:.3f}", "-c:v", "libx264", "-c:a", "aac",
        "-movflags", "+faststart", destination,
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=300)
    if completed.returncode or not os.path.isfile(destination):
        raise RuntimeError(f"Could not extract video segment: {completed.stderr[-400:]}")


def _edit_windows(timeline: list[dict], duration: float) -> list[tuple[float, float]]:
    """Produce disjoint ≤10s source windows that cover every visual issue."""
    ranges = sorted((_range(item) for item in timeline), key=lambda item: item[0])
    ranges = [item for item in ranges if item]
    if not ranges:
        return []

    windows: list[tuple[float, float]] = []
    group_start, group_end = ranges[0]
    for start, end in ranges[1:]:
        # Nearby findings usually belong to the same shot. Preserve enough
        # context for a single coherent edit instead of changing the talent or
        # styling independently every second.
        if start <= group_end + 4 and end - group_start <= 10:
            group_end = max(group_end, end)
            continue
        windows.extend(_split_window(group_start, group_end, duration))
        group_start, group_end = start, end
    windows.extend(_split_window(group_start, group_end, duration))
    return windows


def _split_window(start: float, end: float, duration: float) -> list[tuple[float, float]]:
    span = end - start
    if span <= 10:
        length = min(10.0, max(3.0, span + 2.0))
        window_start = max(0.0, min(start - 1.0, duration - length))
        return [(window_start, min(duration, window_start + length))]
    windows: list[tuple[float, float]] = []
    cursor = start
    while cursor < end:
        window_end = min(cursor + 10.0, end)
        windows.append((cursor, window_end))
        cursor = window_end
    return windows


def _concat(parts: list[str], output_path: str, profile: tuple[int, int, str, int]) -> None:
    width, height, frame_rate, sample_rate = profile
    inputs = [item for path in parts for item in ("-i", path)]
    filters = ";".join(
        f"[{index}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={frame_rate},setpts=PTS-STARTPTS[v{index}];"
        f"[{index}:a]aresample={sample_rate},asetpts=PTS-STARTPTS[a{index}]"
        for index in range(len(parts))
    )
    joined = "".join(f"[v{index}][a{index}]" for index in range(len(parts)))
    command = [
        "ffmpeg", "-y", *inputs, "-filter_complex", f"{filters};{joined}concat=n={len(parts)}:v=1:a=1[v][a]",
        "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-c:a", "aac", "-movflags", "+faststart", output_path,
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=600)
    if completed.returncode or not os.path.isfile(output_path):
        raise RuntimeError(f"Could not assemble Omni-edited video: {completed.stderr[-500:]}")


def _capcut_draft(parts: list[str], task_id: str, profile: tuple[int, int, str, int]) -> dict:
    """Persist editable segment copies and build a CapCut timeline from them."""
    from jusads_compliance.capcut_client import DRAFTS_DIR, create_multi_scene_draft

    media_dir = os.path.join(DRAFTS_DIR, "media", task_id)
    os.makedirs(media_dir, exist_ok=True)
    draft_clips: list[str] = []
    for index, source in enumerate(parts):
        destination = os.path.join(media_dir, f"{index + 1:02d}_{os.path.basename(source)}")
        shutil.copy2(source, destination)
        draft_clips.append(destination)

    width, height, frame_rate, _ = profile
    try:
        numerator, denominator = frame_rate.split("/", 1)
        fps = max(1, round(float(numerator) / float(denominator)))
    except (ValueError, ZeroDivisionError):
        fps = 30
    draft = create_multi_scene_draft(
        draft_clips,
        draft_name=f"omni_compliance_{task_id}",
        width=width,
        height=height,
        fps=fps,
    )
    return draft or {
        "warning": "CapCut draft library is unavailable; editable segment files were saved locally.",
        "media_folder": media_dir,
        "scene_count": len(draft_clips),
    }


def remediate_video(state: dict) -> dict:
    """Edit only timestamped problem windows; safe footage remains byte-faithful in content."""
    plan = state.get("remediation_plan", {})
    timeline = [item for item in plan.get("violations_timeline") or [] if isinstance(item, dict) and _range(item)]
    if not timeline:
        return {"error": "Video remediation requires timestamped compliance findings."}

    task_id = state["task_id"]
    source_path = os.path.join(tempfile.gettempdir(), f"source_{task_id}.mp4")
    urllib.request.urlretrieve(state["source_media_url"], source_path)
    temporary_paths = [source_path]
    try:
        source_duration = _duration(source_path)
        source_profile = _media_profile(source_path)
        windows = _edit_windows(timeline, source_duration)
        if len(windows) > 3:
            return {"error": "This video needs more than three Omni edit windows; split it into scenes for review before regeneration."}

        from jusads_compliance.remediation_executor import _execute_omni_video_edit

        localisation = plan.get("localization_plan") or ""
        localization = plan.get("localization") or {}
        output_language = localization.get("output_language", "the language required by the localization plan")
        tone = localization.get("tone", "clear and audience-appropriate")
        instructions = (
            "Use the supplied clip as the original reference and edit it in place. "
            "Preserve the product, brand, camera movement, framing, timing, and safe content. "
            "Change only the timestamped compliance concerns: use non-suggestive lifestyle framing, "
            "appropriate non-stereotyped talent and attire where genuinely needed. "
            f"Any replacement copy or speech MUST be in {output_language}, with a {tone} tone. "
            "Do not make unsupported health, certification, or efficacy claims. "
            f"Localisation plan: {localisation}"
        )
        edited_windows: list[tuple[float, float, str]] = []
        interactions: list[str] = []
        for index, (start, end) in enumerate(windows):
            source_clip = os.path.join(tempfile.gettempdir(), f"omni_source_{task_id}_{index}.mp4")
            _extract(source_path, start, end, source_clip)
            temporary_paths.append(source_clip)
            edited = _execute_omni_video_edit(source_clip, instructions)
            if edited.get("error"):
                return {"error": edited["error"]}
            output = edited.get("output_path")
            if not output or not os.path.isfile(output):
                return {"error": "Gemini Omni returned no usable edited video."}
            temporary_paths.append(output)
            edited_windows.append((start, end, output))
            if edited.get("interaction_id"):
                interactions.append(edited["interaction_id"])

        parts: list[str] = []
        cursor = 0.0
        for index, (start, end, edited_path) in enumerate(edited_windows):
            if start > cursor + 0.01:
                original_part = os.path.join(tempfile.gettempdir(), f"omni_original_{task_id}_{index}.mp4")
                _extract(source_path, cursor, start, original_part)
                temporary_paths.append(original_part)
                parts.append(original_part)
            normalised_edit = os.path.join(tempfile.gettempdir(), f"omni_edited_{task_id}_{index}.mp4")
            _extract(edited_path, 0, end - start, normalised_edit)
            temporary_paths.append(normalised_edit)
            parts.append(normalised_edit)
            cursor = end
        if cursor < source_duration - 0.01:
            original_part = os.path.join(tempfile.gettempdir(), f"omni_original_{task_id}_tail.mp4")
            _extract(source_path, cursor, source_duration, original_part)
            temporary_paths.append(original_part)
            parts.append(original_part)

        output_path = os.path.join(tempfile.gettempdir(), f"remediated_video_{task_id}.mp4")
        _concat(parts, output_path, source_profile)
        capcut_draft = _capcut_draft(parts, task_id, source_profile)
        return {
            "output_path": output_path,
            "strategy": "omni_video_reference_edit",
            "violation_segments": [
                {"start_seconds": start, "end_seconds": end, "type": item.get("type", "visual"), "description": item.get("description", "Compliance finding")}
                for item in timeline for start, end in [_range(item)]
            ],
            "omni_edit_status": "completed",
            "omni_interaction_ids": interactions,
            "verification_status": "pending_compliance_recheck",
            "capcut_draft": capcut_draft,
        }
    except Exception as exc:
        return {"error": f"Omni video remediation failed: {exc}"}
    finally:
        for path in temporary_paths:
            if path != os.path.join(tempfile.gettempdir(), f"remediated_video_{task_id}.mp4"):
                try:
                    if os.path.isfile(path):
                        os.remove(path)
                except OSError:
                    pass
