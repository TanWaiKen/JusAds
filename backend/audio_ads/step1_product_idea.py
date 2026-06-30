"""
Step 1: Product Idea Enhancement
==================================
Enhances a rough product idea into a compelling concept using Gemini.
"""

from classes.bedrock import Bedrock


def enhance_product_idea(
    idea: str,
    mood: str,
    audience: str,
    model: str = "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
) -> str:
    """
    Enhance a rough product idea into a concrete, compelling concept.

    Args:
        idea: Rough product idea.
        mood: Target mood (e.g. 'energetic', 'calm').
        audience: Target audience (e.g. 'young professionals').
        model: Gemini model name.

    Returns:
        Refined product concept string (2-3 sentences).
    """
    bedrock = Bedrock()

    prompt = f"""
    Enhance this product idea to make it more compelling:
    
    Original idea: {idea}
    Target mood: {mood}
    Target audience: {audience}
    
    Make it:
    1. Clear and specific about the value proposition
    2. Appeal to {audience}
    3. Match the {mood.lower()} tone
    4. Be memorable and marketable
    
    Keep it to 2-3 sentences.
    """

    print(f"Enhancing idea: '{idea}'...")

    parameters = {
        "model_id": model,
        "messages": [{
            "role": "user",
            "content": [{"text": prompt}]
        }],
        "inference_config": {
            "temperature": 0.7,
            "maxTokens": 1000
        }
    }

    response_message, _ = bedrock.converse(parameters)
    return response_message['content'][0]['text'].strip()