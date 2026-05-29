"""
Voice Ads Creation Pipeline — main.py
=======================================
Full 4-step pipeline to generate a voice ad from a rough product idea:

  Step 1: Product Idea Enhancement   (Gemini)
  Step 2: Script Generation           (Gemini → 4-scene JSON)
  Step 3: Sound Effects               (ElevenLabs SFX API)
  Step 4: Voice Over + Final Mix      (ElevenLabs TTS + pydub overlay)

Usage:
    python main.py \
        --idea "FitPulse AI smart wristband" \
        --mood "energetic" \
        --audience "young professionals" \
        --language ms \
        --gender male
"""

import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env from backend/ directory
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from step1_product_idea import enhance_product_idea
from step2_script_generation import generate_ad_script
from step3_sound_effects import generate_sfx_for_script
from step4_voiceover import generate_voiceover_for_script
from utils.elevenlabs_utils import resolve_voice_id, mix_vo_and_sfx


def run_pipeline(idea, mood, audience, language, gender, country, voice_override, output):
    """
    Full pipeline: idea → script → SFX → VO → mix.

    Returns True on success.
    """
    # Resolve voice
    if voice_override:
        voice_id = voice_override
    else:
        voice_id = resolve_voice_id(country, language, gender)
    if not voice_id:
        print(
            f"ERROR: No voice for ({country}, {language}, {gender}).\n"
            "  Check .env or pass --voice.",
            file=sys.stderr,
        )
        return False

    # ---- Step 1 ----
    print(f"\n{'='*60}")
    print("  STEP 1: Enhancing Product Idea")
    print(f"{'='*60}")
    try:
        refined_concept = enhance_product_idea(idea, mood, audience)
    except Exception as e:
        print(f"Step 1 failed: {e}", file=sys.stderr)
        return False
    print(f"\n  Refined Concept:\n  {refined_concept}\n")

    # ---- Step 2 ----
    print(f"{'='*60}")
    print("  STEP 2: Generating 4-Scene Ad Script")
    print(f"{'='*60}")
    try:
        script = generate_ad_script(refined_concept, mood, audience)
    except Exception as e:
        print(f"Step 2 failed: {e}", file=sys.stderr)
        return False

    print("\n  --- Script Preview ---")
    for scene in script:
        n = scene.get("number", "?")
        s = scene.get("script", "")
        sfx = scene.get("sfxPrompt", "")
        print(f"  Scene {n}: {s[:80]}{'...' if len(s) > 80 else ''}")
        print(f"       SFX: {sfx[:60]}{'...' if len(sfx) > 60 else ''}")
    print("  --- End Preview ---\n")

    # ---- Step 3 ----
    print(f"{'='*60}")
    print(f"  STEP 3: Generating Sound Effects ({len(script)} scenes)")
    print(f"{'='*60}")
    sfx_results = generate_sfx_for_script(script)

    sfx_ok = sum(1 for r in sfx_results if r["ok"])
    print(f"\n  SFX: {sfx_ok}/{len(script)} generated successfully")

    # ---- Step 4 ----
    print(f"\n{'='*60}")
    print(f"  STEP 4: Generating Voice Over ({len(script)} scenes)")
    print(f"{'='*60}")
    vo_results = generate_voiceover_for_script(
        script,
        voice_id=voice_id,
        language_code=language,
    )

    vo_ok = sum(1 for r in vo_results if r["ok"])
    print(f"\n  VO: {vo_ok}/{len(script)} generated successfully")

    if vo_ok == 0:
        print("ERROR: No voiceover segments generated.", file=sys.stderr)
        return False

    # ---- Final Mix ----
    print(f"\n{'='*60}")
    print("  FINAL: Mixing VO + SFX")
    print(f"{'='*60}")
    success = mix_vo_and_sfx(vo_results, sfx_results, output_path=output)

    if success:
        print(f"\n{'='*60}")
        print(f"  DONE!")
        print(f"  Output: {output}")
        print(f"{'='*60}\n")

    return success


def main():
    parser = argparse.ArgumentParser(
        description="Voice Ads Creation Pipeline (4 steps: Idea → Script → SFX → VO)"
    )
    parser.add_argument("--idea", required=True, help="Rough product idea")
    parser.add_argument("--mood", required=True, help="Target mood (e.g. energetic, calm, professional)")
    parser.add_argument("--audience", required=True, help="Target audience (e.g. young professionals)")
    parser.add_argument("--language", default="ms", help="Language code (default: ms)")
    parser.add_argument("--gender", default="male", choices=["male", "female"], help="Narrator gender")
    parser.add_argument("--country", default="my", help="Country code (default: my)")
    parser.add_argument("--voice", default=None, help="Override: explicit ElevenLabs voice ID")
    parser.add_argument("--output", default="output/final_ad.mp3", help="Final output path")

    args = parser.parse_args()

    print(f"\n{'='*60}")
    print("  Voice Ads Creation Pipeline")
    print(f"{'='*60}")
    print(f"  Idea     : {args.idea}")
    print(f"  Mood     : {args.mood}")
    print(f"  Audience : {args.audience}")
    print(f"  Language : {args.language}")
    print(f"  Gender   : {args.gender}")
    print(f"  Country  : {args.country}")
    print(f"  Output   : {args.output}")
    print(f"{'='*60}")

    success = run_pipeline(
        idea=args.idea,
        mood=args.mood,
        audience=args.audience,
        language=args.language,
        gender=args.gender,
        country=args.country,
        voice_override=args.voice,
        output=args.output,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
