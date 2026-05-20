"""
ElevenLabs Client
==================
Raw API calls for Text-to-Speech (TTS) and Sound Effects (SFX).
"""

import sys
import requests
from pathlib import Path

ELEVENLABS_API_BASE = "https://api.elevenlabs.io"


def generate_tts(
    text: str,
    output_path: str,
    api_key: str,
    voice_id: str,
    model_id: str = "eleven_v3",
    stability: float = 0.40,
    similarity_boost: float = 0.75,
    style: float = 0.12,
    language_code: str | None = None,
) -> bool:
    """
    Generate narrator audio using ElevenLabs TTS.

    Args:
        text: Narration text.
        output_path: Where to save the generated MP3.
        api_key: ElevenLabs API key.
        voice_id: ElevenLabs voice ID.
        model_id: Model to use (default: eleven_v3).
        stability: Voice stability 0-1.
        similarity_boost: Voice similarity 0-1.
        style: Voice style 0-1.
        language_code: ISO 639-1 code to enforce language.
                       None = auto-detect from text.

    Returns:
        True if successful, False otherwise.
    """
    try:
        headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json",
        }

        payload = {
            "text": text,
            "model_id": model_id,
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity_boost,
                "style": style,
                "use_speaker_boost": True,
            },
        }

        if language_code:
            # ElevenLabs expects 'zh' for Chinese dialects; auto-detects Cantonese from text
            api_lang = "zh" if language_code.lower() == "yue" else language_code
            payload["language_code"] = api_lang

        endpoint = f"{ELEVENLABS_API_BASE}/v1/text-to-speech/{voice_id}"
        print(f"  Calling ElevenLabs TTS...")
        print(f"  Text: {text[:80]}{'...' if len(text) > 80 else ''}")
        lang_info = f", Lang={language_code}" if language_code else ""
        print(f"  Settings: Stability={stability}, Similarity={similarity_boost}, Style={style}{lang_info}")

        response = requests.post(endpoint, headers=headers, json=payload)

        if response.status_code != 200:
            print(f"  TTS API Error: {response.status_code}", file=sys.stderr)
            print(f"  Response: {response.text[:200]}", file=sys.stderr)
            return False

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "wb") as f:
            f.write(response.content)

        print(f"  Audio saved: {out}")
        return True

    except Exception as e:
        print(f"  Error generating TTS: {e}", file=sys.stderr)
        return False


def generate_sfx(
    prompt: str,
    output_path: str,
    api_key: str,
    duration_seconds: float = 5.0,
    prompt_influence: float = 0.3,
) -> bool:
    """
    Generate a sound effect using ElevenLabs Sound Generation API.

    Args:
        prompt: Text description of the sound effect.
        output_path: Where to save the generated MP3.
        api_key: ElevenLabs API key.
        duration_seconds: Length in seconds (0.5-30).
        prompt_influence: How closely to follow the prompt (0-1).

    Returns:
        True if successful, False otherwise.
    """
    try:
        headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json",
        }

        payload = {
            "text": prompt,
            "duration_seconds": duration_seconds,
            "prompt_influence": prompt_influence,
        }

        endpoint = f"{ELEVENLABS_API_BASE}/v1/sound-generation"
        print(f"  Generating SFX: {prompt[:60]}{'...' if len(prompt) > 60 else ''}")
        print(f"  Duration: {duration_seconds}s, Prompt influence: {prompt_influence}")

        response = requests.post(endpoint, headers=headers, json=payload)

        if response.status_code != 200:
            print(f"  SFX API Error: {response.status_code}", file=sys.stderr)
            print(f"  Response: {response.text[:200]}", file=sys.stderr)
            return False

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "wb") as f:
            f.write(response.content)

        print(f"  SFX saved: {out}")
        return True

    except Exception as e:
        print(f"  Error generating SFX: {e}", file=sys.stderr)
        return False
