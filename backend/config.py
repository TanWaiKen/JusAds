"""
config.py
─────────
Centralised configuration for the JusAds agent pipeline.
All secrets are read from environment variables.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from backend/ directory
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

# ── Google Vertex AI ──────────────────────────────────────────────────────────
VERTEX_PROJECT_ID = os.environ.get("VERTEX_PROJECT_ID", "")
VERTEX_LOCATION = os.environ.get("VERTEX_LOCATION", "global")

# ── Qdrant Vector Database ────────────────────────────────────────────────────
QDRANT_URL = os.environ.get("QDRANT_URL", "")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", "")
QDRANT_COLLECTION_NAME = os.environ.get("QDRANT_COLLECTION_NAME", "regulatory-rules")
QDRANT_TOP_K = int(os.environ.get("QDRANT_TOP_K", "10"))

# ── API Keys ──────────────────────────────────────────────────────────────────
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
FLUXAI_API_KEY = os.environ.get("FLUXAI_API_KEY", "")

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

# ── Voice Configuration Mapping ──────────────────────────────────────────────
# Maps (market, ethnicity, gender) tuples to ElevenLabs voice_id and language code.
# Used by the Audio Remixer to select the appropriate voice for TTS generation.
VOICE_CONFIG = {
    ("malaysia", "malay", "male"): {"voice_id": ELEVENLABS_VOICE_MY_MS_MALE, "lang": "ms"},
    ("malaysia", "malay", "female"): {"voice_id": ELEVENLABS_VOICE_MY_MS_FEMALE, "lang": "ms"},
    ("malaysia", "chinese", "male"): {"voice_id": ELEVENLABS_VOICE_MY_ZH_MALE, "lang": "zh"},
    ("malaysia", "chinese", "female"): {"voice_id": ELEVENLABS_VOICE_MY_ZH_FEMALE, "lang": "zh"},
    ("malaysia", "indian", "male"): {"voice_id": ELEVENLABS_VOICE_MY_EN_IND_MALE, "lang": "en"},
    ("malaysia", "indian", "female"): {"voice_id": ELEVENLABS_VOICE_MY_EN_IND_FEMALE, "lang": "en"},
    ("singapore", "chinese", "male"): {"voice_id": ELEVENLABS_VOICE_SG_EN_MALE, "lang": "en"},
    ("singapore", "chinese", "female"): {"voice_id": ELEVENLABS_VOICE_SG_EN_FEMALE, "lang": "en"},
}

# Fallback voice when no exact (market, ethnicity, gender) match exists
DEFAULT_VOICE = {"voice_id": ELEVENLABS_VOICE_MY_MS_FEMALE, "lang": "ms"}
