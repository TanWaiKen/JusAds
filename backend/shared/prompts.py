"""
prompts.py
──────────
Centralized prompt registry — loads all LLM prompts from ``docs/prompts/*.md``
at import time and exposes them as module-level constants.

Usage::

    from shared.prompts import INTENT_DETECTION_PROMPT, TEXT_AD_GENERATION_PROMPT

Each constant corresponds to a markdown file in ``docs/prompts/``.  When a file
is missing the loader emits a warning and falls back to a short placeholder so
the application can still start (useful during development).
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Resolve ``prompts/`` relative to this file:
#   shared/prompts.py  ->  backend/shared/prompts/
_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def _load_prompt(filename: str, fallback: str = "") -> str:
    """Read a prompt template from *shared/prompts/{filename}*.

    Returns the file contents stripped of leading/trailing whitespace.
    Falls back to *fallback* (or empty string) with a warning when the
    file is missing, so import never crashes.
    """
    path = _PROMPTS_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    logger.warning("[Prompts] Prompt file not found: %s — using fallback.", path)
    return fallback.strip()


# -- Generation prompts --------------------------------------------------------

INTENT_DETECTION_PROMPT = _load_prompt("intent_detection.md")
ASSISTANT_CHAT_PROMPT = _load_prompt("assistant_chat.md")
TEXT_AD_GENERATION_PROMPT = _load_prompt("text_ad_generation.md")
IMAGE_AD_GENERATION_PROMPT = _load_prompt("image_ad_generation.md")
AUDIO_AD_GENERATION_PROMPT = _load_prompt("audio_ad_generation.md")
VIDEO_AD_GENERATION_PROMPT = _load_prompt("video_ad_generation.md")
VIDEO_DIRECTOR_PROMPT = _load_prompt("video_director.md")
VIDEO_EDIT_PLANNER_PROMPT = _load_prompt("video_edit_planner.md")

# -- Compliance prompts --------------------------------------------------------

COMPLIANCE_FRAMEWORK = _load_prompt("compliance_framework.md")
TEXT_COMPLIANCE_PROMPT = _load_prompt("text_compliance.md")
IMAGE_COMPLIANCE_PROMPT = _load_prompt("image_compliance.md")
AUDIO_COMPLIANCE_PROMPT = _load_prompt("audio_compliance.md")
VIDEO_COMPLIANCE_PROMPT = _load_prompt("video_compliance.md")
BIAS_HALLUCINATION_PROMPT = _load_prompt("bias_hallucination.md")
REMEDIATION_TEXT_REWRITE_PROMPT = _load_prompt("remediation_text_rewrite.md")
COMPLIANCE_SEGMENTATION_PROMPT = _load_prompt("compliance_segmentation.md")
COMPLIANCE_SCULPT_TEMPLATE = _load_prompt("compliance_sculpt_template.md")

# -- Pre-scan prompts (short, kept inline) -------------------------------------

IMAGE_PRESCAN_PROMPT = (
    "What is in this image? Directly state: what product, what people are doing, "
    "what they are wearing, any text or numbers shown, and the setting. Be factual."
)
VIDEO_PRESCAN_PROMPT = (
    "What is happening in this video? Describe: people, clothing, actions, "
    "products, text on screen, setting. Be factual."
)
