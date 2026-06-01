"""
Shared ElevenLabs Client
==========================
Voice selection and TTS API helpers.
"""

import httpx
from config import (
    ELEVENLABS_API_KEY,
    ELEVENLABS_VOICE_MY_MS_MALE,
    ELEVENLABS_VOICE_MY_MS_FEMALE,
    ELEVENLABS_VOICE_MY_ZH_MALE,
    ELEVENLABS_VOICE_MY_ZH_FEMALE,
    ELEVENLABS_VOICE_MY_EN_IND_MALE,
    ELEVENLABS_VOICE_MY_EN_IND_FEMALE,
    ELEVENLABS_VOICE_SG_EN_MALE,
    ELEVENLABS_VOICE_SG_EN_FEMALE,
    ELEVENLABS_VOICE_SG_ZH_MALE,
    ELEVENLABS_VOICE_SG_ZH_FEMALE,
)

ELEVENLABS_API_BASE = "https://api.elevenlabs.io"

# Voice mapping: (market, ethnicity, gender) → voice_id
VOICE_MAP = {
    ("malaysia", "malay", "male"): ELEVENLABS_VOICE_MY_MS_MALE,
    ("malaysia", "malay", "female"): ELEVENLABS_VOICE_MY_MS_FEMALE,
    ("malaysia", "chinese", "male"): ELEVENLABS_VOICE_MY_ZH_MALE,
    ("malaysia", "chinese", "female"): ELEVENLABS_VOICE_MY_ZH_FEMALE,
    ("malaysia", "indian", "male"): ELEVENLABS_VOICE_MY_EN_IND_MALE,
    ("malaysia", "indian", "female"): ELEVENLABS_VOICE_MY_EN_IND_FEMALE,
    ("singapore", "english", "male"): ELEVENLABS_VOICE_SG_EN_MALE,
    ("singapore", "english", "female"): ELEVENLABS_VOICE_SG_EN_FEMALE,
    ("singapore", "chinese", "male"): ELEVENLABS_VOICE_SG_ZH_MALE,
    ("singapore", "chinese", "female"): ELEVENLABS_VOICE_SG_ZH_FEMALE,
}

# Language code mapping: (market, ethnicity) → language_code
LANGUAGE_MAP = {
    ("malaysia", "malay"): "ms",
    ("malaysia", "chinese"): "zh",
    ("malaysia", "indian"): "en",
    ("singapore", "english"): "en",
    ("singapore", "chinese"): "zh",
}

# Default fallback
DEFAULT_VOICE_ID = ELEVENLABS_VOICE_MY_MS_FEMALE
DEFAULT_LANGUAGE = "ms"


def select_voice(market: str, ethnicity: str, gender: str = "female") -> dict:
    """
    Select the appropriate voice for TTS.

    Args:
        market: Target market (malaysia/singapore).
        ethnicity: Target ethnicity.
        gender: male/female.

    Returns:
        Dict with voice_id, language_code, market, ethnicity, gender.
    """
    market = market.lower()
    ethnicity = ethnicity.lower()
    gender = gender.lower()

    voice_id = VOICE_MAP.get((market, ethnicity, gender), DEFAULT_VOICE_ID)
    language_code = LANGUAGE_MAP.get((market, ethnicity), DEFAULT_LANGUAGE)

    return {
        "voice_id": voice_id,
        "language_code": language_code,
        "market": market,
        "ethnicity": ethnicity,
        "gender": gender,
    }
