"""
ElevenLabs Utilities
=====================
Voice map, voice resolution, listing, and audio merging helpers.
"""

import os
import sys
from pathlib import Path

# Try to import pydub for audio merging / mixing
try:
    from pydub import AudioSegment
    HAS_PYDUB = True
except ImportError:
    HAS_PYDUB = False

# ---------------------------------------------------------------------------
# Voice map: (COUNTRY, LANGUAGE, GENDER) -> .env variable name
# ---------------------------------------------------------------------------
VOICE_MAP = {
    # -- Malaysia --
    ("my", "ms",     "male"):    "ELEVENLABS_VOICE_MY_MS_MALE",
    ("my", "ms",     "female"):  "ELEVENLABS_VOICE_MY_MS_FEMALE",
    ("my", "zh",     "male"):    "ELEVENLABS_VOICE_MY_ZH_MALE",
    ("my", "zh",     "female"):  "ELEVENLABS_VOICE_MY_ZH_FEMALE",
    ("my", "yue",    "male"):    "ELEVENLABS_VOICE_MY_YUE",
    ("my", "yue",    "female"):  "ELEVENLABS_VOICE_MY_YUE",
    ("my", "en-chi", "male"):    "ELEVENLABS_VOICE_MY_EN_CHI_MALE",
    ("my", "en-chi", "female"):  "ELEVENLABS_VOICE_MY_EN_CHI_FEMALE",
    ("my", "en-ind", "male"):    "ELEVENLABS_VOICE_MY_EN_IND_MALE",
    ("my", "en-ind", "female"):  "ELEVENLABS_VOICE_MY_EN_IND_FEMALE",
    # -- Singapore --
    ("sg", "en",     "male"):    "ELEVENLABS_VOICE_SG_EN_MALE",
    ("sg", "en",     "female"):  "ELEVENLABS_VOICE_SG_EN_FEMALE",
    ("sg", "zh",     "male"):    "ELEVENLABS_VOICE_SG_ZH_MALE",
    ("sg", "zh",     "female"):  "ELEVENLABS_VOICE_SG_ZH_FEMALE",
}

VOICE_LABELS = {
    ("my", "ms",     "male"):    "MY | Bahasa Malaysia | Male",
    ("my", "ms",     "female"):  "MY | Bahasa Malaysia | Female",
    ("my", "zh",     "male"):    "MY | Mandarin Chinese | Male",
    ("my", "zh",     "female"):  "MY | Mandarin Chinese | Female",
    ("my", "yue",    "male"):    "MY | Cantonese (prompt-engineered) | Male",
    ("my", "yue",    "female"):  "MY | Cantonese (prompt-engineered) | Female",
    ("my", "en-chi", "male"):    "MY | English (Chinese accent) | Male",
    ("my", "en-chi", "female"):  "MY | English (Chinese accent) | Female",
    ("my", "en-ind", "male"):    "MY | English (Indian accent) | Male",
    ("my", "en-ind", "female"):  "MY | English (Indian accent) | Female",
    ("sg", "en",     "male"):    "SG | English (Singaporean) | Male",
    ("sg", "en",     "female"):  "SG | English (Singaporean) | Female",
    ("sg", "zh",     "male"):    "SG | Mandarin Chinese | Male",
    ("sg", "zh",     "female"):  "SG | Mandarin Chinese | Female",
}


def resolve_voice_id(country: str, language: str, gender: str) -> str | None:
    """
    Look up the correct voice ID from VOICE_MAP + .env.

    Returns:
        voice_id string if found and set, None otherwise.
    """
    key = (country.lower(), language.lower(), gender.lower())
    env_var = VOICE_MAP.get(key)
    if env_var is None:
        return None
    return os.getenv(env_var) or None


