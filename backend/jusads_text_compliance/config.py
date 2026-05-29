"""Configuration for JusAds Text Compliance

Loads environment variables for:
- Qdrant (vector store)
- AWS Bedrock (Cohere embeddings)
- Google Gemini (LLM evaluation)
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from backend/ directory
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ── Qdrant ────────────────────────────────────────────────────────────────────
QDRANT_URL = os.environ.get("QDRANT_URL", "")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", "")

# Collection names (reuse from culture_compliance)
REGULATORY_COLLECTION_MALAYSIA = "mcmc-guidelines"
CULTURAL_COLLECTION = "cultural-guidelines"
PERSONA_COLLECTION = "cultural-personas"

# Retrieval settings
TOP_K_REGULATORY = int(os.environ.get("TOP_K_REGULATORY", "10"))
TOP_K_CULTURAL = int(os.environ.get("TOP_K_CULTURAL", "10"))

# ── AWS Bedrock (Cohere embeddings) ───────────────────────────────────────────
AWS_REGION_EMBED = os.environ.get("AWS_REGION_EMBED", "ap-southeast-1")
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
EMBED_MODEL_ID = "global.cohere.embed-v4:0"
EMBED_DIMENSIONS = 1536

# ── AWS Transcribe ────────────────────────────────────────────────────────────
TRANSCRIBE_S3_BUCKET = os.environ.get("TRANSCRIBE_S3_BUCKET", "")

# ── Google Gemini (LLM for evaluation via Vertex AI) ──────────────────────────
VERTEX_PROJECT_ID = os.environ.get("VERTEX_PROJECT_ID", "project-d53d74fb-f547-4728-977")
VERTEX_LOCATION = os.environ.get("VERTEX_LOCATION", "global")
LLM_MODEL_ID = os.environ.get("GEMINI_MODEL_ID", "gemini-3.1-pro-preview")
