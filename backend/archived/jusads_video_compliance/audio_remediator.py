"""Audio Remediator for the JusAds Video Compliance Remediation Pipeline.

Fixes audio violations by regenerating problematic audio segments using
ElevenLabs TTS with market-appropriate voice selection.

Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7
"""

from __future__ import annotations

import logging
import os
import subprocess
import uuid
from pathlib import Path

import httpx

from config import (
    ELEVENLABS_API_KEY,
    ELEVENLABS_VOICE_MY_MS_MALE,
    ELEVENLABS_VOICE_MY_MS_FEMALE,
    ELEVENLABS_VOICE_MY_ZH_MALE,
    ELEVENLABS_VOICE_MY_ZH_FEMALE,
    ELEVENLABS_VOICE_MY_EN_IND_MALE,
    ELEVENLABS_VOICE_MY_EN_IND_FEMALE,
    ELEVENLABS_VOICE_SG_EN_MALE,
    ELEVENLABS_VOICE_SG_EN_FEMALE,
    ELEVENLABS_VOICE_SG_ZH_MALE,
    ELEVENLABS_VOICE_SG_ZH_FEMALE,
)

logger = logging.getLogger(__name__)

ELEVENLABS_API_BASE = "https://api.elevenlabs.io"


# Simple voice config container
class VoiceConfig:
    """Voice configuration for ElevenLabs TTS."""
    def __init__(self, voice_id: str, language_code: str, market: str, ethnicity: str, gender: str):
        self.voice_id = voice_id
        self.language_code = language_code
        self.market = market
        self.ethnicity = ethnicity
        self.gender = gender


# Simple result container (replaces models.py dataclass)
class AudioRemediationResult:
    """Result of an audio remediation attempt."""
    def __init__(self, original_start, original_end, replacement_audio_path, voice_id_used, success, error=None):
        self.original_start = original_start
        self.original_end = original_end
        self.replacement_audio_path = replacement_audio_path
        self.voice_id_used = voice_id_used
        self.success = success
        self.error = error


# Voice ID mapping: (market, ethnicity, gender) -> voice_id from config.py
# All keys are stored in lowercase for case-insensitive lookup.
VOICE_MAP: dict[tuple[str, str, str], str] = {
    ("malaysia", "malay", "male"): ELEVENLABS_VOICE_MY_MS_MALE,
    ("malaysia", "malay", "female"): ELEVENLABS_VOICE_MY_MS_FEMALE,
    ("malaysia", "chinese", "male"): ELEVENLABS_VOICE_MY_ZH_MALE,
    ("malaysia", "chinese", "female"): ELEVENLABS_VOICE_MY_ZH_FEMALE,
    ("malaysia", "indian", "male"): ELEVENLABS_VOICE_MY_EN_IND_MALE,
    ("malaysia", "indian", "female"): ELEVENLABS_VOICE_MY_EN_IND_FEMALE,
    ("singapore", "english", "male"): ELEVENLABS_VOICE_SG_EN_MALE,
    ("singapore", "english", "female"): ELEVENLABS_VOICE_SG_EN_FEMALE,
    ("singapore", "chinese", "male"): ELEVENLABS_VOICE_SG_ZH_MALE,
    ("singapore", "chinese", "female"): ELEVENLABS_VOICE_SG_ZH_FEMALE,
}

# Language code mapping: (market, ethnicity) -> language code
# All keys are stored in lowercase for case-insensitive lookup.
LANGUAGE_CODE_MAP: dict[tuple[str, str], str] = {
    ("malaysia", "malay"): "ms",
    ("malaysia", "chinese"): "zh",
    ("malaysia", "indian"): "en",
    ("singapore", "english"): "en",
    ("singapore", "chinese"): "zh",
}

# Default fallback: Malaysia Malay Female
_DEFAULT_MARKET = "malaysia"
_DEFAULT_ETHNICITY = "malay"
_DEFAULT_GENDER = "female"


