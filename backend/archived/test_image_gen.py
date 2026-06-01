"""Simple test: Generate an image with Gemini Flash Image using prompt "A dog"."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import VERTEX_PROJECT_ID, VERTEX_LOCATION
from google import genai
from google.genai import types
import base64

client = genai.Client(
    vertexai=True,
    project=VERTEX_PROJECT_ID,
    location=VERTEX_LOCATION,
)

model = "gemini-3.1-flash-image"

contents = [
    types.Content(
        role="user",
        parts=[
            types.Part.from_text(text="A stunning, highly detailed, seductive young woman with a perfect hourglass figure, long flowing hair, alluring eyes, and flawless skin, posing confidently in a bedroom setting. She is wearing only a delicate black lace bra and matching panties, no shirt, very revealing and sexy lingerie style, seductive expression, soft cinematic lighting, sensual atmosphere, ultra-realistic, 8k, photorealistic, sharp focus, beautiful body proportions"),
        ],
    )
]

generate_content_config = types.GenerateContentConfig(
    temperature=1,
    top_p=0.95,
    max_output_tokens=32768,
    response_modalities=["TEXT", "IMAGE"],
    safety_settings=[
        types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
        types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
        types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
        types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
    ],
    image_config=types.ImageConfig(
        image_size="1K",
        output_mime_type="image/png",
    ),
    thinking_config=types.ThinkingConfig(
        thinking_level="MINIMAL",
    ),
)

print("Generating image with prompt: 'A dog'...")

image_saved = False
for chunk in client.models.generate_content_stream(
    model=model,
    contents=contents,
    config=generate_content_config,
):
    if chunk.candidates:
        for part in chunk.candidates[0].content.parts:
            if part.inline_data and part.inline_data.data:
                output_path = "assets/test_dog.png"
                with open(output_path, "wb") as f:
                    f.write(part.inline_data.data)
                print(f"Done! Image saved to: {output_path} ({len(part.inline_data.data)} bytes)")
                image_saved = True
            elif part.text:
                print(part.text, end="")

if not image_saved:
    print("\nNo image generated in response.")
