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
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

# ── Google Vertex AI / Gemini ─────────────────────────────────────────────────
VERTEX_PROJECT_ID = os.environ.get("VERTEX_PROJECT_ID", "")
VERTEX_LOCATION = os.environ.get("VERTEX_LOCATION", "global")
LLM_MODEL_ID = os.environ.get("LLM_MODEL_ID", "gemini-2.0-flash")

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
