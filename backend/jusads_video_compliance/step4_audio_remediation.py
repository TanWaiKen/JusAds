"""
Step 4: Audio Remediation
===========================
For each audio violation:
  1. Extract audio segment from video (FFmpeg)
  2. Regenerate with ElevenLabs TTS (matching voice/language)
"""

import logging
import os
import uuid

from jusads_video_compliance.audio_remediator import (
    extract_audio_segment,
    regenerate_with_elevenlabs,
    select_voice,
)

logger = logging.getLogger(__name__)


async def remediate_audio(
    video_path: str,
    violations: list[dict],
    output_dir: str,
    market: str,
    ethnicity: str,
    language: str,
) -> list[dict]:
    """
    Remediate all audio violations.

    Args:
        video_path: Path to the source video.
        violations: List of audio violation dicts from Step 2.
        output_dir: Directory to save output files.
        market: Target market for voice selection.
        ethnicity: Target ethnicity for voice selection.
        language: Language code for TTS.

    Returns:
        List of result dicts with: success, original_start, original_end,
        extracted_path, regen_path, error.
    """
    if not violations:
        return []

    # Select voice once for all audio violations
    voice = select_voice(market=market, ethnicity=ethnicity, age_group="all_ages", language=language)
    print(f"  Voice: {voice.voice_id} ({voice.market}/{voice.ethnicity}/{voice.gender})")

    results = []
    for i, v in enumerate(violations):
        print(f"  [{i+1}/{len(violations)}] Fixing audio: {v['description'][:50]}...")
        result = await _fix_one_audio(video_path, v, output_dir, voice)
        results.append(result)

    return results


async def _fix_one_audio(video_path: str, violation: dict, output_dir: str, voice) -> dict:
    """Fix a single audio violation."""
    segment_id = uuid.uuid4().hex[:8]
    start = violation["start"]
    end = violation["end"]
    duration = end - start

    # 1. Extract audio segment
    extracted_path = os.path.join(output_dir, f"extracted_{segment_id}.mp3")
    if not extract_audio_segment(video_path, start, end, extracted_path):
        return _fail(start, end, "Audio extraction failed")

    # 2. Regenerate with ElevenLabs
    regen_path = os.path.join(output_dir, f"regen_{segment_id}.mp3")
    success = await regenerate_with_elevenlabs(
        text=violation["description"],
        voice_id=voice.voice_id,
        language_code=voice.language_code,
        target_duration=duration,
        output_path=regen_path,
    )

    if not success:
        return _fail(start, end, "ElevenLabs TTS failed")

    return {
        "success": True,
        "original_start": start,
        "original_end": end,
        "extracted_path": extracted_path,
        "regen_path": regen_path,
        "error": None,
    }


def _fail(start: float, end: float, error: str) -> dict:
    """Return a failure result."""
    logger.error(error)
    return {
        "success": False,
        "original_start": start,
        "original_end": end,
        "extracted_path": "",
        "regen_path": "",
        "error": error,
    }
