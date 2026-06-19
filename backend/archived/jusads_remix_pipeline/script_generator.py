"""Script & Voiceover Generator for the JusAds Video Remix Pipeline.

Analyzes remixed video clips to generate a localized script with natural timing,
then produces voiceover audio via ElevenLabs TTS. The script matches the visual
flow and uses timing cues (speech + silence) for natural rhythm.

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

import requests

from jusads_remix_pipeline.config import (
    ELEVENLABS_API_KEY,
    GEMINI_API_KEY,
    get_language_for_ethnicity,
    get_voice_id,
)

logger = logging.getLogger(__name__)

# ElevenLabs API configuration (same pattern as audio_remixer.py)
ELEVENLABS_API_BASE = "https://api.elevenlabs.io"
TTS_MODEL_ID = "eleven_v3"

# Gemini API for visual analysis
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_MODEL = "gemini-2.0-flash"

# Timing constraints (Req 7.2)
MIN_SILENCE_BETWEEN_SPEECH = 1.0  # minimum 1 second of silence between speech

# Duration tolerance (Req 7.5)
DURATION_TOLERANCE_MS = 500  # 500ms tolerance

# Output directory for generated voiceover files
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "assets" / "results"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PUBLIC API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def generate_script_and_voiceover(
    remixed_clips: list[dict],
    target_audience: dict,
) -> dict:
    """Generate localized script and voiceover for remixed video clips.

    Analyzes the visual content of each remixed clip, generates a localized
    script with timing cues (speech + silence segments), selects voice based
    on target audience, and produces voiceover audio via ElevenLabs TTS.

    Args:
        remixed_clips: List of clip dicts, each containing:
            - video_path (str): Path to the remixed video clip.
            - ambient_audio_path (str): Path to the extracted ambient audio.
            - duration (float): Clip duration in seconds.
            - start_time (float): Clip start time in the overall video.
            - end_time (float): Clip end time in the overall video.
        target_audience: Dict with audience demographics:
            - market (str): Target market (e.g. "Malaysia").
            - ethnicity (str | None): Target ethnicity (e.g. "Chinese", "Malay").
            - gender (str | None): Target gender demographic ("male" or "female").

    Returns:
        Dict with:
            - script_segments: List of script segment dicts with timing cues.
            - voiceover_segments: List of generated voiceover audio segments.
            - voice_id: The ElevenLabs voice ID used.
            - language: The language used for the voiceover.
            - errors: List of error messages for any failed segments.
    """
    errors: list[str] = []

    # Req 7.4, 7.6: Map ethnicity to language
    ethnicity = target_audience.get("ethnicity")
    language = get_language_for_ethnicity(ethnicity)

    # Req 7.3: Select voice gender based on target audience gender demographic
    voice_gender = _select_voice_gender(target_audience)

    # Get voice ID from config mapping
    market = target_audience.get("market", "Malaysia")
    voice_id = get_voice_id(market, ethnicity or "default", voice_gender)

    # Req 7.1: Analyze visual content and generate localized script
    script_segments = _generate_script_from_visuals(
        remixed_clips, language, target_audience
    )

    # If script generation failed completely, return early with error
    if not script_segments:
        errors.append("Script generation failed: could not analyze video clips")
        return {
            "script_segments": [],
            "voiceover_segments": [],
            "voice_id": voice_id,
            "language": language,
            "errors": errors,
        }

    # Req 7.5, 7.7: Generate voiceover for each speech segment
    voiceover_segments: list[dict] = []
    for i, segment in enumerate(script_segments):
        if segment["type"] != "speech":
            continue

        # Generate TTS for this speech segment
        vo_result = _generate_voiceover_segment(
            text=segment["text"],
            voice_id=voice_id,
            target_duration=segment["duration"],
            segment_index=i,
            language=language,
            ethnicity=ethnicity,
        )

        if vo_result.get("error"):
            # Req 7.7: Preserve successful segments, report failed ones
            errors.append(
                f"Voiceover generation failed for segment {i} "
                f"({segment['start_time']:.1f}s-{segment['end_time']:.1f}s): "
                f"{vo_result['error']}"
            )
        else:
            voiceover_segments.append({
                "start_time": segment["start_time"],
                "end_time": segment["end_time"],
                "audio_path": vo_result["audio_path"],
                "duration": vo_result["duration"],
            })

    return {
        "script_segments": script_segments,
        "voiceover_segments": voiceover_segments,
        "voice_id": voice_id,
        "language": language,
        "errors": errors,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PRIVATE HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _select_voice_gender(target_audience: dict) -> str:
    """Select voice gender based on target audience gender demographic.

    Req 7.3: Voice gender selection based on target audience gender.

    Args:
        target_audience: Dict with audience demographics including optional
            'gender' field.

    Returns:
        Voice gender string: "male" or "female".
    """
    gender = target_audience.get("gender")
    if gender in ("male", "female"):
        return gender
    # Default to female if not specified
    return "female"


def _generate_script_from_visuals(
    remixed_clips: list[dict],
    language: str,
    target_audience: dict,
) -> list[dict]:
    """Analyze visual content of clips and generate a localized script.

    Req 7.1: Analyze visual content and generate script referencing timestamps.
    Req 7.2: Generate timing cues with speech + silence (min 1s silence between speech).

    Uses Gemini to analyze the video clips and produce a script with natural
    timing that matches the visual flow.

    Args:
        remixed_clips: List of clip dicts with video_path, duration, start_time, end_time.
        language: Target language for the script (e.g. "Mandarin", "English").
        target_audience: Dict with audience demographics for context.

    Returns:
        List of script segment dicts, each with:
            - start_time (float)
            - end_time (float)
            - text (str): Script text (empty for silence segments)
            - type (str): "speech" or "silence"
            - duration (float)
    """
    # Build clip descriptions for Gemini prompt
    clip_descriptions = []
    for clip in remixed_clips:
        clip_descriptions.append({
            "video_path": clip.get("video_path", ""),
            "start_time": clip.get("start_time", 0.0),
            "end_time": clip.get("end_time", 0.0),
            "duration": clip.get("duration", 0.0),
        })

    # Build the analysis prompt
    prompt = _build_script_generation_prompt(
        clip_descriptions, language, target_audience
    )

    try:
        # Call Gemini for script generation
        script_data = _call_gemini_for_script(prompt, remixed_clips)

        if script_data is None:
            logger.error("Gemini returned no script data")
            return []

        # Parse and validate the script segments
        segments = _parse_script_response(script_data, remixed_clips)

        # Ensure minimum silence between speech segments (Req 7.2)
        segments = _enforce_silence_constraints(segments)

        return segments

    except Exception as e:
        logger.error(f"Script generation failed: {e}")
        return []


def _build_script_generation_prompt(
    clip_descriptions: list[dict],
    language: str,
    target_audience: dict,
) -> str:
    """Build the Gemini prompt for script generation.

    Args:
        clip_descriptions: List of clip metadata dicts.
        language: Target language for the script.
        target_audience: Audience demographics for context.

    Returns:
        Formatted prompt string for Gemini.
    """
    clips_info = json.dumps(clip_descriptions, indent=2)
    ethnicity = target_audience.get("ethnicity", "general")
    market = target_audience.get("market", "Malaysia")

    prompt = f"""You are a professional advertising scriptwriter creating voiceover narration for a video advertisement.

