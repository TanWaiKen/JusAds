"""
clients.py
──────────
Shared client instances for the agent pipeline.
All external service clients are centralised here.
"""

import logging

from google import genai
from google.api_core.client_options import ClientOptions
from google.cloud.speech_v2 import SpeechClient
from qdrant_client import QdrantClient
from tavily import TavilyClient
from config import (
    VERTEX_PROJECT_ID,
    VERTEX_LOCATION,
    QDRANT_URL,
    QDRANT_API_KEY,
    ELEVENLABS_API_KEY,
    TAVILY_API_KEY,
    FLUXAI_API_KEY,
)

logger = logging.getLogger(__name__)

# ── Gemini (Vertex AI) ────────────────────────────────────────────────────────
gemini = genai.Client(vertexai=True, project=VERTEX_PROJECT_ID, location=VERTEX_LOCATION)

# ── Google Cloud Speech-to-Text (Chirp 3) ─────────────────────────────────────
STT_LOCATION = "us"
speech_client = SpeechClient(
    client_options=ClientOptions(api_endpoint=f"{STT_LOCATION}-speech.googleapis.com")
)
speech_recognizer = speech_client.recognizer_path(VERTEX_PROJECT_ID, STT_LOCATION, "_")

# ── Qdrant ────────────────────────────────────────────────────────────────────
qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

# ── ElevenLabs ────────────────────────────────────────────────────────────────
try:
    from elevenlabs import ElevenLabs
    elevenlabs = ElevenLabs(api_key=ELEVENLABS_API_KEY)
except Exception as e:
    logger.warning(f"ElevenLabs client unavailable: {e}")
    elevenlabs = None

# ── Tavily ────────────────────────────────────────────────────────────────────
tavily = TavilyClient(TAVILY_API_KEY)
