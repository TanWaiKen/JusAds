"""
clients.py
──────────
All external service client instances live here.
Import the raw client you need from this module.
"""

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

# ── Gemini (Vertex AI) ────────────────────────────────────────────────────────
gemini = genai.Client(vertexai=True, project=VERTEX_PROJECT_ID, location=VERTEX_LOCATION)

# ── ElevenLabs ────────────────────────────────────────────────────────────────
elevenlabs = ElevenLabs(api_key=ELEVENLABS_API_KEY)

# ── Tavily ────────────────────────────────────────────────────────────────────
tavily = TavilyClient(api_key=TAVILY_API_KEY)

# ── Supabase ───────────────────────────────────────────────────────────────────
supabase: Client = create_client(supabase_url=SUPABASE_URL, supabase_key=SUPABASE_KEY)

# ── AWS S3 ─────────────────────────────────────────────────────────────────────
s3 = boto3.client("s3", region_name=AWS_REGION)

# ── AWS Transcribe ─────────────────────────────────────────────────────────────
transcribe = boto3.client("transcribe", region_name=AWS_REGION)
