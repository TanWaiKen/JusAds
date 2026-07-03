"""
intent.py
─────────
Intent detection helper for the Agentic Ad Studio orchestrator.

Exposes :func:`detect_media_types`, which classifies a user's chat message into
the subset of supported media types ({text, image, audio, video}) it requests.
Classification is performed by Gemini with a deterministic keyword-based
fallback used whenever the model call fails or yields no usable result.

Unlike the legacy ``generation_agent.py`` (which defaulted to
``["text", "image"]`` when nothing matched), this detector returns ``[]`` when
no supported media type is detected so the orchestrator can request
clarification (Req 4.3).

Follows project conventions (steering ``tech.md``): ``[Intent]``-prefixed
logging via ``logging.getLogger(__name__)``, type hints, and docstrings. Never
imports from ``backend/archived/``.
"""

import json
import logging
from typing import get_args

from shared.clients import gemini

from .state import MediaType

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────────────

_GEMINI_MODEL = "gemini-2.5-flash"

# All valid media types, in a stable canonical ordering used for output.
_VALID_MEDIA_TYPES: tuple[MediaType, ...] = get_args(MediaType)

# Deterministic keyword map for the offline fallback classifier. Each media
# type maps to the substrings that signal a request for that output.
_KEYWORDS: dict[MediaType, tuple[str, ...]] = {
    "text": ("text", "caption", "copy", "headline", "tagline", "slogan"),
    "image": ("image", "picture", "photo", "poster", "banner", "visual", "graphic"),
    "audio": ("audio", "voice", "voiceover", "sound", "radio", "jingle", "podcast"),
    "video": ("video", "clip", "movie", "reel", "reels", "tiktok", "footage"),
}

_DECISION_PROMPT = """Analyze the user's advertisement request:
"{user_message}"

Decide which of the following channels are requested to be generated (you can select multiple):
1. "text" (ad copy, captions, headlines)
2. "image" (ad visual banner, poster)
3. "audio" (radio, voiceover, sound byte)
4. "video" (video ad, stitching image and voiceover)

Return ONLY a JSON list of lowercase strings representing the selected media types.
Example: ["text", "image"]
If nothing matches, return: []
Do not return any other text."""


# ─── Public API ───────────────────────────────────────────────────────────


def detect_media_types(user_message: str) -> list[MediaType]:
    """Return the media types requested in ``user_message``.

    Classifies the message into a deduplicated subset of
    {text, image, audio, video} using Gemini, falling back to a deterministic
    keyword classifier when the model call fails or produces no usable result.
    Returns ``[]`` when no supported media type is detected — the orchestrator
    treats an empty result as a signal to request clarification (Req 4.3). The
    detector never defaults to ``["text", "image"]``.

    Args:
        user_message: The raw chat message submitted by the user.

    Returns:
        A deduplicated list of detected media types in canonical order
        (text, image, audio, video). Empty when nothing is detected.
    """
    if not user_message or not user_message.strip():
        logger.info("[Intent] Empty message; no media types detected")
        return []

    detected = _classify_with_gemini(user_message)
    if detected is None:
        # Gemini failed — fall back to deterministic keyword classification.
        detected = _classify_with_keywords(user_message)
    elif not detected:
        # Gemini returned an empty/unusable set — retry via keywords as a
        # safety net before concluding nothing was requested.
        keyword_detected = _classify_with_keywords(user_message)
        if keyword_detected:
            detected = keyword_detected

    logger.info("[Intent] Detected media types: %s", detected)
    return detected


# ─── Internal helpers ─────────────────────────────────────────────────────


def _classify_with_gemini(user_message: str) -> list[MediaType] | None:
    """Classify the message with Gemini.

    Returns the detected media types on success (possibly empty), or ``None``
    when the model call or response parsing fails so the caller can fall back
    to the keyword classifier.
    """
    try:
        response = gemini.models.generate_content(
            model=_GEMINI_MODEL,
            contents=_DECISION_PROMPT.format(user_message=user_message),
        )
        raw = (response.text or "").strip().replace("```json", "").replace("```", "")
        parsed = json.loads(raw)
    except Exception as exc:  # noqa: BLE001 - degrade gracefully on any failure
        logger.error("[Intent] Gemini classification failed: %s", exc)
        return None

    if not isinstance(parsed, list):
        logger.error("[Intent] Gemini returned non-list result: %r", parsed)
        return None

    return _normalize(parsed)


def _classify_with_keywords(user_message: str) -> list[MediaType]:
    """Deterministically classify the message using keyword matching."""
    lowered = user_message.lower()
    detected: list[MediaType] = [
        media_type
        for media_type in _VALID_MEDIA_TYPES
        if any(keyword in lowered for keyword in _KEYWORDS[media_type])
    ]
    return detected


def _normalize(candidates: list) -> list[MediaType]:
    """Filter ``candidates`` to valid media types, deduplicated, in canonical order."""
    present = {
        value.lower()
        for value in candidates
        if isinstance(value, str)
    }
    return [media_type for media_type in _VALID_MEDIA_TYPES if media_type in present]
