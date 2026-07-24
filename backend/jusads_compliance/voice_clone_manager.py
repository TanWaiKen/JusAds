"""
voice_clone_manager.py
──────────────────────
Manages persistent brand voice clones via ElevenLabs.

Key capabilities:
  - Clone a brand voice from sample audio (stored permanently)
  - Retrieve existing clone by project/brand ID
  - Dub specific segments using the cloned voice
  - Full re-read of script with cloned voice
  - Cleanup: delete voice when project is deleted

Voice clones are stored in Supabase (brand_voices table) and persist
across all future ads for that brand — no re-cloning needed.
"""

import logging
import os
import tempfile
import urllib.request
from typing import Optional

from shared.clients import elevenlabs, supabase
from shared.config import get_voice, DEFAULT_VOICE

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Voice Clone CRUD
# -----------------------------------------------------------------------------


async def clone_brand_voice(
    project_id: str,
    voice_name: str,
    sample_audio_url: str,
    description: str = "",
) -> Optional[dict]:
    """Clone a voice from sample audio and persist the voice_id.

    Args:
        project_id: The project this voice belongs to.
        voice_name: Human-readable name for the voice (e.g., "Brand VO - Malay Female").
        sample_audio_url: S3 URL of the audio sample to clone from.
        description: Optional description of the voice characteristics.

    Returns:
        Dict with voice_id, name, and metadata on success. None on failure.
    """
    if not elevenlabs:
        logger.error("[VoiceCloneManager] ElevenLabs client unavailable")
        return None

    try:
        # Download sample audio to temp file
        tmp_sample = os.path.join(tempfile.gettempdir(), f"voice_sample_{project_id}.mp3")
        urllib.request.urlretrieve(sample_audio_url, tmp_sample)

        # Clone via ElevenLabs API
        with open(tmp_sample, "rb") as audio_file:
            voice = elevenlabs.clone(
                name=voice_name,
                description=description or f"Brand voice for project {project_id}",
                files=[audio_file],
            )

        voice_id = voice.voice_id
        logger.info("[VoiceCloneManager] Cloned voice: %s (id=%s)", voice_name, voice_id)

        # Persist to Supabase
        record = {
            "project_id": project_id,
            "voice_id": voice_id,
            "voice_name": voice_name,
            "description": description,
            "sample_url": sample_audio_url,
            "status": "active",
        }

        if supabase:
            try:
                supabase.table("brand_voices").upsert(
                    record, on_conflict="project_id"
                ).execute()
                logger.info("[VoiceCloneManager] Persisted voice clone to DB")
            except Exception as db_err:
                logger.warning("[VoiceCloneManager] DB persist failed (voice still usable): %s", db_err)

        # Cleanup temp file
        try:
            os.remove(tmp_sample)
        except OSError:
            pass

        return {
            "voice_id": voice_id,
            "name": voice_name,
            "project_id": project_id,
            "status": "active",
        }

    except Exception as e:
        logger.error("[VoiceCloneManager] Voice cloning failed: %s", e)
        return None


