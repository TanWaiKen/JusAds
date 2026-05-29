"""
config.py
─────────
Centralised configuration for the Culture Compliance pipeline.
All secrets are read from environment variables.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from backend/ directory
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ── AWS Bedrock (Kept legacy env variables for fallback/history, default to Gemini) ──
AWS_REGION_LLM = os.environ.get("AWS_REGION_LLM", "ap-southeast-1")
AWS_REGION_EMBED = os.environ.get("AWS_REGION_EMBED", "ap-southeast-1")
EMBED_MODEL_ID = os.environ.get("EMBED_MODEL_ID", "global.cohere.embed-v4:0")
if any(legacy in EMBED_MODEL_ID for legacy in ("nova", "claude", "apac", "amazon")):
    EMBED_MODEL_ID = "global.cohere.embed-v4:0"
EMBED_DIMENSIONS = int(os.environ.get("EMBED_DIMENSIONS", "1536"))

# ── Qdrant ────────────────────────────────────────────────────────────────────
QDRANT_URL = os.environ.get("QDRANT_URL", "")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", "")
QDRANT_COLLECTION_NAME = os.environ.get("QDRANT_COLLECTION_NAME", "mcmc-guidelines")
# Updated default - expanded from 5 to 50 for comprehensive coverage
QDRANT_TOP_K = int(os.environ.get("QDRANT_TOP_K", "50"))

# New cultural collection config
CULTURAL_COLLECTION_NAME = os.environ.get(
    "CULTURAL_COLLECTION_NAME", "cultural-guidelines"
)

CULTURAL_COLLECTION_CONFIG = {
    "collection_name": "cultural-guidelines",
    "vector_size": 768,
    "distance": "Cosine",
}

# ── Persona Collection ────────────────────────────────────────────────────────
PERSONA_COLLECTION_NAME = os.environ.get(
    "PERSONA_COLLECTION_NAME", "cultural-personas"
)

PERSONA_COLLECTION_CONFIG = {
    "collection_name": "cultural-personas",
    "vector_size": 768,
    "distance": "Cosine",
}

# ── Gemini Models ─────────────────────────────────────────────────────────────
LLM_MODEL_ID = os.environ.get("LLM_MODEL_ID", "gemini-2.5-flash")
if any(legacy in LLM_MODEL_ID for legacy in ("nova", "claude", "apac", "amazon")):
    LLM_MODEL_ID = "gemini-2.5-flash"

VISION_MODEL_ID = os.environ.get("VISION_MODEL_ID", "gemini-2.5-flash")
if any(legacy in VISION_MODEL_ID for legacy in ("nova", "claude", "apac", "amazon")):
    VISION_MODEL_ID = "gemini-2.5-flash"

# ── S3 (legacy, unused in Gemini) ──────────────────────────────────────────
TRANSCRIBE_S3_BUCKET = os.environ.get("TRANSCRIBE_S3_BUCKET", "jusads-transcribe-temp")

# ── Video Understanding ──────────────────────────────────────────────────────
VIDEO_MODEL_ID = os.environ.get("VIDEO_MODEL_ID", "gemini-2.5-flash")

# ── Video Compliance Model (single-model pipeline v3) ────────────────────────
# Which model to use for direct video compliance evaluation.
# Options: "gemini" (Google Gemini File API)
VIDEO_COMPLIANCE_MODEL = os.environ.get("VIDEO_COMPLIANCE_MODEL", "gemini")
CLAUDE_VIDEO_MODEL_ID = os.environ.get(
    "CLAUDE_VIDEO_MODEL_ID", "gemini-2.5-flash"
)

