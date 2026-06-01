"""
Shared Gemini / Vertex AI Client
==================================
Single client instance used across all modules.
"""

from google import genai
from google.genai import types
from config import VERTEX_PROJECT_ID, VERTEX_LOCATION

# Main Gemini client (for text, image gen, compliance checks)
gemini_client = genai.Client(
    vertexai=True,
    project=VERTEX_PROJECT_ID,
    location=VERTEX_LOCATION,
)

# Veo client (video generation requires us-central1)
veo_client = genai.Client(
    vertexai=True,
    project=VERTEX_PROJECT_ID,
    location="us-central1",
)