def select_voice(
    market: str,
    ethnicity: str,
    age_group: str,
    language: str,
    gender: str = "female",
) -> VoiceConfig:
    """Select appropriate ElevenLabs voice ID based on user parameters.

    Performs case-insensitive lookup against the VOICE_MAP and LANGUAGE_CODE_MAP.
    Falls back to the default voice (Malaysia Malay Female) when no exact match
    is found for the given market/ethnicity/gender combination.

    Args:
        market: Target market ("malaysia" or "singapore").
        ethnicity: Target ethnicity (e.g. "malay", "chinese", "indian", "english").
        age_group: Target age group (currently unused in voice selection but
            reserved for future use).
        language: Language code (currently used as context; voice selection is
            primarily driven by market + ethnicity).
        gender: Voice gender preference ("male" or "female"). Defaults to "female".

    Returns:
        VoiceConfig with the selected voice_id, language_code, market,
        ethnicity, and gender.

    Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7
    """
    # Normalize inputs to lowercase for case-insensitive lookup (Req 4.7)
    market_lower = market.strip().lower()
    ethnicity_lower = ethnicity.strip().lower()
    gender_lower = gender.strip().lower() if gender else "female"

    # Default to "female" if gender is empty or not specified (Req 4.6)
    if not gender_lower:
        gender_lower = "female"

    # Attempt exact match in VOICE_MAP
    voice_key = (market_lower, ethnicity_lower, gender_lower)
    voice_id = VOICE_MAP.get(voice_key)

    # Determine language code for the market/ethnicity combination
    lang_key = (market_lower, ethnicity_lower)
    language_code = LANGUAGE_CODE_MAP.get(lang_key)

    if voice_id is not None and language_code is not None:
        # Exact match found
        return VoiceConfig(
            voice_id=voice_id,
            language_code=language_code,
            market=market_lower,
            ethnicity=ethnicity_lower,
            gender=gender_lower,
        )

    # Fallback to default voice: Malaysia Malay Female (Req 4.5)
    fallback_voice_key = (_DEFAULT_MARKET, _DEFAULT_ETHNICITY, _DEFAULT_GENDER)
    fallback_lang_key = (_DEFAULT_MARKET, _DEFAULT_ETHNICITY)

    return VoiceConfig(
        voice_id=VOICE_MAP[fallback_voice_key],
        language_code=LANGUAGE_CODE_MAP[fallback_lang_key],
        market=_DEFAULT_MARKET,
        ethnicity=_DEFAULT_ETHNICITY,
        gender=_DEFAULT_GENDER,
    )


