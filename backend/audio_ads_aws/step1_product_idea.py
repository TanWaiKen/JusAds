"""
Step 1: Product Idea Enhancement
==================================
Enhances a rough product idea into a compelling concept using Gemini.
"""

from utils.bedrock_client import invoke_bedrock_model

def enhance_product_idea(
    idea: str,
    mood: str,
    audience: str,
    language: str = "English",
    model: str = "apac.amazon.nova-pro-v1:0",
) -> str:
    """
    Enhance a rough product idea into a concrete, compelling concept.

    Args:
        idea: Rough product idea.
        mood: Target mood (e.g. 'energetic', 'calm').
        audience: Target audience (e.g. 'young professionals').
        language: Target language for the output.
        model: Bedrock model ID.

    Returns:
        Refined product concept string (2-3 sentences).
    """
    prompt = f"""
    Enhance this product idea to make it more compelling:
    
    Original idea: {idea}
    Target mood: {mood}
    Target audience: {audience}
    Target language: {language}
    
    Make it:
    1. Clear and specific about the value proposition
    2. Appeal to {audience}
    3. Match the {mood.lower()} tone
    4. Be memorable and marketable
    
    The enhanced idea MUST be written in {language}. Keep it to 2-3 sentences.
    """

    print(f"Enhancing idea: '{idea}'...")

    response_text = invoke_bedrock_model(prompt=prompt, model_id=model, temperature=0.7)
    return response_text.strip()