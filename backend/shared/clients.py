"""
clients.py
──────────
All external service client instances live here.
Import the raw client you need from this module.

Client initialization is resilient (Req 3.1, 3.7): each client is created inside
a ``try/except`` block that catches any initialization exception without
propagating it to the caller. On failure the client is set to ``None`` and an
error is logged with the ``[Clients]`` module prefix, so the application can fall
back to local storage / deferred retry and continue startup rather than crashing
at import time. Downstream module functions already wrap their calls in
``try/except`` and degrade gracefully when a client is unavailable.
"""

import logging

import boto3
from google import genai
from elevenlabs import ElevenLabs
from supabase import create_client, Client
from tavily import TavilyClient

from config import (
    VERTEX_PROJECT_ID,
    VERTEX_LOCATION,
    ELEVENLABS_API_KEY,
    TAVILY_API_KEY,
    SUPABASE_URL,
    SUPABASE_KEY,
    AWS_REGION,
    S3_BUCKET_NAME,
)

logger = logging.getLogger(__name__)

# -- Gemini (Vertex AI) --------------------------------------------------------
try:
    gemini = genai.Client(vertexai=True, project=VERTEX_PROJECT_ID, location=VERTEX_LOCATION)
    logger.info("[Clients] Gemini (Vertex AI) client initialized")
except Exception as e:  # noqa: BLE001 - resilient init, do not propagate (Req 3.1)
    logger.error("[Clients] Gemini client init failed; AI generation will degrade: %s", e)
    gemini = None

# -- ElevenLabs ----------------------------------------------------------------
try:
    elevenlabs = ElevenLabs(api_key=ELEVENLABS_API_KEY)
    logger.info("[Clients] ElevenLabs client initialized")
except Exception as e:  # noqa: BLE001 - resilient init, do not propagate (Req 3.1)
    logger.error("[Clients] ElevenLabs client init failed; TTS will degrade: %s", e)
    elevenlabs = None

# -- Tavily --------------------------------------------------------------------
try:
    tavily = TavilyClient(api_key=TAVILY_API_KEY)
    logger.info("[Clients] Tavily client initialized")
except Exception as e:  # noqa: BLE001 - resilient init, do not propagate (Req 3.1)
    logger.error("[Clients] Tavily client init failed; web search will degrade: %s", e)
    tavily = None

# -- Supabase -------------------------------------------------------------------
try:
    supabase: Client = create_client(supabase_url=SUPABASE_URL, supabase_key=SUPABASE_KEY)
    logger.info("[Clients] Supabase client initialized")
except Exception as e:  # noqa: BLE001 - resilient init; fall back to local storage (Req 3.7)
    logger.error(
        "[Clients] Supabase client init failed; falling back to local storage: %s", e
    )
    supabase = None

# -- AWS S3 ---------------------------------------------------------------------
try:
    s3 = boto3.client("s3", region_name=AWS_REGION)
    logger.info("[Clients] S3 client initialized")
except Exception as e:  # noqa: BLE001 - resilient init; fall back to local storage (Req 3.7)
    logger.error("[Clients] S3 client init failed; falling back to local storage: %s", e)
    s3 = None

# -- AWS Transcribe -------------------------------------------------------------
try:
    transcribe = boto3.client("transcribe", region_name=AWS_REGION)
    logger.info("[Clients] Transcribe client initialized")
except Exception as e:  # noqa: BLE001 - resilient init, do not propagate (Req 3.1)
    logger.error("[Clients] Transcribe client init failed; transcription will degrade: %s", e)
    transcribe = None
