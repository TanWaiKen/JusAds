import os
from google import genai
from google.genai import types

from config import VERTEX_PROJECT_ID, VERTEX_LOCATION

# Initialize the global Gemini Client using Vertex AI
# Make sure VERTEX_PROJECT_ID and VERTEX_LOCATION are properly set in your .env
client = genai.Client(vertexai=True, project=VERTEX_PROJECT_ID, location=VERTEX_LOCATION)

def call_gemini_3_1_flash_lite(prompt_text: str):
    """
    Calls the gemini-3.1-flash-lite model using the configuration provided, 
    including Google Search tools, disabled safety thresholds, and Thinking Config.
    """
    model = "gemini-3.1-flash-lite"
    
    # Structure the contents as requested
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=prompt_text)
            ]
        )
    ]
    
    # Define tools (Google Search enabled)
    tools = [
        types.Tool(google_search=types.GoogleSearch()),
    ]

    # Full generation config with safety settings disabled and thinking level medium
    generate_content_config = types.GenerateContentConfig(
        temperature=1,
        top_p=0.95,
        max_output_tokens=65535,
        safety_settings=[
            types.SafetySetting(
                category="HARM_CATEGORY_HATE_SPEECH",
                threshold="OFF"
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT",
                threshold="OFF"
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                threshold="OFF"
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_HARASSMENT",
                threshold="OFF"
            )
        ],
        tools=tools,
        thinking_config=types.ThinkingConfig(
            thinking_level="MEDIUM",
        ),
    )

    # Generate the response
    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=generate_content_config
    )
    
    return response