def list_voices():
    """Print all defined voice slots with their current .env values."""
    print()
    print("=" * 80)
    print("  JusAds -- ElevenLabs Voice Slots")
    print("=" * 80)
    print(f"  {'Status':<8} {'Slot':<38} {'Env Var':<33} Voice ID")
    print(f"  {'-'*8} {'-'*38} {'-'*33} {'-'*30}")

    for key, env_var in VOICE_MAP.items():
        if key[2] == "female" and key[1] == "yue":
            continue  # skip duplicate yue row
        label = VOICE_LABELS.get(key, str(key))
        voice_id = os.getenv(env_var, "(not set)")
        status = "[OK]" if voice_id != "(not set)" else "[--]"
        print(f"  {status:<8} {label:<38} {env_var:<33} {voice_id}")

    print("=" * 80)
    print()


def merge_audio_files(files: list[str], output_path: str) -> bool:
    """
    Merge multiple MP3 files into one.
    Uses pydub if available (proper re-encoding), otherwise binary concat.
    """
    if HAS_PYDUB:
        try:
            combined = AudioSegment.empty()
            for f in files:
                combined += AudioSegment.from_mp3(f)
            combined.export(output_path, format="mp3")
            print(f"  Audio merged (pydub): {output_path}")
            return True
        except Exception as e:
            print(f"  pydub merge failed: {e} -- falling back to binary concat")

    # Fallback: binary concatenation
    try:
        with open(output_path, "wb") as outfile:
            for f in files:
                with open(f, "rb") as infile:
                    outfile.write(infile.read())
        print(f"  Audio merged (binary): {output_path}")
        return True
    except Exception as e:
        print(f"  Merge failed: {e}", file=sys.stderr)
        return False


def mix_vo_and_sfx(
    vo_results: list[dict],
    sfx_results: list[dict],
    output_path: str = "output/final_ad.mp3",
    sfx_volume_reduction_db: int = -8,
) -> bool:
    """
    Mix voiceover and sound effects into a final ad audio file.

    For each scene, overlays the SFX (lowered volume) under the VO.
    Then concatenates all scenes sequentially.

    Falls back to VO-only merge if pydub is not available.
    """
    sfx_by_scene = {r["scene"]: r["path"] for r in sfx_results if r["ok"]}
    vo_files = [r for r in vo_results if r["ok"]]

    if not vo_files:
        print("ERROR: No voiceover segments available.", file=sys.stderr)
        return False

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    if HAS_PYDUB:
        try:
            combined = AudioSegment.empty()

            for vo_r in vo_files:
                scene_num = vo_r["scene"]
                vo_seg = AudioSegment.from_mp3(vo_r["path"])

                sfx_path = sfx_by_scene.get(scene_num)
                if sfx_path and Path(sfx_path).exists():
                    sfx_seg = AudioSegment.from_mp3(sfx_path)
                    sfx_seg = sfx_seg + sfx_volume_reduction_db
                    # Match SFX length to VO length
                    if len(sfx_seg) > len(vo_seg):
                        sfx_seg = sfx_seg[:len(vo_seg)]
                    elif len(sfx_seg) < len(vo_seg):
                        loops_needed = (len(vo_seg) // len(sfx_seg)) + 1
                        sfx_seg = (sfx_seg * loops_needed)[:len(vo_seg)]
                    mixed = vo_seg.overlay(sfx_seg)
                    combined += mixed
                    print(f"  Scene {scene_num}: VO + SFX mixed")
                else:
                    combined += vo_seg
                    print(f"  Scene {scene_num}: VO only (no SFX)")

            combined.export(output_path, format="mp3")
            print(f"\n  Final ad saved (pydub mix): {output_path}")
            return True

        except Exception as e:
            print(f"  pydub mix failed: {e} — falling back to VO-only merge")

    # Fallback: concatenate VO files only
    print("  WARNING: pydub not available, merging VO only (no SFX overlay)")
    vo_paths = [r["path"] for r in vo_files]
    return merge_audio_files(vo_paths, output_path)
