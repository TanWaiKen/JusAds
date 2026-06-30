"""
Step 2: Ad Script Generation
==============================
Generates a 4-scene commercial script using a refined product concept.
"""

from classes.bedrock import Bedrock
from utils.gemini_client import parse_json_response


def generate_ad_script(
    product_concept: str,
    mood: str,
    audience: str,
    model: str = "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
) -> list[dict]:
    """
    Generate a 4-scene commercial script.

    Args:
        product_concept: Refined product concept (from Step 1).
        mood: Target mood.
        audience: Target audience.
        model: Gemini model name.

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
    bedrock = Bedrock()

    prompt = f"""
        Create a 30-second commercial script with exactly 4 scenes.
        
        Refined Product Concept: {product_concept}
        Audience: {audience}
        Mood: {mood}
        
        Important: Include ElevenLabs v3 emotional tags in the script where appropriate 
        (e.g., [laughs], [whispers], [sarcastic], [excited]).
        
        Return ONLY a JSON array with 4 scenes, each with:
        - number: 1-4
        - duration: roughly how many seconds this scene takes
        - script: What the voiceover says (including emotion tags)
        - videoPrompt: Visual description for video generation
        - sfxPrompt: Sound effects description
        
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

    parameters = {
        "model_id": model,
        "messages": [{
            "role": "user",
            "content": [{"text": prompt}]
        }],
        "inference_config": {
            "temperature": 0.8,
            "maxTokens": 2000
        }
    }

    response_message, _ = bedrock.converse(parameters)
    script_text = response_message['content'][0]['text']

    script = parse_json_response(script_text)
    print(f"Script generated: {len(script)} scenes")
    return script