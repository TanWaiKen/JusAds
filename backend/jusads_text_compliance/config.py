"""Configuration for JusAds Text Compliance

Loads environment variables and provides defaults for Qdrant and AWS Bedrock.
Reuses existing collections from culture_compliance module.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from jusads_text_compliance directory, then fallback to backend/
load_dotenv(Path(__file__).resolve().parent / ".env")
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ── Qdrant Configuration ──────────────────────────────────────────────────────
QDRANT_URL = os.environ.get("QDRANT_URL", "")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", "")

# Collection names (reuse from culture_compliance)
REGULATORY_COLLECTION_MALAYSIA = "mcmc-guidelines"
CULTURAL_COLLECTION = "cultural-guidelines"
PERSONA_COLLECTION = "cultural-personas"

# Retrieval settings
TOP_K_REGULATORY = int(os.environ.get("TOP_K_REGULATORY", "10"))
TOP_K_CULTURAL = int(os.environ.get("TOP_K_CULTURAL", "10"))

# ── Google Gemini (LLM for evaluation) ────────────────────────────────────────
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY", "")
LLM_MODEL_ID = os.environ.get("LLM_MODEL_ID", "gemini-2.5-flash")
if any(legacy in LLM_MODEL_ID for legacy in ("nova", "claude", "apac", "amazon")):
    LLM_MODEL_ID = "gemini-2.5-flash"

# ── Embedding Model ───────────────────────────────────────────────────────────
# Using Gemini text-embedding-004 (768-dim)
EMBED_MODEL_ID = os.environ.get("EMBED_MODEL_ID", "text-embedding-004")
if any(legacy in EMBED_MODEL_ID for legacy in ("cohere", "global", "titan")):
    EMBED_MODEL_ID = "text-embedding-004"
EMBED_DIMENSIONS = int(os.environ.get("EMBED_DIMENSIONS", "768"))
