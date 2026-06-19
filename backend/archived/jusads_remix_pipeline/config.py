"""
config.py
─────────
Shared configuration and utility module for the JusAds Remix Pipeline.

Provides:
- API key loading from environment variables
- Voice mapping tables (market + ethnicity + gender → ElevenLabs voice ID)
- Cultural rules definitions per target audience
- Ethnicity-to-language mapping
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env from backend/ directory
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)


# ─── API Keys ─────────────────────────────────────────────────────────────────

ELEVENLABS_API_KEY: str = os.environ.get("ELEVENLABS_API_KEY", "")
GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
VERTEX_PROJECT_ID: str = os.environ.get("VERTEX_PROJECT_ID", "")
VERTEX_LOCATION: str = os.environ.get("VERTEX_LOCATION", "global")


# ─── Voice Mapping ────────────────────────────────────────────────────────────
# Maps (market, ethnicity, gender) → ElevenLabs voice ID.
# Market values: "Malaysia", "Singapore"
# Ethnicity values: "Malay", "Chinese", "Indian"
# Gender values: "male", "female"

VOICE_MAPPING: dict[tuple[str, str, str], str] = {
    # Malaysia — Malay (Bahasa Malaysia voices)
    ("Malaysia", "Malay", "male"): os.environ.get(
        "ELEVENLABS_VOICE_MY_MS_MALE", "jvcMcno3QtjOzGtfpjoI"
    ),
    ("Malaysia", "Malay", "female"): os.environ.get(
        "ELEVENLABS_VOICE_MY_MS_FEMALE", "qAJVXEQ6QgjOQ25KuoU8"
    ),
    # Malaysia — Chinese (Mandarin voices)
    ("Malaysia", "Chinese", "male"): os.environ.get(
        "ELEVENLABS_VOICE_MY_ZH_MALE", "8igW4g37ydZ0LysAbCNs"
    ),
    ("Malaysia", "Chinese", "female"): os.environ.get(
        "ELEVENLABS_VOICE_MY_ZH_FEMALE", "c2b7tErUjk7k5Zkyd4Uu"
    ),
    # Malaysia — Indian (English voices with Indian accent)
    ("Malaysia", "Indian", "male"): os.environ.get(
        "ELEVENLABS_VOICE_MY_EN_IND_MALE", "rgltZvTfiMmgWweZhh7n"
    ),
    ("Malaysia", "Indian", "female"): os.environ.get(
        "ELEVENLABS_VOICE_MY_EN_IND_FEMALE", "xPVEa1fRos3Rlvw7i1XC"
    ),
    # Singapore — English
    ("Singapore", "Chinese", "male"): os.environ.get(
        "ELEVENLABS_VOICE_SG_ZH_MALE", "aSXZu6bgEOS8MXVRzjPi"
    ),
    ("Singapore", "Chinese", "female"): os.environ.get(
        "ELEVENLABS_VOICE_SG_ZH_FEMALE", "br5zxCrqmrANOZvHTTrb"
    ),
    ("Singapore", "default", "male"): os.environ.get(
        "ELEVENLABS_VOICE_SG_EN_MALE", "aSXZu6bgEOS8MXVRzjPi"
    ),
    ("Singapore", "default", "female"): os.environ.get(
        "ELEVENLABS_VOICE_SG_EN_FEMALE", "ljEOxtzNoGEa58anWyea"
    ),
}

# Default fallback voice (English, male)
DEFAULT_VOICE_ID: str = os.environ.get(
    "ELEVENLABS_VOICE_SG_EN_MALE", "aSXZu6bgEOS8MXVRzjPi"
)


def get_voice_id(market: str, ethnicity: str, gender: str) -> str:
    """Look up an ElevenLabs voice ID for a given market, ethnicity, and gender.

    Falls back to the default English voice if the combination is not found.

    Args:
        market: Target market (e.g. "Malaysia", "Singapore").
        ethnicity: Target ethnicity (e.g. "Malay", "Chinese", "Indian").
        gender: Voice gender ("male" or "female").

    Returns:
        ElevenLabs voice ID string.
    """
    key = (market, ethnicity, gender)
    if key in VOICE_MAPPING:
        return VOICE_MAPPING[key]

    # Try market + default ethnicity
    fallback_key = (market, "default", gender)
    if fallback_key in VOICE_MAPPING:
        return VOICE_MAPPING[fallback_key]

    return DEFAULT_VOICE_ID


# ─── Cultural Rules ───────────────────────────────────────────────────────────
# Rules applied during image generation and storyboard generation prompts.


@dataclass(frozen=True)
class CulturalRules:
    """Cultural constraints for a target audience."""

    ethnicity: str
    model_ethnicity: str
    hijab_required_for_females: bool = False
    modest_dress_required: bool = False
    modest_dress_description: str = ""
    additional_constraints: list[str] = field(default_factory=list)

    def to_prompt_instructions(self) -> str:
        """Convert cultural rules to a prompt instruction string for image/video generation."""
        instructions: list[str] = []
        instructions.append(f"Use ONLY {self.model_ethnicity} models/characters.")

        if self.hijab_required_for_females:
            instructions.append(
                "All female models MUST wear hijab (headscarf covering hair)."
            )

        if self.modest_dress_required:
            instructions.append(
                f"Modest dress code: {self.modest_dress_description}"
            )

        for constraint in self.additional_constraints:
            instructions.append(constraint)

        return " ".join(instructions)


# Pre-defined cultural rules per ethnicity
CULTURAL_RULES: dict[str, CulturalRules] = {
    "Malay": CulturalRules(
        ethnicity="Malay",
        model_ethnicity="Malay",
        hijab_required_for_females=True,
        modest_dress_required=True,
        modest_dress_description=(
            "No exposed skin above the elbow or below the knee for all models. "
            "Males must wear modest clothing (long sleeves, long pants or traditional attire)."
        ),
    ),
    "Chinese": CulturalRules(
        ethnicity="Chinese",
        model_ethnicity="Chinese",
        hijab_required_for_females=False,
        modest_dress_required=False,
    ),
}


def get_cultural_rules(ethnicity: str) -> Optional[CulturalRules]:
    """Get cultural rules for a given ethnicity.

    Args:
        ethnicity: Target audience ethnicity (e.g. "Malay", "Chinese").

    Returns:
        CulturalRules instance if rules are defined for the ethnicity, else None.
    """
    return CULTURAL_RULES.get(ethnicity)


def get_cultural_prompt(ethnicity: str) -> str:
    """Get the prompt instruction string for cultural rules.

    Returns an empty string if no rules are defined for the ethnicity.

    Args:
        ethnicity: Target audience ethnicity.

    Returns:
        Prompt instruction string for image/video generation.
    """
    rules = get_cultural_rules(ethnicity)
    if rules is None:
        return ""
    return rules.to_prompt_instructions()


# ─── Ethnicity-to-Language Mapping ────────────────────────────────────────────
# Used by the Script Generator and Text Remixer for voiceover and text localization.

ETHNICITY_LANGUAGE_MAP: dict[str, str] = {
    "Chinese": "Mandarin",
    "Malay": "Bahasa Malaysia",
}

DEFAULT_LANGUAGE: str = "English"


def get_language_for_ethnicity(ethnicity: Optional[str]) -> str:
    """Map a target audience ethnicity to the appropriate voiceover/text language.

    Falls back to English if the ethnicity is not specified or not in the
    supported set.

    Args:
        ethnicity: Target audience ethnicity (e.g. "Chinese", "Malay"),
                   or None if not specified.

    Returns:
        Language string (e.g. "Mandarin", "Bahasa Malaysia", "English").
    """
    if ethnicity is None:
        return DEFAULT_LANGUAGE
    return ETHNICITY_LANGUAGE_MAP.get(ethnicity, DEFAULT_LANGUAGE)
