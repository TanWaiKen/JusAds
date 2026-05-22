"""
Step 2: Ad Script Generation
==============================
Generates a 4-scene commercial script using a refined product concept.
"""

from utils.bedrock_client import invoke_bedrock_model, parse_json_response

def generate_ad_script(
    product_concept: str,
    mood: str,
    audience: str,
    language: str = "English",
    model: str = "apac.amazon.nova-pro-v1:0",
) -> list[dict]:
    """
    Generate a 4-scene commercial script.

    Args:
        product_concept: Refined product concept (from Step 1).
        mood: Target mood.
        audience: Target audience.
        language: Target language for the script (e.g. 'Cantonese').
        model: Bedrock model ID.

    Returns:
        List of scene dicts, each with:
        - number (1-4)
        - duration (seconds)
        - script (voiceover text with emotion tags)
        - videoPrompt (visual description)
        - sfxPrompt (sound effects description)

    Raises:
        RuntimeError on generation or parse failure.
    """
    prompt = f"""
        Create a 30-second commercial script with exactly 4 scenes.
        
        Refined Product Concept: {product_concept}
        Audience: {audience}
        Mood: {mood}
        Target Language: {language}
        
        Important: Include ElevenLabs v3 emotional tags in the script where appropriate 
        (e.g., [laughs], [whispers], [sarcastic], [excited]).
        
        CRITICAL: The "script" part MUST be written in {language}.
        
        Return ONLY a JSON array with 4 scenes, each with:
        - number: 1-4
        - duration: roughly how many seconds this scene takes
        - script: What the voiceover says (including emotion tags) in {language}
        - videoPrompt: Visual description for video generation (in English)
        - sfxPrompt: Sound effects description (in English)
        
        Output format:
        [{{
            "number": 1, 
            "duration": 5, 
            "script": "[excited] Hey there! Have you seen this?", 
            "videoPrompt": "...", 
            "sfxPrompt": "..."
        }}]
    """

    print("Generating ad script for concept...")

    response_text = invoke_bedrock_model(prompt=prompt, model_id=model, temperature=0.8)

    script = parse_json_response(response_text)
    print(f"Script generated: {len(script)} scenes")
    return script