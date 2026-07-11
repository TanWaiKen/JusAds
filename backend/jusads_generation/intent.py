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

from shared.config import MODEL_TEXT
_GEMINI_MODEL = MODEL_TEXT

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

Decide which media outputs the user is EXPLICITLY asking you to CREATE/GENERATE.

IMPORTANT RULES:
- The user MUST explicitly mention or imply they want you to GENERATE/CREATE/MAKE a specific media type.
- Simply mentioning a concept (e.g., "my coffee shop") is NOT a request to generate anything.
- The message MUST contain action words (generate, create, make, design, produce, write) OR explicit media type words (image, video, text, audio, poster, banner, clip, reel, caption, voiceover).
- If the user is just chatting, asking questions, or describing something without requesting generation, return [].
- IMPORTANT: If the user says "yes", "continue", "do it", "go ahead", "generate it", "make it", "proceed" — these are CONFIRMATIONS of a previous plan. In that case, look for media type context in the same message or return ["text", "image"] as a default confirmation response.

Media types:
1. "text" — ONLY if they ask for: ad copy, captions, headlines, taglines, slogans, descriptions
2. "image" — ONLY if they ask for: ad image, poster, banner, visual, graphic, picture, photo
3. "audio" — ONLY if they ask for: radio ad, voiceover, sound, jingle, podcast ad, audio, TTS
4. "video" — ONLY if they ask for: video ad, clip, reel, TikTok video, footage, video content

Return ONLY a JSON list. Examples:
- "Generate a TikTok video ad for my coffee" → ["video"]
- "Create image and text ads for shoes" → ["text", "image"]
- "I want to promote my restaurant" → [] (no specific media type requested)
- "Make me a poster" → ["image"]
- "Yes, generate the audio" → ["audio"]
- "Continue with the audio ad" → ["audio"]
- "Hi, how are you?" → []

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
    """Deterministically classify the message using keyword matching.

    Requires BOTH a generation-intent signal AND a media type keyword.
    Without an action word, media keywords alone don't trigger generation.
    """
    lowered = user_message.lower()

    # Confirmation words — user is saying "yes" to a previous plan
    _CONFIRMATION_WORDS = (
        "yes", "yeah", "yep", "sure", "ok", "okay", "continue",
        "go ahead", "do it", "proceed", "generate it", "make it",
        "let's go", "sounds good", "perfect", "great",
    )

    # Must have at least one generation-intent action word
    _ACTION_WORDS = (
        "generate", "create", "make", "design", "produce", "write",
        "build", "craft", "compose", "develop", "prepare", "give me",
        "i want", "i need", "can you make", "please make",
    )
    has_action = any(action in lowered for action in _ACTION_WORDS)
    is_confirmation = any(confirm in lowered for confirm in _CONFIRMATION_WORDS)

    # If no action intent AND no explicit media type word, return empty
    if not has_action and not is_confirmation:
        # Still allow if message explicitly names the media type with enough context
        explicit_media = any(
            media_type in lowered
            for media_type in ("image", "video", "audio", "text ad", "poster", "banner", "reel")
        )
        if not explicit_media:
            return []

    detected: list[MediaType] = [
        media_type
        for media_type in _VALID_MEDIA_TYPES
        if any(keyword in lowered for keyword in _KEYWORDS[media_type])
    ]

    # If it's a confirmation but no specific media type found, check for audio/video keywords
    # in the message context (user might say "yes, generate the audio")
    if is_confirmation and not detected:
        # Return empty — let Gemini handle it or the orchestrator will clarify
        # This is better than defaulting to ["text", "image"] blindly
        pass

    return detected


def _normalize(candidates: list) -> list[MediaType]:
    """Filter ``candidates`` to valid media types, deduplicated, in canonical order."""
    present = {
        value.lower()
        for value in candidates
        if isinstance(value, str)
    }
    return [media_type for media_type in _VALID_MEDIA_TYPES if media_type in present]
