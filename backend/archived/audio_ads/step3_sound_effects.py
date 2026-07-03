"""
Step 3: Sound Effects Generation
==================================
Generates a sound effect for each scene using ElevenLabs SFX API.
"""

import os
from pathlib import Path

from utils.elevenlabs_client import generate_sfx


def generate_sfx_for_script(
    script: list[dict],
    output_dir: str = "output/sfx",
    api_key: str | None = None,
) -> list[dict]:
    """
    Generate sound effects for each scene in the ad script.

    Args:
        script: List of scene dicts from Step 2 (each has 'sfxPrompt', 'duration').
        output_dir: Directory to save SFX files.
        api_key: ElevenLabs API key (falls back to env var).

    Returns:
        List of dicts: [{"scene": 1, "path": "output/sfx/sfx_scene_1.mp3", "ok": True}, ...]
    """
    key = api_key or os.getenv("ELEVENLABS_API_KEY")
    if not key:
        raise ValueError("ELEVENLABS_API_KEY is required")

    results = []

    for scene in script:
        scene_num = scene.get("number", 0)
        sfx_prompt = scene.get("sfxPrompt", "")
        duration = scene.get("duration", 5)

        if not sfx_prompt:
            print(f"  Scene {scene_num}: No sfxPrompt, skipping SFX.")
            results.append({"scene": scene_num, "path": None, "ok": False})
            continue

        out_path = str(Path(output_dir) / f"sfx_scene_{scene_num}.mp3")

        ok = generate_sfx(
            prompt=sfx_prompt,
            output_path=out_path,
            api_key=key,
            duration_seconds=float(duration),
        )

        results.append({"scene": scene_num, "path": out_path if ok else None, "ok": ok})

    return results
