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
PLATFORM_CREATIVE_GUIDE = _load_prompt("platform_creative_guide.md")
COPY_GUARDRAILS = _load_prompt("copy_guardrails.md")

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
    "Inspect this advertisement factually. Transcribe every visible word, number, "
    "badge, logo, certification mark and disclaimer exactly where legible; identify "
    "the product, people, their apparent role/age presentation and attire, setting, "
    "and any flags, conflict imagery, weapons, extremist symbols, political symbols, "
    "or religious symbols. State 'unreadable' or 'cannot verify from image' rather "
    "than guessing. Do not infer a person's religion, ethnicity, nationality, or "
    "certification status from appearance alone."
)
VIDEO_PRESCAN_PROMPT = (
    "What is happening in this video? Describe: people, clothing, actions, "
    "products, text on screen, setting. Be factual."
)
