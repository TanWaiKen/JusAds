"""Configuration for JusAds Text Compliance

Loads environment variables for:
- Qdrant (vector store)
- AWS Bedrock (Cohere embeddings)
- Google Gemini (LLM evaluation)
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from jusads_text_compliance directory, then fallback to backend/
load_dotenv(Path(__file__).resolve().parent / ".env")
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

# ── Google Gemini (LLM for evaluation) ────────────────────────────────────────
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY", "")
LLM_MODEL_ID = "gemini-2.5-flash"