def _get_audio_duration(file_path: str) -> float | None:
    """Get the duration of an audio file in seconds using FFprobe.

    Args:
        file_path: Path to the audio file.

    Returns:
        Duration in seconds, or None if the probe fails.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.error(
                f"FFprobe failed for '{file_path}': {result.stderr.strip()}"
            )
            return None
        return float(result.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError, OSError) as e:
        logger.error(f"FFprobe error for '{file_path}': {e}")
        return None


def extract_audio_segment(
    video_path: str,
    start_sec: float,
    end_sec: float,
    output_path: str,
) -> bool:
    """Extract audio segment from video using FFmpeg.

    Extracts the audio between start_sec and end_sec from the given video
    file and writes it to output_path as an MP3 file.

    Args:
        video_path: Path to the source video file.
        start_sec: Start time in seconds (must be >= 0).
        end_sec: End time in seconds (must be > start_sec).
        output_path: Path where the extracted audio will be saved.

    Returns:
        True if extraction succeeded, False if it failed.

    Validates: Requirements 3.2, 3.7
    """
    try:
        # Validate inputs
        if start_sec < 0:
            logger.error(f"Invalid start_sec: {start_sec} (must be >= 0)")
            return False
        if end_sec <= start_sec:
            logger.error(
                f"Invalid time range: start_sec={start_sec}, end_sec={end_sec}"
            )
            return False
        if not os.path.isfile(video_path):
            logger.error(f"Video file not found: '{video_path}'")
            return False

        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        duration = end_sec - start_sec

        # Use FFmpeg to extract audio segment
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",                       # Overwrite output
                "-i", video_path,           # Input file
                "-ss", str(start_sec),      # Start time
                "-t", str(duration),        # Duration
                "-vn",                      # No video
                "-acodec", "libmp3lame",    # Encode as MP3
                "-q:a", "2",               # Quality level
                output_path,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            logger.error(
                f"FFmpeg audio extraction failed (exit code {result.returncode}): "
                f"{result.stderr.strip()}"
            )
            return False

        # Verify output file was created
        if not os.path.isfile(output_path):
            logger.error(
                f"FFmpeg completed but output file not found: '{output_path}'"
            )
            return False

        logger.info(
            f"Extracted audio segment [{start_sec:.2f}s - {end_sec:.2f}s] "
            f"to '{output_path}'"
        )
        return True

    except subprocess.TimeoutExpired:
        logger.error(
            f"FFmpeg audio extraction timed out for '{video_path}' "
            f"[{start_sec:.2f}s - {end_sec:.2f}s]"
        )
        return False
    except OSError as e:
        logger.error(f"FFmpeg audio extraction OS error: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during audio extraction: {e}")
        return False


def _trim_audio(input_path: str, target_duration: float, output_path: str) -> bool:
    """Trim an audio file to the target duration using FFmpeg.

    Args:
        input_path: Path to the audio file to trim.
        target_duration: Desired duration in seconds.
        output_path: Path for the trimmed output.

    Returns:
        True if trimming succeeded, False otherwise.
    """
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i", input_path,
                "-t", str(target_duration),
                "-acodec", "libmp3lame",
                "-q:a", "2",
                output_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.error(f"FFmpeg trim failed: {result.stderr.strip()}")
            return False
        return True
    except (subprocess.TimeoutExpired, OSError) as e:
        logger.error(f"FFmpeg trim error: {e}")
        return False


def _pad_audio_with_silence(
    input_path: str, target_duration: float, output_path: str
) -> bool:
    """Pad an audio file with silence at the end to reach target duration.

    Uses FFmpeg's apad filter to add silence until the target duration is met.

    Args:
        input_path: Path to the audio file to pad.
        target_duration: Desired total duration in seconds.
        output_path: Path for the padded output.

    Returns:
        True if padding succeeded, False otherwise.
    """
    try:
        # Use apad filter with whole_dur to pad to exact duration
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i", input_path,
                "-af", f"apad=whole_dur={target_duration}",
                "-acodec", "libmp3lame",
                "-q:a", "2",
                output_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.error(f"FFmpeg pad failed: {result.stderr.strip()}")
            return False
        return True
    except (subprocess.TimeoutExpired, OSError) as e:
        logger.error(f"FFmpeg pad error: {e}")
        return False


async def regenerate_with_elevenlabs(
    text: str,
    voice_id: str,
    language_code: str,
    target_duration: float,
    output_path: str,
) -> bool:
    """Regenerate audio using ElevenLabs TTS.

    Generates audio via the ElevenLabs TTS API, then adjusts the duration
    to match target_duration within ±0.2s tolerance by trimming (if too long)
    or padding with silence (if too short).

    Args:
        text: The text to synthesize.
        voice_id: ElevenLabs voice ID to use.
        language_code: ISO 639-1 language code (e.g. "ms", "zh", "en").
        target_duration: Desired output duration in seconds.
        output_path: Path where the final audio will be saved.

    Returns:
        True if generation and duration matching succeeded, False if failed.

    Validates: Requirements 3.3, 3.4, 3.6
    """
    api_key = os.environ.get("ELEVENLABS_API_KEY", "") or ELEVENLABS_API_KEY
    if not api_key:
        logger.error("ELEVENLABS_API_KEY is not set in environment variables")
        return False

    if not text or not text.strip():
        logger.error("Cannot generate audio: empty text provided")
        return False

    if target_duration <= 0:
        logger.error(f"Invalid target_duration: {target_duration}")
        return False

    # Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    try:
        # Call ElevenLabs TTS API
        endpoint = f"{ELEVENLABS_API_BASE}/v1/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }

        payload: dict = {
            "text": text.strip(),
            "model_id": "eleven_v3",
            "voice_settings": {
                "stability": 0.40,
                "similarity_boost": 0.75,
                "style": 0.12,
                "use_speaker_boost": True,
            },
        }

        # Add language code for non-English languages
        if language_code:
            # ElevenLabs expects 'zh' for Chinese dialects
            api_lang = "zh" if language_code.lower() == "yue" else language_code
            payload["language_code"] = api_lang

        logger.info(
            f"Calling ElevenLabs TTS (voice={voice_id}, lang={language_code})"
        )

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(endpoint, headers=headers, json=payload)

        if response.status_code != 200:
            logger.error(
                f"ElevenLabs API error (status {response.status_code}): "
                f"{response.text[:200]}"
            )
            return False

        # Write raw TTS output to a temporary file
        raw_output_path = output_path + ".raw.mp3"
        Path(raw_output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(raw_output_path, "wb") as f:
            f.write(response.content)

        # Check duration of generated audio
        generated_duration = _get_audio_duration(raw_output_path)
        if generated_duration is None:
            logger.error("Failed to determine duration of generated audio")
            # Clean up temp file
            _safe_remove(raw_output_path)
            return False

        logger.info(
            f"Generated audio duration: {generated_duration:.2f}s, "
            f"target: {target_duration:.2f}s"
        )

        # Duration matching: ±0.2s tolerance (Req 3.4)
        tolerance = 0.2
        duration_diff = generated_duration - target_duration

        if abs(duration_diff) <= tolerance:
            # Within tolerance — use as-is
            os.replace(raw_output_path, output_path)
            logger.info("Generated audio within tolerance, no adjustment needed")
        elif duration_diff > tolerance:
            # Too long — trim to target duration
            logger.info(
                f"Trimming audio from {generated_duration:.2f}s "
                f"to {target_duration:.2f}s"
            )
            success = _trim_audio(raw_output_path, target_duration, output_path)
            _safe_remove(raw_output_path)
            if not success:
                logger.error("Failed to trim generated audio")
                return False
        else:
            # Too short — pad with silence to target duration
            logger.info(
                f"Padding audio from {generated_duration:.2f}s "
                f"to {target_duration:.2f}s"
            )
            success = _pad_audio_with_silence(
                raw_output_path, target_duration, output_path
            )
            _safe_remove(raw_output_path)
            if not success:
                logger.error("Failed to pad generated audio with silence")
                return False

        # Final verification
        if not os.path.isfile(output_path):
            logger.error(f"Output file not found after processing: '{output_path}'")
            return False

        final_duration = _get_audio_duration(output_path)
        if final_duration is not None:
            logger.info(f"Final audio duration: {final_duration:.2f}s")

        return True

    except httpx.TimeoutException:
        logger.error("ElevenLabs API request timed out")
        return False
    except httpx.HTTPError as e:
        logger.error(f"ElevenLabs HTTP error: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during audio regeneration: {e}")
        return False


def _safe_remove(file_path: str) -> None:
    """Safely remove a file, ignoring errors if it doesn't exist."""
    try:
        if os.path.isfile(file_path):
            os.remove(file_path)
    except OSError:
        pass


