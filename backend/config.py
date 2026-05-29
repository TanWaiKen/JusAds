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

# ── AWS ───────────────────────────────────────────────────────────────────────
AWS_REGION = os.environ.get("AWS_REGION", "ap-southeast-1")
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")

EMBED_MODEL_ID = os.environ.get("EMBED_MODEL_ID", "global.cohere.embed-v4:0")
EMBED_DIMENSIONS = int(os.environ.get("EMBED_DIMENSIONS", "1536"))

AWS_LLM_MODEL_ID = os.environ.get("AWS_LLM_MODEL_ID", "apac.amazon.nova-pro-v1:0")
GOOGLE_LLM_MODEL_ID = os.environ.get("GOOGLE_LLM_MODEL_ID", "gemini-3.1-flash-lite")

# Default LLM model for the app
LLM_MODEL_ID = os.environ.get("LLM_MODEL_ID", "gemini-3.1-flash-lite")
VIDEO_MODEL_ID = os.environ.get("VIDEO_MODEL_ID", "global.twelvelabs.pegasus-1-2-v1:0")

TRANSCRIBE_S3_BUCKET = os.environ.get("TRANSCRIBE_S3_BUCKET", "")

# ── API Keys (ElevenLabs, Gemini, KIE) ────────────────────────────────────────
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
KIE_API_KEY = os.environ.get("KIE_API_KEY", "")

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
QDRANT_TOP_K = int(os.environ.get("QDRANT_TOP_K", "5"))
TOP_K_REGULATORY = int(os.environ.get("TOP_K_REGULATORY", "10"))
TOP_K_CULTURAL = int(os.environ.get("TOP_K_CULTURAL", "10"))

CULTURAL_COLLECTION_CONFIG = {
    "collection_name": "cultural-guidelines",
    "vector_size": EMBED_DIMENSIONS,
    "distance": "Cosine",
}

PERSONA_COLLECTION_CONFIG = {
    "collection_name": "cultural-personas",
    "vector_size": EMBED_DIMENSIONS,
    "distance": "Cosine",
}

# ── Celery ────────────────────────────────────────────────────────────────────
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

# ── ElevenLabs Voice IDs ──────────────────────────────────────────────────────
ELEVENLABS_VOICE_MY_MS_MALE = os.environ.get("ELEVENLABS_VOICE_MY_MS_MALE", "jvcMcno3QtjOzGtfpjoI")
ELEVENLABS_VOICE_MY_MS_FEMALE = os.environ.get("ELEVENLABS_VOICE_MY_MS_FEMALE", "qAJVXEQ6QgjOQ25KuoU8")

ELEVENLABS_VOICE_MY_EN_CHI_MALE = os.environ.get("ELEVENLABS_VOICE_MY_EN_CHI_MALE", "O8ykjWKd0RjX6e5EyDuE")
ELEVENLABS_VOICE_MY_EN_CHI_FEMALE = os.environ.get("ELEVENLABS_VOICE_MY_EN_CHI_FEMALE", "FUu5jJAN31dt6KeE1fk2")
ELEVENLABS_VOICE_MY_ZH_MALE = os.environ.get("ELEVENLABS_VOICE_MY_ZH_MALE", "8igW4g37ydZ0LysAbCNs")
ELEVENLABS_VOICE_MY_ZH_FEMALE = os.environ.get("ELEVENLABS_VOICE_MY_ZH_FEMALE", "c2b7tErUjk7k5Zkyd4Uu")
ELEVENLABS_VOICE_MY_YUE = os.environ.get("ELEVENLABS_VOICE_MY_YUE", "S9m1yQMfk6zSu0QQdGqR")

ELEVENLABS_VOICE_MY_EN_IND_MALE = os.environ.get("ELEVENLABS_VOICE_MY_EN_IND_MALE", "rgltZvTfiMmgWweZhh7n")
ELEVENLABS_VOICE_MY_EN_IND_FEMALE = os.environ.get("ELEVENLABS_VOICE_MY_EN_IND_FEMALE", "xPVEa1fRos3Rlvw7i1XC")

ELEVENLABS_VOICE_SG_EN_MALE = os.environ.get("ELEVENLABS_VOICE_SG_EN_MALE", "aSXZu6bgEOS8MXVRzjPi")
ELEVENLABS_VOICE_SG_EN_FEMALE = os.environ.get("ELEVENLABS_VOICE_SG_EN_FEMALE", "ljEOxtzNoGEa58anWyea")
ELEVENLABS_VOICE_SG_ZH_MALE = os.environ.get("ELEVENLABS_VOICE_SG_ZH_MALE", "aSXZu6bgEOS8MXVRzjPi")
ELEVENLABS_VOICE_SG_ZH_FEMALE = os.environ.get("ELEVENLABS_VOICE_SG_ZH_FEMALE", "br5zxCrqmrANOZvHTTrb")

# ── Google Gemini (Vertex AI) ─────────────────────────────────────────────────
VERTEX_PROJECT_ID = os.environ.get("VERTEX_PROJECT_ID", "")
VERTEX_LOCATION = os.environ.get("VERTEX_LOCATION", "global")