def get_brand_voice(project_id: str) -> Optional[dict]:
    """Retrieve the stored brand voice for a project.

    Priority: custom clone for the project > global catalog voice.

    Returns:
        Dict with voice_id, name, etc. or None if no clone exists.
    """
    if not supabase:
        logger.warning("[VoiceCloneManager] Supabase unavailable — cannot retrieve voice")
        return None

    try:
        # First try: project-specific custom clone
        response = (
            supabase.table("brand_voices")
            .select("*")
            .eq("project_id", project_id)
            .eq("status", "active")
            .eq("is_custom_clone", True)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if rows:
            logger.info("[VoiceCloneManager] Found custom clone for project %s", project_id)
            return rows[0]
        return None

    except Exception as e:
        logger.error("[VoiceCloneManager] Failed to retrieve voice: %s", e)
        return None


def get_global_voices(market: str = "", ethnicity: str = "", gender: str = "") -> list[dict]:
    """Retrieve available global catalog voices, optionally filtered.

    These are pre-loaded voices available to all users (project_id IS NULL).

    Args:
        market: Optional filter by market.
        ethnicity: Optional filter by ethnicity.
        gender: Optional filter by gender.

    Returns:
        List of voice dicts from the global catalog.
    """
    if not supabase:
        return []

    try:
        query = (
            supabase.table("brand_voices")
            .select("*")
            .is_("project_id", "null")
            .eq("status", "active")
        )

        if market:
            query = query.eq("market", market.lower())
        if ethnicity:
            query = query.eq("ethnicity", ethnicity.lower())
        if gender:
            query = query.eq("gender", gender.lower())

        response = query.execute()
        return response.data or []

    except Exception as e:
        logger.error("[VoiceCloneManager] Failed to list global voices: %s", e)
        return []


def delete_brand_voice(project_id: str) -> bool:
    """Delete the brand voice clone (both ElevenLabs + DB record).

    Called when a project is deleted to clean up resources.
    """
    voice_record = get_brand_voice(project_id)
    if not voice_record:
        return True  # Nothing to delete

    voice_id = voice_record.get("voice_id")

    # Delete from ElevenLabs
    if elevenlabs and voice_id:
        try:
            elevenlabs.voices.delete(voice_id=voice_id)
            logger.info("[VoiceCloneManager] Deleted voice %s from ElevenLabs", voice_id)
        except Exception as e:
            logger.warning("[VoiceCloneManager] ElevenLabs delete failed: %s", e)

    # Mark as deleted in DB
    if supabase:
        try:
            supabase.table("brand_voices").update(
                {"status": "deleted"}
            ).eq("project_id", project_id).execute()
        except Exception as e:
            logger.warning("[VoiceCloneManager] DB status update failed: %s", e)

    return True


# -----------------------------------------------------------------------------
# Audio Dubbing / TTS with cloned or configured voice
# -----------------------------------------------------------------------------


def isolate_vocals_from_audio(input_audio_path: str, output_audio_path: str) -> bool:
    """Isolate spoken vocal track from input audio/video file using ffmpeg filters.

    Applies bandpass filtering (80Hz-8000Hz speech range), noise reduction, and
    loudness normalization to isolate clear vocals for voice cloning.
    """
    import subprocess
    from pathlib import Path

    try:
        out_p = Path(output_audio_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            "ffmpeg",
            "-y",
            "-i", input_audio_path,
            "-af", "highpass=f=80,lowpass=f=8000,afftdn=nr=12,loudnorm",
            "-ar", "44100",
            "-ac", "1",
            output_audio_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0 and os.path.exists(output_audio_path):
            logger.info("[VoiceCloneManager] Vocals isolated successfully: %s", output_audio_path)
            return True
        else:
            logger.warning("[VoiceCloneManager] ffmpeg vocal isolation warning: %s. Using original audio.", result.stderr[:200])
            import shutil
            shutil.copy(input_audio_path, output_audio_path)
            return True
    except Exception as e:
        logger.error("[VoiceCloneManager] Vocal isolation failed: %s", e)
        return False


def dub_segment(
    text: str,
    voice_id: Optional[str] = None,
    project_id: Optional[str] = None,
    market: str = "malaysia",
    ethnicity: str = "malay",
    gender: str = "female",
    emotion: Optional[str] = None,
    speed: float = 1.0,
) -> Optional[str]:
    """Generate TTS audio for a specific text segment using ElevenLabs v3 with emotion & pitch controls.

    Voice priority:
      1. Explicit voice_id (if provided)
      2. Project's cloned brand voice (if exists)
      3. VOICE_CONFIG lookup by (market, ethnicity, gender)
      4. DEFAULT_VOICE fallback
    """
    from shared.elevenlabs_utils import generate_tts

    resolved_voice_id = _resolve_voice_id(voice_id, project_id, market, ethnicity, gender)
    output_path = os.path.join(
        tempfile.gettempdir(),
        f"dub_segment_{hash(text) % 100000}.mp3",
    )

    ok = generate_tts(
        text=text,
        output_path=output_path,
        voice_id=resolved_voice_id,
        model_id="eleven_v3",
        emotion=emotion,
        speed=speed,
    )
    if ok:
        logger.info("[VoiceCloneManager] Dubbed segment (%d chars, emotion=%s) → %s", len(text), emotion or "default", output_path)
        return output_path
    return None


def full_reread(
    script: str,
    voice_id: Optional[str] = None,
    project_id: Optional[str] = None,
    market: str = "malaysia",
    ethnicity: str = "malay",
    gender: str = "female",
    emotion: Optional[str] = None,
    speed: float = 1.0,
) -> Optional[str]:
    """Generate full TTS audio for an entire script (voice clone re-read) via ElevenLabs v3 with emotion control."""
    from shared.elevenlabs_utils import generate_tts

    resolved_voice_id = _resolve_voice_id(voice_id, project_id, market, ethnicity, gender)
    output_path = os.path.join(
        tempfile.gettempdir(),
        f"full_reread_{hash(script) % 100000}.mp3",
    )

    ok = generate_tts(
        text=script,
        output_path=output_path,
        voice_id=resolved_voice_id,
        model_id="eleven_v3",
        emotion=emotion,
        speed=speed,
    )
    if ok:
        logger.info("[VoiceCloneManager] Full re-read (%d chars, emotion=%s) → %s", len(script), emotion or "default", output_path)
        return output_path
    return None


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _resolve_voice_id(
    explicit_voice_id: Optional[str],
    project_id: Optional[str],
    market: str,
    ethnicity: str,
    gender: str,
) -> str:
    """Resolve the best voice_id to use with priority chain.

    Priority:
      1. Explicit voice_id parameter
      2. Project's custom brand voice clone
      3. Global catalog voice (by market/ethnicity/gender)
      4. DEFAULT_VOICE fallback
    """
    # 1. Explicit
    if explicit_voice_id:
        return explicit_voice_id

    # 2. Brand voice clone (custom)
    if project_id:
        brand_voice = get_brand_voice(project_id)
        if brand_voice and brand_voice.get("voice_id"):
            logger.info("[VoiceCloneManager] Using custom clone for project %s", project_id)
            return brand_voice["voice_id"]

    # 3. Global catalog lookup
    global_voices = get_global_voices(market=market, ethnicity=ethnicity, gender=gender)
    if global_voices:
        logger.info("[VoiceCloneManager] Using global catalog voice: %s", global_voices[0].get("voice_name"))
        return global_voices[0]["voice_id"]

    # 4. Hardcoded fallback
    voice_entry = get_voice(market, ethnicity, gender)
    return voice_entry["voice_id"]
