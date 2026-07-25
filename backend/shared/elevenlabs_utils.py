"""
elevenlabs_utils.py
───────────────────
Raw ElevenLabs API helpers for the generation agents.
Provides TTS (voiceover) and SFX (sound effects) generation, plus audio mixing.

Mirrors the working implementation in audio_ads/utils/ but adapted for the
generation pipeline (uses config.ELEVENLABS_API_KEY).
"""

import logging
from collections.abc import Sequence
from pathlib import Path

import requests

from config import ELEVENLABS_API_KEY

logger = logging.getLogger(__name__)

ELEVENLABS_API_BASE = "https://api.elevenlabs.io"

# Optional pydub for proper audio mixing
try:
    from pydub import AudioSegment
    HAS_PYDUB = True
except ImportError:
    HAS_PYDUB = False


def format_v3_delivery_text(text: str, delivery_tags: Sequence[str] | None = None) -> str:
    """Prefix clean ElevenLabs V3 performance tags without altering authored tags."""
    spoken_text = text.strip()
    if spoken_text.startswith("["):
        return spoken_text

    allowed = {
        "authoritative", "bright", "calm", "clear", "concerned", "confident",
        "energetic", "excited", "fast", "friendly", "playful", "softly",
        "urgent", "warmly",
    }
    tags: list[str] = []
    for raw_tag in delivery_tags or ():
        if not isinstance(raw_tag, str):
            continue
        tag = raw_tag.strip().strip("[]").lower()
        if tag in allowed and tag not in tags:
            tags.append(tag)
        if len(tags) == 3:
            break
    prefix = " ".join(f"[{tag}]" for tag in tags)
    return f"{prefix} {spoken_text}".strip()


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
    delivery_tags: Sequence[str] | None = None,
    speed: float = 1.0,
) -> bool:
    """Generate speech with ElevenLabs V3 direction and fallback to multilingual v2 only on V3 failure."""
    if not ELEVENLABS_API_KEY:
        logger.warning("[ElevenLabs] No API key configured")
        return False

    try:
        requested_tags = list(delivery_tags or [])
        if not requested_tags and emotion:
            requested_tags = [emotion]
        formatted_text = (
            format_v3_delivery_text(text, requested_tags)
            if model_id == "eleven_v3"
            else text
        )

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

        # V3 is always attempted first. The fallback deliberately uses raw spoken
        # text because V3 bracket directions are not a multilingual-v2 contract.
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
        logger.info(
            "[ElevenLabs] TTS saved (model=%s, delivery_tags=%s): %s",
            payload["model_id"],
            ",".join(requested_tags) or "default",
            out.name,
        )
        return True
    except Exception as exc:
        logger.error("[ElevenLabs] TTS failed: %s", exc)
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

def generate_music(prompt: str, output_path: str, duration: float) -> bool:
    """Generate background music (using SFX API as fallback)."""
    return generate_sfx(prompt, output_path, duration_seconds=min(duration, 22.0), prompt_influence=0.5)

def generate_music_from_video(video_paths: list, output_path: str, description: str, tags: str) -> bool:
    """Generate music synchronized to video (stub)."""
    # Just fail so it falls back to generate_music
    return False

def build_video_audio_program(
    output_path: str,
    target_duration: float,
    voiceover_path: str | None = None,
    music_path: str | None = None,
    sound_effects: list[dict] | None = None,
) -> bool:
    """Build the final audio program with VO, music, and SFX."""
    if not HAS_PYDUB:
        logger.warning("[ElevenLabs] pydub not available for audio program")
        return False

    try:
        target_ms = int(target_duration * 1000)
        base = AudioSegment.silent(duration=target_ms)

        if music_path and Path(music_path).exists():
            music = AudioSegment.from_file(music_path)
            if len(music) < target_ms and len(music) > 0:
                loops = (target_ms // len(music)) + 1
                music = music * loops
            music = music[:target_ms]
            music = music - 12  # Duck music
            base = base.overlay(music)

        if sound_effects:
            import math
            for sfx_info in sound_effects:
                p = sfx_info.get("path")
                if p and Path(p).exists():
                    sfx = AudioSegment.from_file(p)
                    vol = sfx_info.get("volume", 1.0)
                    if vol != 1.0 and vol > 0:
                        db_change = 20 * math.log10(vol)
                        sfx = sfx + db_change
                    start_ms = int(sfx_info.get("start_seconds", 0) * 1000)
                    base = base.overlay(sfx, position=start_ms)

        if voiceover_path and Path(voiceover_path).exists():
            vo = AudioSegment.from_file(voiceover_path)
            base = base.overlay(vo)

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        base.export(output_path, format="mp3")
        logger.info("[ElevenLabs] Audio program built: %s", out.name)
        return True
    except Exception as e:
        logger.error("[ElevenLabs] build_video_audio_program failed: %s", e)
        return False