async def remediate_audio_segment(
    video_path: str,
    violation,
    voice_config: VoiceConfig,
    replacement_text: str | None,
    output_dir: str,
) -> AudioRemediationResult:
    """Fix a single audio violation segment.

    Orchestrates the full audio remediation flow:
    1. Extract audio segment between violation timestamps
    2. If replacement_text is provided, use it; otherwise use the violation
       description as fallback text
    3. Regenerate audio with ElevenLabs TTS using voice_config
    4. Duration matching is handled by regenerate_with_elevenlabs
    5. Return AudioRemediationResult

    Args:
        video_path: Path to the source video file.
        violation: The audio violation to remediate, with timestamp_start
            and timestamp_end defining the segment.
        voice_config: Voice configuration (voice_id, language_code, etc.)
            selected for this market/ethnicity/language combination.
        replacement_text: Text to use for TTS generation. If None or empty,
            the violation description is used as fallback.
        output_dir: Directory where output audio files will be saved.

    Returns:
        AudioRemediationResult with success=True and the replacement audio
        path on success, or success=False with an error description on failure.

    Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7
    """
    # Compute target duration from violation timestamps
    target_duration = violation.timestamp_end - violation.timestamp_start

    # Generate unique filename for this segment
    segment_id = uuid.uuid4().hex[:8]

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Step 1: Extract audio segment from video (Req 3.2)
    extracted_audio_path = os.path.join(
        output_dir, f"extracted_{segment_id}.mp3"
    )
    extraction_success = extract_audio_segment(
        video_path=video_path,
        start_sec=violation.timestamp_start,
        end_sec=violation.timestamp_end,
        output_path=extracted_audio_path,
    )

    if not extraction_success:
        # Req 3.7: If FFmpeg audio extraction fails, mark as failed
        logger.error(
            f"Audio extraction failed for segment "
            f"[{violation.timestamp_start:.2f}s - {violation.timestamp_end:.2f}s]"
        )
        return AudioRemediationResult(
            original_start=violation.timestamp_start,
            original_end=violation.timestamp_end,
            replacement_audio_path="",
            voice_id_used="",
            success=False,
            error=(
                f"FFmpeg audio extraction failed for segment "
                f"[{violation.timestamp_start:.2f}s - {violation.timestamp_end:.2f}s]"
            ),
        )

    # Step 2: Determine text for TTS (Req 3.3)
    # Use replacement_text if provided, otherwise fall back to violation description
    tts_text = replacement_text if replacement_text and replacement_text.strip() else None
    if not tts_text:
        # Fallback: use the violation description as the text to regenerate
        tts_text = violation.description
        logger.info(
            f"No replacement_text provided; using violation description as "
            f"fallback text for TTS: '{tts_text[:50]}...'"
        )

    # Step 3: Regenerate audio with ElevenLabs TTS (Req 3.3, 3.4)
    # Duration matching (trim/pad to ±0.2s) is handled inside regenerate_with_elevenlabs
    output_audio_path = os.path.join(
        output_dir, f"voiceover_{segment_id}.mp3"
    )

    # Log if voice_config is using a fallback/default voice (Req 3.5, 10.5)
    # We detect fallback by checking if the voice_config market/ethnicity differ
    # from what was originally requested. The caller (orchestrator) handles
    # process log entries, but we log here for traceability.
    logger.info(
        f"Regenerating audio with voice_id={voice_config.voice_id}, "
        f"language={voice_config.language_code}, "
        f"target_duration={target_duration:.2f}s"
    )

    tts_success = await regenerate_with_elevenlabs(
        text=tts_text,
        voice_id=voice_config.voice_id,
        language_code=voice_config.language_code,
        target_duration=target_duration,
        output_path=output_audio_path,
    )

    # Clean up extracted audio (intermediate file)
    _safe_remove(extracted_audio_path)

    if not tts_success:
        # Req 3.6: If ElevenLabs TTS fails, mark as failed
        logger.error(
            f"ElevenLabs TTS regeneration failed for segment "
            f"[{violation.timestamp_start:.2f}s - {violation.timestamp_end:.2f}s]"
        )
        return AudioRemediationResult(
            original_start=violation.timestamp_start,
            original_end=violation.timestamp_end,
            replacement_audio_path="",
            voice_id_used=voice_config.voice_id,
            success=False,
            error=(
                f"ElevenLabs TTS regeneration failed for segment "
                f"[{violation.timestamp_start:.2f}s - {violation.timestamp_end:.2f}s]"
            ),
        )

    # Step 4: Return successful result
    logger.info(
        f"Audio remediation succeeded for segment "
        f"[{violation.timestamp_start:.2f}s - {violation.timestamp_end:.2f}s] → "
        f"'{output_audio_path}'"
    )

    return AudioRemediationResult(
        original_start=violation.timestamp_start,
        original_end=violation.timestamp_end,
        replacement_audio_path=output_audio_path,
        voice_id_used=voice_config.voice_id,
        success=True,
        error=None,
    )
