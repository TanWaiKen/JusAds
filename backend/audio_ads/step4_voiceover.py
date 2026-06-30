"""
Step 4: Voice Over Generation
===============================
Generates voiceover audio for each scene using ElevenLabs TTS.
"""

import os
from pathlib import Path

from utils.elevenlabs_client import generate_tts


def generate_voiceover_for_script(
    script: list[dict],
    voice_id: str,
    output_dir: str = "output/vo",
    api_key: str | None = None,
    language_code: str = "ms",
) -> list[dict]:
    """
    Generate voiceover audio for each scene in the ad script.

    Args:
        script: List of scene dicts from Step 2 (each has 'script').
        voice_id: ElevenLabs voice ID.
        output_dir: Directory to save VO files.
        api_key: ElevenLabs API key (falls back to env var).
        language_code: ISO 639-1 code for TTS language enforcement.

    Returns:
        List of dicts: [{"scene": 1, "path": "output/vo/vo_scene_1.mp3", "ok": True}, ...]
    """
    key = api_key or os.getenv("ELEVENLABS_API_KEY")
    if not key:
        raise ValueError("ELEVENLABS_API_KEY is required")

    results = []

    for scene in script:
        scene_num = scene.get("number", 0)
        text = scene.get("script", "")

        if not text:
            print(f"  Scene {scene_num}: No script text, skipping VO.")
            results.append({"scene": scene_num, "path": None, "ok": False})
            continue

        out_path = str(Path(output_dir) / f"vo_scene_{scene_num}.mp3")

        print(f"\n  [{scene_num}/4] Generating VO...")
        ok = generate_tts(
            text=text,
            output_path=out_path,
            api_key=key,
            voice_id=voice_id,
            language_code=language_code,
        )

        results.append({"scene": scene_num, "path": out_path if ok else None, "ok": ok})

    return results
