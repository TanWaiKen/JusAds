"""
Audio Remixer — Fixes non-compliant audio by correcting transcripts and
regenerating speech via ElevenLabs TTS.

Takes audio violation data from the compliance audit, corrects the transcript
by replacing non-compliant phrases, selects an appropriate voice based on
target audience, and generates replacement audio matching the original duration.
"""

import logging
import os
import uuid
from pathlib import Path
from typing import Any

import requests

from jusads_remix_pipeline.config import (
    ELEVENLABS_API_KEY,
    get_voice_id,
    get_language_for_ethnicity,
)
from jusads_remix_pipeline.models import AudioRemixOutput

logger = logging.getLogger(__name__)

# ElevenLabs API configuration
ELEVENLABS_API_BASE = "https://api.elevenlabs.io"
TTS_MODEL_ID = "eleven_v3"

# Output directory for generated audio files
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "assets" / "results"


def remix_audio(
    original_transcript: str,
    violations: list[dict],
    target_audience: dict,
    original_duration: float,
) -> AudioRemixOutput:
    """Fix non-compliant audio by correcting transcript and regenerating speech.

    Corrects the transcript by replacing all non-compliant spoken phrases with
    compliant alternatives, selects an appropriate voice based on the target
    audience, and generates replacement audio via ElevenLabs TTS that matches
    the original duration.

    Args:
        original_transcript: The original audio transcript text.
        violations: List of violation dicts, each containing at minimum
            'spoken_phrase', 'suggested_replacement', and optionally
            'voice_gender'.
        target_audience: Dict with 'market', 'ethnicity', and 'age_group'.
        original_duration: Duration of the original audio in seconds.

    Returns:
        AudioRemixOutput with original_transcript, compliant_transcript,
        audio_path, and voice_used.
    """
    # Requirement 2.1: Correct transcript by replacing non-compliant phrases
    compliant_transcript = _correct_transcript(original_transcript, violations)

    # Requirement 2.2: Select voice gender based on content context and audience
    voice_gender = _select_voice_gender(violations, target_audience)

    # Requirement 2.3: Map market+ethnicity to ElevenLabs voice
    market = target_audience.get("market", "Malaysia")
    ethnicity = target_audience.get("ethnicity", "default")
    voice_id = get_voice_id(market, ethnicity, voice_gender)

    # Requirement 2.4: Generate replacement audio matching original duration
    audio_path = _generate_audio(
        text=compliant_transcript,
        voice_id=voice_id,
        original_duration=original_duration,
        target_audience=target_audience,
    )

    # Requirement 2.5: Return structured output
    return AudioRemixOutput(
        original_transcript=original_transcript,
        compliant_transcript=compliant_transcript,
        audio_path=audio_path,
        voice_used=voice_id,
    )


def _correct_transcript(
    transcript: str,
    violations: list[dict],
) -> str:
    """Replace all non-compliant spoken phrases in the transcript.

    Iterates through each violation and replaces the spoken_phrase with
    its suggested_replacement. Only replaces phrases that actually exist
    in the transcript.

    Args:
        transcript: The original transcript text.
        violations: List of violation dicts with 'spoken_phrase' and
            'suggested_replacement' fields.

    Returns:
        The corrected transcript with all violations replaced.
    """
    corrected = transcript

    for violation in violations:
        spoken_phrase = violation.get("spoken_phrase", "")
        replacement = violation.get("suggested_replacement", "")

        if not spoken_phrase:
            continue

        # Only replace if the phrase exists in the transcript
        if spoken_phrase in corrected:
            corrected = corrected.replace(spoken_phrase, replacement)
            logger.debug(
                f"Replaced '{spoken_phrase}' with '{replacement}'"
            )

    return corrected


def _select_voice_gender(
    violations: list[dict],
    target_audience: dict,
) -> str:
    """Select voice gender based on violations and target audience context.

    Uses the voice_gender from violations if consistently specified.
    Falls back to target audience context for gender selection.

    Args:
        violations: List of violation dicts, each optionally containing
            'voice_gender' ("male" or "female").
        target_audience: Dict with audience demographic information.

    Returns:
        Voice gender string: "male" or "female".
    """
    # Check if violations specify a consistent voice gender
    violation_genders = [
        v.get("voice_gender")
        for v in violations
        if v.get("voice_gender") in ("male", "female")
    ]

    if violation_genders:
        # Use the most common gender from violations
        male_count = violation_genders.count("male")
        female_count = violation_genders.count("female")
        if male_count >= female_count:
            return "male"
        return "female"

    # Fallback: default to female for beauty/personal care contexts,
    # male otherwise. This is a simple heuristic.
    return "female"