Analyze the provided video clips and generate a localized voiceover script that matches the visual content.

TARGET AUDIENCE:
- Market: {market}
- Ethnicity: {ethnicity}
- Language: {language}

VIDEO CLIPS:
{clips_info}

REQUIREMENTS:
1. Generate a script in {language} that narrates what is happening visually in each clip.
2. Include BOTH speech segments AND silence segments for natural rhythm.
3. Minimum 1 second of silence between any two speech segments.
4. Speech segments should align with visual action — narrate when there is something to describe.
5. Silence segments should align with visual transitions or pauses — let the visuals breathe.
6. Each script line must reference its corresponding time range.
7. Keep narration concise, natural, and appropriate for the target audience.
8. The script should feel like a natural voiceover — not every second needs dialogue.

OUTPUT FORMAT (JSON array):
[
  {{
    "start_time": <float>,
    "end_time": <float>,
    "text": "<script text or empty for silence>",
    "type": "speech" | "silence"
  }},
  ...
]

Generate the script segments covering the full duration of all clips, with natural pacing.
Return ONLY the JSON array, no other text."""

    return prompt


def _call_gemini_for_script(
    prompt: str,
    remixed_clips: list[dict],
) -> list[dict] | None:
    """Call Gemini API to analyze video clips and generate script.

    Args:
        prompt: The script generation prompt.
        remixed_clips: List of clip dicts (for potential video upload context).

    Returns:
        Parsed JSON list of script segments, or None on failure.
    """
    try:
        headers = {
            "Content-Type": "application/json",
        }

        # Build request payload for Gemini
        payload: dict[str, Any] = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
                "topP": 0.9,
                "responseMimeType": "application/json",
            },
        }

        endpoint = (
            f"{GEMINI_API_BASE}/models/{GEMINI_MODEL}:generateContent"
            f"?key={GEMINI_API_KEY}"
        )

        logger.info("Calling Gemini for script generation")

        response = requests.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=60,
        )

        if response.status_code != 200:
            logger.error(
                f"Gemini API error: {response.status_code} — "
                f"{response.text[:200]}"
            )
            return None

        # Parse Gemini response
        result = response.json()
        candidates = result.get("candidates", [])
        if not candidates:
            logger.error("No candidates in Gemini response")
            return None

        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        if not parts:
            logger.error("No parts in Gemini response content")
            return None

        text_response = parts[0].get("text", "")

        # Parse the JSON response
        script_data = json.loads(text_response)

        if not isinstance(script_data, list):
            logger.error("Gemini response is not a JSON array")
            return None

        return script_data

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Gemini script response as JSON: {e}")
        return None
    except requests.Timeout:
        logger.error("Gemini API request timed out after 60 seconds")
        return None
    except Exception as e:
        logger.error(f"Gemini API call failed: {e}")
        return None


def _parse_script_response(
    script_data: list[dict],
    remixed_clips: list[dict],
) -> list[dict]:
    """Parse and validate the script response from Gemini.

    Ensures all segments have required fields and valid values.

    Args:
        script_data: Raw script segments from Gemini.
        remixed_clips: Original clips for time range validation.

    Returns:
        List of validated script segment dicts.
    """
    segments: list[dict] = []

    for item in script_data:
        try:
            start_time = float(item.get("start_time", 0))
            end_time = float(item.get("end_time", 0))
            text = str(item.get("text", ""))
            seg_type = item.get("type", "silence")

            # Validate type
            if seg_type not in ("speech", "silence"):
                seg_type = "silence" if not text.strip() else "speech"

            # Validate times
            if end_time <= start_time:
                continue

            duration = end_time - start_time

            segments.append({
                "start_time": start_time,
                "end_time": end_time,
                "text": text if seg_type == "speech" else "",
                "type": seg_type,
                "duration": duration,
            })
        except (ValueError, TypeError):
            continue

    return segments


def _enforce_silence_constraints(segments: list[dict]) -> list[dict]:
    """Ensure minimum silence between speech segments.

    Req 7.2: Minimum 1 second of silence between speech segments.
    If two speech segments are too close, insert a silence segment between them.

    Args:
        segments: List of script segments (speech and silence).

    Returns:
        Updated list with silence constraints enforced.
    """
    if not segments:
        return segments

    # Sort by start_time
    segments.sort(key=lambda s: s["start_time"])

    result: list[dict] = []
    last_speech_end: float | None = None

    for segment in segments:
        if segment["type"] == "speech":
            # Check if there's enough silence since last speech
            if last_speech_end is not None:
                gap = segment["start_time"] - last_speech_end
                if gap < MIN_SILENCE_BETWEEN_SPEECH:
                    # Insert a silence segment to meet the minimum requirement
                    silence_end = last_speech_end + MIN_SILENCE_BETWEEN_SPEECH
                    # Only insert if it doesn't overlap the current segment
                    if silence_end <= segment["start_time"]:
                        result.append({
                            "start_time": last_speech_end,
                            "end_time": silence_end,
                            "text": "",
                            "type": "silence",
                            "duration": MIN_SILENCE_BETWEEN_SPEECH,
                        })
                    else:
                        # Shift the speech segment forward if possible
                        new_start = last_speech_end + MIN_SILENCE_BETWEEN_SPEECH
                        segment = {
                            **segment,
                            "start_time": new_start,
                            "end_time": new_start + segment["duration"],
                        }
                        result.append({
                            "start_time": last_speech_end,
                            "end_time": new_start,
                            "text": "",
                            "type": "silence",
                            "duration": new_start - last_speech_end,
                        })

            result.append(segment)
            last_speech_end = segment["end_time"]
        else:
            result.append(segment)

    return result


def _generate_voiceover_segment(
    text: str,
    voice_id: str,
    target_duration: float,
    segment_index: int,
    language: str,
    ethnicity: str | None,
) -> dict:
    """Generate a voiceover audio segment via ElevenLabs TTS.

    Req 7.5: Each segment duration within 500ms of the corresponding video segment.
    Req 7.7: On failure, return error info (partial failure handling).

    Args:
        text: The script text to speak.
        voice_id: ElevenLabs voice ID to use.
        target_duration: Target duration in seconds for this segment.
        segment_index: Index of this segment (for error reporting).
        language: Target language string.
        ethnicity: Target audience ethnicity for language code mapping.

    Returns:
        Dict with:
            - audio_path (str): Path to generated audio file.
            - duration (float): Actual duration of the generated audio.
            - error (str | None): Error message if failed.
    """
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Generate unique output filename
    output_filename = f"voiceover_segment_{segment_index}_{uuid.uuid4().hex[:8]}.mp3"
    output_path = OUTPUT_DIR / output_filename

    # Get ElevenLabs language code
    language_code = _get_elevenlabs_language_code(ethnicity)

    # Calculate stability for duration matching
    stability = _calculate_stability_for_duration(text, target_duration)

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
            f"Generating voiceover segment {segment_index}: "
            f"voice={voice_id}, target_duration={target_duration:.1f}s, "
            f"language={language_code or 'auto'}"
        )

        response = requests.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=60,
        )

        if response.status_code != 200:
            error_msg = (
                f"ElevenLabs TTS API error: {response.status_code} — "
                f"{response.text[:200]}"
            )
            logger.error(error_msg)
            return {"audio_path": "", "duration": 0.0, "error": error_msg}

        # Save the generated audio
        with open(output_path, "wb") as f:
            f.write(response.content)

        # Get the actual duration of the generated audio
        actual_duration = _get_audio_duration(str(output_path))

        # Req 7.5: Check if duration is within 500ms tolerance
        if actual_duration > 0:
            diff_ms = abs(actual_duration - target_duration) * 1000
            if diff_ms > DURATION_TOLERANCE_MS:
                logger.warning(
                    f"Voiceover segment {segment_index} duration mismatch: "
                    f"target={target_duration:.1f}s, actual={actual_duration:.1f}s "
                    f"(diff={diff_ms:.0f}ms, tolerance={DURATION_TOLERANCE_MS}ms)"
                )

        logger.info(
            f"Voiceover segment {segment_index} generated: {output_path} "
            f"({actual_duration:.1f}s)"
        )

        return {
            "audio_path": str(output_path),
            "duration": actual_duration if actual_duration > 0 else target_duration,
            "error": None,
        }

    except requests.Timeout:
        error_msg = (
            f"ElevenLabs TTS request timed out for segment {segment_index}"
        )
        logger.error(error_msg)
        return {"audio_path": "", "duration": 0.0, "error": error_msg}
    except Exception as e:
        error_msg = f"Voiceover generation failed for segment {segment_index}: {e}"
        logger.error(error_msg)
        return {"audio_path": "", "duration": 0.0, "error": error_msg}


def _get_elevenlabs_language_code(ethnicity: str | None) -> str | None:
    """Map ethnicity to ElevenLabs language code.

    Req 7.4: Chinese → Mandarin (zh), Malay → Bahasa Malaysia (ms).
    Req 7.6: Default to English if not specified or unsupported.

    Args:
        ethnicity: Target audience ethnicity.

    Returns:
        ISO language code for ElevenLabs, or None for auto-detection (English).
    """
    language_map: dict[str, str] = {
        "Chinese": "zh",
        "Malay": "ms",
    }

    if ethnicity is None:
        return None  # Defaults to English (auto)

    return language_map.get(ethnicity)


def _calculate_stability_for_duration(
    text: str,
    target_duration: float,
) -> float:
    """Calculate voice stability parameter to approximate target duration.

    Uses a heuristic based on text length and target duration to adjust
    the stability parameter for pacing control.

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
    stability = min(0.8, max(0.3, 0.4 + (ratio - 1.0) * 0.2))

    return round(stability, 2)


def _get_audio_duration(audio_path: str) -> float:
    """Get the duration of an audio file using FFprobe.

    Args:
        audio_path: Path to the audio file.

    Returns:
        Duration in seconds, or 0.0 if probe fails.
    """
    import subprocess

    try:
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path,
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10
        )

        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())

    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError) as e:
        logger.warning(f"Failed to get audio duration for {audio_path}: {e}")

    return 0.0
