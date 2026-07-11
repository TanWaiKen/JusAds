"""
config.py
─────────
Centralised configuration for the JusAds agent pipeline.
All secrets are read from environment variables.
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load .env from backend/ directory
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

# ── Google Vertex AI / Gemini ─────────────────────────────────────────────────
VERTEX_PROJECT_ID = os.environ.get("VERTEX_PROJECT_ID", "")
VERTEX_LOCATION = os.environ.get("VERTEX_LOCATION", "global")
LLM_MODEL_ID = "gemini-3.5-flash"

# ── Model Registry (centralised model IDs) ────────────────────────────────────
# Chat Model (Cheaper)
MODEL_TEXT = "gemini-3.5-flash"
# Video Inpainting / Video editing
MODEL_VIDEO = "gemini-omni-flash-preview"
# Image Generation
MODEL_IMAGE_CREATIVE = "gemini-3.1-flash-lite-image"
# Scene Extraction
MODEL_SCENE_EXTRACTION = "image-4.0"
# Multimodal Analysis / Image Analysis
MODEL_IMAGE_ANALYSIS = "gemini-3.5-flash"
# Voice Model
MODEL_VOICE = "eleven_multilingual_v2"
# Image Inpainting
MODEL_INPAINT = "imagen-3.0-capability-002"


# ── PredictHQ (Events Calendar) ───────────────────────────────────────────────
PREDICTHQ_API_KEY = os.environ.get("PREDICTHQ_API_KEY", "")

# ── Tavily Control ────────────────────────────────────────────────────────────
TAVILY_ENABLED = os.environ.get("TAVILY_ENABLED", "true").lower() == "true"

# ── AWS Credentials & S3 ──────────────────────────────────────────────────────
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION = os.environ.get("AWS_REGION", "ap-southeast-1")
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "")

# ── API Keys ──────────────────────────────────────────────────────────────────
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
FLUXAI_API_KEY = os.environ.get("FLUXAI_API_KEY", "")

# ── Supabase ──────────────────────────────────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

# ── ElevenLabs Voice Lookup (from Supabase brand_voices table) ────────────────
# Voice IDs are stored in the brand_voices table and fetched at runtime.
# A simple in-process cache avoids repeated DB round-trips.

_voice_cache: dict = {}


def get_voice(market: str, ethnicity: str, gender: str = "female") -> dict:
    """Look up voice_id and language_code from the brand_voices table.

    Returns ``{"voice_id": "...", "lang": "..."}`` or the hardcoded fallback
    if the DB is unreachable or no matching row exists.
    """
    cache_key = (market.lower(), ethnicity.lower(), gender.lower())

    # Return from cache if available
    if cache_key in _voice_cache:
        return _voice_cache[cache_key]

    # Query Supabase
    try:
        from shared.clients import supabase as _sb
        if _sb:
            resp = (
                _sb.table("brand_voices")
                .select("voice_id, language_code")
                .eq("market", cache_key[0])
                .eq("ethnicity", cache_key[1])
                .eq("gender", cache_key[2])
                .eq("status", "active")
                .limit(1)
                .execute()
            )
            if resp.data:
                row = resp.data[0]
                result = {"voice_id": row["voice_id"], "lang": row.get("language_code", "ms")}
                _voice_cache[cache_key] = result
                return result
    except Exception as e:
        logger.warning("[Config] brand_voices DB lookup failed, using fallback: %s", e)

    # Hardcoded fallback — MY Malay Female
    return {"voice_id": "qAJVXEQ6QgjOQ25KuoU8", "lang": "ms"}


# Convenience constant for code that just needs a safe default
DEFAULT_VOICE = {"voice_id": "qAJVXEQ6QgjOQ25KuoU8", "lang": "ms"}


# ── Zernio Distribution API ───────────────────────────────────────────────────
ZERNIO_API_KEY = os.environ.get("ZERNIO_API_KEY", "")
ZERNIO_ACCOUNT_TIKTOK = os.environ.get("ZERNIO_ACCOUNT_TIKTOK", "")
ZERNIO_ACCOUNT_INSTAGRAM = os.environ.get("ZERNIO_ACCOUNT_INSTAGRAM", "")


# ── CapCut / pyJianYingDraft (Intelligent Remediation — video editing) ─────────
# pyJianYingDraft is imported directly as a Python library (no separate server).
# Drafts are saved locally and can be opened in CapCut/JianYing desktop.
# FFmpeg handles the actual .mp4 rendering for API responses.


# ── Startup secret check (Req 3.5, 3.6) ───────────────────────────────────────
# At least one secret is required for the backend to serve requests. If a
# required secret is missing from the environment configuration, startup must
# halt before accepting any request, logging the missing secret BY NAME ONLY —
# never its value.
REQUIRED_SECRETS: tuple[str, ...] = ("SUPABASE_URL", "SUPABASE_KEY")


class MissingSecretError(RuntimeError):
    """Raised at startup when a required secret is absent from the environment.

    The message names the missing secret(s) only; no secret value is included.
    """


def verify_required_secrets(required: tuple[str, ...] = REQUIRED_SECRETS) -> None:
    """Halt startup if any required secret is missing (Req 3.5, 3.6).

    Loads at least one required secret from the backend environment configuration
    (Req 3.5). If a required secret cannot be loaded, raises
    :class:`MissingSecretError` before the app accepts any request, logging the
    missing secret by name without exposing any secret value (Req 3.6).

    Args:
        required: The names of the environment variables that must be present.

    Raises:
        MissingSecretError: When one or more required secrets are missing/empty.
    """
    missing = [name for name in required if not os.environ.get(name, "").strip()]
    if missing:
        # Log the NAMES only — never the values (Req 3.6).
        logger.error(
            "[Config] Startup halted: missing required secret(s): %s",
            ", ".join(missing),
        )
        raise MissingSecretError(
            "Missing required secret(s): " + ", ".join(missing)
        )
    logger.info(
        "[Config] Startup secret check passed (%d required secret(s) present)",
        len(required),
    )
