"""
config.py
─────────
Centralised configuration for the entire Langhub backend.
All secrets are read from environment variables.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from backend/ directory
load_dotenv(Path(__file__).resolve().parent / ".env")

# ── AWS (Bedrock & Transcribe) ────────────────────────────────────────────────
AWS_REGION_LLM = os.environ.get("AWS_REGION_LLM", "ap-southeast-1")
AWS_REGION_EMBED = os.environ.get("AWS_REGION_EMBED", "ap-southeast-1")
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")

EMBED_MODEL_ID = os.environ.get("EMBED_MODEL_ID", "global.cohere.embed-v4:0")
if any(legacy in EMBED_MODEL_ID for legacy in ("nova", "claude", "apac", "amazon")):
    EMBED_MODEL_ID = "global.cohere.embed-v4:0"
EMBED_DIMENSIONS = int(os.environ.get("EMBED_DIMENSIONS", "1536"))

TRANSCRIBE_S3_BUCKET = os.environ.get("TRANSCRIBE_S3_BUCKET", "jusads-transcribe-temp")

# ── Qdrant ────────────────────────────────────────────────────────────────────
QDRANT_URL = os.environ.get("QDRANT_URL", "")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", "")

# Collection names
QDRANT_COLLECTION_NAME = os.environ.get("QDRANT_COLLECTION_NAME", "mcmc-guidelines")
REGULATORY_COLLECTION_MALAYSIA = "mcmc-guidelines"
CULTURAL_COLLECTION = "cultural-guidelines"
PERSONA_COLLECTION = "cultural-personas"

CULTURAL_COLLECTION_NAME = os.environ.get("CULTURAL_COLLECTION_NAME", "cultural-guidelines")
PERSONA_COLLECTION_NAME = os.environ.get("PERSONA_COLLECTION_NAME", "cultural-personas")

# Retrieval settings
QDRANT_TOP_K = int(os.environ.get("QDRANT_TOP_K", "50"))
TOP_K_REGULATORY = int(os.environ.get("TOP_K_REGULATORY", "10"))
TOP_K_CULTURAL = int(os.environ.get("TOP_K_CULTURAL", "10"))

CULTURAL_COLLECTION_CONFIG = {
    "collection_name": "cultural-guidelines",
    "vector_size": 768,
    "distance": "Cosine",
}

PERSONA_COLLECTION_CONFIG = {
    "collection_name": "cultural-personas",
    "vector_size": 768,
    "distance": "Cosine",
}

# ── Google Gemini (Vertex AI & standard) ──────────────────────────────────────
# Vertex AI settings for gemini-3.1-pro-preview
VERTEX_PROJECT_ID = os.environ.get("VERTEX_PROJECT_ID", "project-d53d74fb-f547-4728-977")
VERTEX_LOCATION = os.environ.get("VERTEX_LOCATION", "global")
LLM_MODEL_ID = os.environ.get("GEMINI_MODEL_ID", "gemini-3.1-pro-preview")

# Default fallback for other modules
if any(legacy in LLM_MODEL_ID for legacy in ("nova", "claude", "apac", "amazon")):
    LLM_MODEL_ID = "gemini-3.1-pro-preview"

VISION_MODEL_ID = os.environ.get("VISION_MODEL_ID", "gemini-2.5-flash")
if any(legacy in VISION_MODEL_ID for legacy in ("nova", "claude", "apac", "amazon")):
    VISION_MODEL_ID = "gemini-2.5-flash"

VIDEO_MODEL_ID = os.environ.get("VIDEO_MODEL_ID", "gemini-2.5-flash")

# ── Video Compliance Model ────────────────────────────────────────────────────
VIDEO_COMPLIANCE_MODEL = os.environ.get("VIDEO_COMPLIANCE_MODEL", "gemini")
CLAUDE_VIDEO_MODEL_ID = os.environ.get("CLAUDE_VIDEO_MODEL_ID", "gemini-2.5-flash")
