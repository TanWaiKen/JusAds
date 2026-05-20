from step1_product_idea import enhance_product_idea
from step2_script_generation import generate_ad_script
from step3_sound_effects import generate_sfx_for_script
from step4_voiceover import generate_voiceover_for_script
from utils.elevenlabs_utils import resolve_voice_id, mix_vo_and_sfx
from dotenv import load_dotenv
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

def test_cantonese_ad():
    idea = "A smart cooling pillow that helps you sleep better in hot weather"
    mood = "Energetic and persuasive"
    audience = "Young adults living in tropical climates"
    language_name = "Cantonese (Chinese characters but colloquial Cantonese structure)"
    
    # ElevenLabs config for Cantonese
    country_code = "my"
    language_code = "yue"  # mapped to ELEVENLABS_VOICE_MY_YUE in utils
    gender = "male"
    
    print("=== Step 1: Enhancing Product Idea in Cantonese ===")
    refined_concept = enhance_product_idea(
        idea=idea, 
        mood=mood, 
        audience=audience, 
        language=language_name
    )
    print(f"\nRefined Concept:\n{refined_concept}\n")
    
    print("=== Step 2: Generating Ad Script ===")
    script = generate_ad_script(
        product_concept=refined_concept,
        mood=mood,
        audience=audience,
        language=language_name
    )
    
    print("\n--- Script Preview ---")
    for scene in script:
        n = scene.get("number", "?")
        s = scene.get("script", "")
        print(f"Scene {n}: {s}")
    print("----------------------\n")
    
    print("=== Step 3: Sound Effects (Skipping for dry run, but you can enable it) ===")
    # Un-comment to generate sound effects
    sfx_results = generate_sfx_for_script(script)
    sfx_results = [{"scene": s["number"], "path": None, "ok": False} for s in script]
    
    print("=== Step 4: Voiceover Generation ===")
    voice_id = resolve_voice_id(country_code, language_code, gender)
    if not voice_id:
        print(f"Warning: No voice ID configured for {country_code}-{language_code}-{gender}.")
        print("Please set ELEVENLABS_VOICE_MY_YUE in your .env file.")
        return
        
    print(f"Using Voice ID: {voice_id}")
    
    # Un-comment to generate Voiceover
    vo_results = generate_voiceover_for_script(script, voice_id=voice_id, language_code=language_code)
    mix_vo_and_sfx(vo_results, sfx_results, output_path="output/cantonese_ad_test.mp3")

if __name__ == "__main__":
    test_cantonese_ad()
