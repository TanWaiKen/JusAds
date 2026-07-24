"""
elevenlabs_utils.py
───────────────────
Raw ElevenLabs API helpers for the generation agents.
Provides TTS (voiceover) and SFX (sound effects) generation, plus audio mixing.

Mirrors the working implementation in audio_ads/utils/ but adapted for the
generation pipeline (uses config.ELEVENLABS_API_KEY).
"""

import logging
import requests
from pathlib import Path

from config import ELEVENLABS_API_KEY

logger = logging.getLogger(__name__)

ELEVENLABS_API_BASE = "https://api.elevenlabs.io"

# Optional pydub for proper audio mixing
try:
    from pydub import AudioSegment
    HAS_PYDUB = True
except ImportError:
    HAS_PYDUB = False


def generate_tts(
    text: str,
    output_path: str,
    voice_id: str,
    model_id: str = "eleven_v3",
    stability: float = 0.40,
    similarity_boost: float = 0.75,
    style: float = 0.12,
    language_code: str | None = None,
    emotion: str | None = None,
    speed: float = 1.0,
) -> bool:
    """Generate voiceover audio via ElevenLabs TTS with v3 emotion & pitch control. Returns True on success."""
    if not ELEVENLABS_API_KEY:
        logger.warning("[ElevenLabs] No API key configured")
        return False

    try:
        formatted_text = text
        if emotion and model_id == "eleven_v3":
            emotion_clean = emotion.strip().lower()
            if not text.startswith("["):
                formatted_text = f"[{emotion_clean}] {text}"

        headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}
        voice_settings = {
            "stability": stability,
            "similarity_boost": similarity_boost,
            "style": style,
            "use_speaker_boost": True,
        }
        if speed and speed != 1.0:
            voice_settings["speed"] = max(0.7, min(1.2, speed))

        payload = {
            "text": formatted_text,
            "model_id": model_id,
            "voice_settings": voice_settings,
        }
        if language_code:
            payload["language_code"] = language_code

        endpoint = f"{ELEVENLABS_API_BASE}/v1/text-to-speech/{voice_id}"
        response = requests.post(endpoint, headers=headers, json=payload, timeout=60)

        # eleven_v3 is the preferred expressive model.  Existing workspaces can
        # still have a key/voice combination without access to it, so preserve a
        # reliable multilingual fallback instead of silently emitting no audio.
        if response.status_code != 200 and model_id == "eleven_v3":
            payload["model_id"] = "eleven_multilingual_v2"
            payload["text"] = text
            response = requests.post(endpoint, headers=headers, json=payload, timeout=60)

        if response.status_code != 200:
            logger.warning("[ElevenLabs] TTS error %d: %s", response.status_code, response.text[:200])
            return False

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(response.content)
        logger.info("[ElevenLabs] TTS saved (model=%s, emotion=%s): %s", payload["model_id"], emotion or "default", out.name)
        return True
    except Exception as e:
        logger.error("[ElevenLabs] TTS failed: %s", e)
        return False


def generate_sfx(
    prompt: str,
    output_path: str,
    duration_seconds: float = 5.0,
    prompt_influence: float = 0.3,
) -> bool:
    """Generate a sound effect via ElevenLabs Sound Generation API. Returns True on success."""
    if not ELEVENLABS_API_KEY:
        logger.warning("[ElevenLabs] No API key configured")
        return False

    try:
        headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}
        payload = {
            "text": prompt,
            "duration_seconds": max(0.5, min(22.0, duration_seconds)),
            "prompt_influence": prompt_influence,
        }
        endpoint = f"{ELEVENLABS_API_BASE}/v1/sound-generation"
        response = requests.post(endpoint, headers=headers, json=payload, timeout=60)

        if response.status_code != 200:
            logger.warning("[ElevenLabs] SFX error %d: %s", response.status_code, response.text[:200])
            return False

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(response.content)
        logger.info("[ElevenLabs] SFX saved: %s", out.name)
        return True
    except Exception as e:
        logger.error("[ElevenLabs] SFX failed: %s", e)
        return False


def mix_vo_and_sfx(
    vo_path: str,
    sfx_path: str | None,
    output_path: str,
    sfx_volume_reduction_db: int = -10,
) -> bool:
    """Overlay an SFX bed (lowered volume) under a voiceover track.

    Falls back to copying the VO file if pydub is unavailable or SFX is missing.
    Returns True on success.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if not HAS_PYDUB or not sfx_path or not Path(sfx_path).exists():
        # No mixing possible — just use the VO track
        try:
            out.write_bytes(Path(vo_path).read_bytes())
            return True
        except Exception as e:
            logger.error("[ElevenLabs] VO copy failed: %s", e)
            return False

    try:
        vo_seg = AudioSegment.from_mp3(vo_path)
        sfx_seg = AudioSegment.from_mp3(sfx_path) + sfx_volume_reduction_db

        # Match SFX length to VO length (loop or trim)
        if len(sfx_seg) > len(vo_seg):
            sfx_seg = sfx_seg[: len(vo_seg)]
        elif len(sfx_seg) < len(vo_seg) and len(sfx_seg) > 0:
            loops = (len(vo_seg) // len(sfx_seg)) + 1
            sfx_seg = (sfx_seg * loops)[: len(vo_seg)]

        mixed = vo_seg.overlay(sfx_seg)
        mixed.export(output_path, format="mp3")
        logger.info("[ElevenLabs] Mixed VO + SFX: %s", out.name)
        return True
    except Exception as e:
        logger.warning("[ElevenLabs] Mix failed: %s. Using VO only.", e)
        try:
            out.write_bytes(Path(vo_path).read_bytes())
            return True
        except Exception:
            return False
