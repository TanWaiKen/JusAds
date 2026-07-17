"""
easy_mode_prompts.py
────────────────────
Hidden prompt enhancement injection for Easy Generation mode.

Wraps the existing `assemble_guided_message()` with quality enhancement terms
(for image types) or AIDA framework instructions (for text_copy), and builds
a full PromptProvenance audit trail for each generated version.

Users never see the hidden enhancements — they produce professional-quality
output without the user needing design expertise.
"""

import logging
from typing import Any, TypedDict

from jusads_generation.guided_prompts import assemble_guided_message
from shared.config import MODEL_TEXT

logger = logging.getLogger(__name__)

# --- Hidden Enhancement Constants --------------------------------------------

IMAGE_QUALITY_ENHANCEMENTS: str = (
    "professional commercial photography, 8K, sharp focus, high contrast, "
    "vibrant colors suitable for social media"
)

IMAGE_NEGATIVE_CONSTRAINTS: str = (
    "no watermark, no text artifacts, no blurry, no amateur, "
    "no low quality, no distorted"
)

TEXT_AIDA_INSTRUCTIONS: str = (
    "Structure using AIDA framework: Attention → Interest → Desire → Action. "
    "Respect platform character limits."
)

# --- Image design types that receive quality enhancements --------------------

_IMAGE_DESIGN_TYPES: set[str] = {"image_poster", "carousel"}

# --- PromptProvenance TypedDict ----------------------------------------------


class PromptProvenance(TypedDict):
    """Full audit trail for a generated version."""

    original_inputs: dict[str, str]
    advanced_overrides: dict[str, Any]
    revision_instruction: str | None
    hidden_enhancements: str
    selected_model: str
    final_assembled_prompt: str


# --- Main Assembly Function --------------------------------------------------


def assemble_easy_mode_prompt(
    design_type: str,
    form_inputs: dict[str, Any],
    revision_instruction: str | None = None,
    advanced_overrides: dict[str, Any] | None = None,
) -> tuple[str, PromptProvenance]:
    """Assemble the final prompt with hidden enhancements for Easy Mode.

    Calls the existing `assemble_guided_message()` to build the base prompt,
    then injects quality enhancements (for image types) or AIDA instructions
    (for text_copy). Appends revision instructions and advanced overrides
    when provided.

    Args:
        design_type: One of the supported design types (e.g. "image_poster",
            "carousel", "text_copy").
        form_inputs: Dict of field_name → value from the Easy Mode form.
        revision_instruction: Optional free-text feedback for regeneration.
        advanced_overrides: Optional dict with keys like "quality", "styleStrength",
            "keepLayout", "extraInstructions".

    Returns:
        A tuple of (final_prompt, provenance_record) where provenance_record
        is a PromptProvenance TypedDict containing the full audit trail.

    Raises:
        ValueError: If design_type is not recognized or required fields are missing
            (propagated from assemble_guided_message).
    """
    logger.info(
        "[EasyModePrompts] Assembling prompt for design_type=%s", design_type
    )

    # Normalize overrides
    overrides = advanced_overrides or {}

    # Step 1: Build base prompt using existing guided message assembly
    base_prompt = assemble_guided_message(design_type, form_inputs)

    # Step 2: Determine and inject hidden enhancements
    hidden_enhancements = _build_hidden_enhancements(design_type, overrides)

    # Step 3: Compose the final prompt
    final_prompt = base_prompt

    if hidden_enhancements:
        final_prompt = f"{final_prompt}\n\n{hidden_enhancements}"

    # Step 4: Append revision instruction if provided
    if revision_instruction:
        final_prompt = (
            f"{final_prompt}\n\n"
            f"REVISION REQUEST: {revision_instruction}"
        )

    # Step 5: Append advanced override extra instructions if provided
    extra_instructions = overrides.get("extraInstructions", "")
    if extra_instructions:
        final_prompt = (
            f"{final_prompt}\n\n"
            f"ADDITIONAL INSTRUCTIONS: {extra_instructions}"
        )

    logger.info(
        "[EasyModePrompts] Final prompt length: %d chars, "
        "hidden enhancements: %d chars",
        len(final_prompt),
        len(hidden_enhancements),
    )

    # Step 6: Build provenance record
    provenance: PromptProvenance = {
        "original_inputs": {k: str(v) for k, v in form_inputs.items()},
        "advanced_overrides": overrides,
        "revision_instruction": revision_instruction,
        "hidden_enhancements": hidden_enhancements,
        "selected_model": MODEL_TEXT,
        "final_assembled_prompt": final_prompt,
    }

    return final_prompt, provenance


# --- Internal Helpers --------------------------------------------------------


def _build_hidden_enhancements(
    design_type: str,
    overrides: dict[str, Any],
) -> str:
    """Build the hidden enhancement string based on design type and overrides.

    For image design types (image_poster, carousel): injects quality terms
    and negative constraints. For text_copy: injects AIDA instructions.

    Args:
        design_type: The backend design type string.
        overrides: Advanced overrides dict (may contain "quality" key).

    Returns:
        The hidden enhancements string to inject into the prompt.
    """
    parts: list[str] = []

    if design_type in _IMAGE_DESIGN_TYPES:
        parts.append(f"QUALITY ENHANCEMENT: {IMAGE_QUALITY_ENHANCEMENTS}")
        parts.append(f"NEGATIVE CONSTRAINTS: {IMAGE_NEGATIVE_CONSTRAINTS}")

        # Extra quality emphasis for high quality override
        if overrides.get("quality") == "high":
            parts.append(
                "QUALITY PRIORITY: Maximum quality output requested — "
                "prioritize photorealistic detail, perfect lighting, "
                "and premium production value above all."
            )

    elif design_type == "text_copy":
        parts.append(f"FRAMEWORK: {TEXT_AIDA_INSTRUCTIONS}")

        # Extra quality emphasis for high quality text
        if overrides.get("quality") == "high":
            parts.append(
                "QUALITY PRIORITY: Premium copywriting requested — "
                "prioritize originality, emotional resonance, "
                "and conversion-optimized language."
            )

    return "\n".join(parts)