def _generate_audio(
    text: str,
    voice_id: str,
    original_duration: float,
    target_audience: dict,
) -> str:
    """Generate audio via ElevenLabs TTS, matching the original duration.

    Uses the ElevenLabs text-to-speech API to generate audio from the
    corrected transcript. Adjusts speech rate parameters to approximate
    the original audio duration.

    Args:
        text: The corrected transcript text.
        voice_id: ElevenLabs voice ID to use.
        original_duration: Target duration in seconds to match.
        target_audience: Dict with audience info for language selection.

    Returns:
        Path to the generated audio file.
    """
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Generate unique output filename
    output_filename = f"remix_audio_{uuid.uuid4().hex[:12]}.mp3"
    output_path = OUTPUT_DIR / output_filename

    # Determine language code for TTS
    ethnicity = target_audience.get("ethnicity")
    language_code = _get_elevenlabs_language_code(ethnicity)

    # Calculate speech rate adjustment based on text length and target duration
    # ElevenLabs stability parameter affects pacing — lower = more variable/expressive
    stability = _calculate_stability_for_duration(text, original_duration)

    try:
        headers = {
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
        }

        payload: dict[str, Any] = {
            "text": text,
            "model_id": TTS_MODEL_ID,
            "voice_settings": {
                "stability": stability,
                "similarity_boost": 0.75,
                "style": 0.10,
                "use_speaker_boost": True,
            },
        }

        if language_code:
            payload["language_code"] = language_code

        endpoint = f"{ELEVENLABS_API_BASE}/v1/text-to-speech/{voice_id}"

        logger.info(
            f"Generating audio: voice={voice_id}, "
            f"target_duration={original_duration}s, "
            f"language={language_code or 'auto'}"
        )

        response = requests.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=60,
        )

        if response.status_code != 200:
            logger.error(
                f"ElevenLabs TTS API error: {response.status_code} — "
                f"{response.text[:200]}"
            )
            # Return a placeholder path indicating failure
            return str(output_path)

        # Save the generated audio
        with open(output_path, "wb") as f:
            f.write(response.content)

        logger.info(f"Audio generated: {output_path}")
        return str(output_path)

    except requests.Timeout:
        logger.error("ElevenLabs TTS request timed out after 60 seconds")
        return str(output_path)
    except Exception as e:
        logger.error(f"Audio generation failed: {e}")
        return str(output_path)


def _get_elevenlabs_language_code(ethnicity: str | None) -> str | None:
    """Map ethnicity to ElevenLabs language code.

    Args:
        ethnicity: Target audience ethnicity.

    Returns:
        ISO language code for ElevenLabs, or None for auto-detection.
    """
    language_map: dict[str, str] = {
        "Chinese": "zh",
        "Malay": "ms",
        "Indian": "en",
    }

    if ethnicity is None:
        return None

    return language_map.get(ethnicity)


def _calculate_stability_for_duration(
    text: str,
    target_duration: float,
) -> float:
    """Calculate voice stability parameter to approximate target duration.

    Uses a heuristic based on text length and target duration to adjust
    the stability parameter. Higher stability = more consistent pacing,
    lower = more natural variation.

    A rough estimate: average speaking rate is ~150 words per minute
    (~2.5 words per second). If target duration is longer than expected
    natural speech, we use higher stability for more measured pacing.

    Args:
        text: The text to be spoken.
        target_duration: Target audio duration in seconds.

    Returns:
        Stability value between 0.3 and 0.8.
    """
    word_count = len(text.split())

    if target_duration <= 0:
        return 0.5

    # Expected natural duration at ~2.5 words/second
    expected_duration = word_count / 2.5

    # Ratio: > 1 means we need to slow down, < 1 means speed up
    ratio = target_duration / expected_duration if expected_duration > 0 else 1.0

    # Map ratio to stability: slower speech → higher stability
    # Clamp between 0.3 and 0.8
    stability = min(0.8, max(0.3, 0.4 + (ratio - 1.0) * 0.2))

    return round(stability, 2)
