"""
ai_designer.py
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
AIDesigner â€” plans HOW to edit an image using a single Gemini Flash call.

Produces an EditPlan containing mode (INPAINT_INSERT or INPAINT_REMOVE)
and an inpaint_prompt (â‰¤ 60 words).

Falls back to SCULPT template + _decide_edit_mode if the Gemini call fails.
"""

import json
import logging
from typing import Optional

from shared.models import EditMode, EditPlan

logger = logging.getLogger(__name__)

# Maximum words allowed in inpaint_prompt (Imagen 3.0 limit)
MAX_PROMPT_WORDS = 60


def _truncate_prompt(prompt: str, max_words: int = MAX_PROMPT_WORDS) -> str:
    """Truncate prompt to max_words words."""
    words = prompt.split()
    if len(words) <= max_words:
        return prompt
    return " ".join(words[:max_words])


def _validate_mode(mode_str: str) -> str:
    """Validate and normalize the edit mode string.

    Returns a valid EditMode value, defaulting to INPAINT_INSERT if invalid.
    """
    valid_modes = {m.value for m in EditMode}
    if mode_str in valid_modes:
        return mode_str
    logger.warning(
        "[AIDesigner] Invalid mode '%s' â€” defaulting to INPAINT_INSERT", mode_str
    )
    return EditMode.INPAINT_INSERT.value


async def plan_edit(
    violations: list[str],
    localization_plan: str,
    platform: str,
    market: str,
    ethnicity: str,
    age_group: str,
    segmentation: Optional[dict] = None,
) -> EditPlan:
    """Use a single Gemini Flash call to plan the edit strategy.

    Args:
        violations: Non-empty list of compliance violation descriptions.
        localization_plan: Localization guidance string.
        platform: Target platform.
        market: Target market.
        ethnicity: Target ethnicity.
        age_group: Target age group.
        segmentation: Segmentation result dict (optional context).

    Returns:
        EditPlan with mode, inpaint_prompt, reasoning, target_description.
        On Gemini failure, falls back to SCULPT template.
    """
    from shared.clients import gemini
from shared.config import MODEL_TEXT
    from google.genai import types as genai_types

    prompt = f"""You are an AI art director for advertising compliance.

VIOLATIONS: {json.dumps(violations)}
LOCALIZATION PLAN: {localization_plan}
PLATFORM: {platform} | MARKET: {market}
AUDIENCE: {ethnicity}, {age_group}

Decide the BEST edit approach:
1. INPAINT_INSERT: Replace violation region with compliant content
   (e.g., swap revealing clothing with modest version, replace background)
2. INPAINT_REMOVE: Remove the violating element entirely
   (e.g., remove alcohol bottle from scene)

Then write an inpainting prompt (max 60 words) describing what
should appear in the masked region.

Return JSON: {{"mode": "INPAINT_INSERT"|"INPAINT_REMOVE",
"inpaint_prompt": "...", "reasoning": "..."}}"""

    try:
        response = gemini.models.generate_content(
            model=MODEL_TEXT,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                response_mime_type="application/json"
            ),
        )
        plan = json.loads(response.text)

        mode = _validate_mode(plan.get("mode", "INPAINT_INSERT"))
        inpaint_prompt = _truncate_prompt(plan.get("inpaint_prompt", ""))
        reasoning = plan.get("reasoning", "")

        if not inpaint_prompt:
            # Empty prompt from Gemini â€” fall back
            raise ValueError("Gemini returned empty inpaint_prompt")

        logger.info(
            "[AIDesigner] Plan: mode=%s, prompt=%s words",
            mode,
            len(inpaint_prompt.split()),
        )

        return EditPlan(
            mode=mode,
            inpaint_prompt=inpaint_prompt,
            reasoning=reasoning,
            target_description=f"Fix: {violations[0][:50]}" if violations else "Fix violations",
        )

    except Exception as e:
        logger.warning("[AIDesigner] Gemini call failed: %s â€” using SCULPT fallback", e)
        return _fallback_edit_plan(violations, market, platform, ethnicity, age_group, localization_plan)


def _fallback_edit_plan(
    violations: list[str],
    market: str,
    platform: str,
    ethnicity: str,
    age_group: str,
    localization_plan: str,
) -> EditPlan:
    """Build a fallback EditPlan from existing SCULPT template + _decide_edit_mode.

    Used when the Gemini AIDesigner call fails.
    """
    try:
        from jusads_compliance.remix_tools import _build_sculpt_prompt, _decide_edit_mode

        sculpt_prompt = _build_sculpt_prompt(
            violations, market, platform, ethnicity, age_group, localization_plan
        )
        edit_mode, inpaint_prompt = _decide_edit_mode(sculpt_prompt)

        # Map old edit mode names to new EditMode values
        mode_mapping = {
            "EDIT_MODE_INPAINT_INSERTION": EditMode.INPAINT_INSERT.value,
            "EDIT_MODE_INPAINT_REMOVAL": EditMode.INPAINT_REMOVE.value,
            "EDIT_MODE_BGSWAP": EditMode.INPAINT_INSERT.value,
            "EDIT_MODE_OUTPAINT": EditMode.INPAINT_INSERT.value,
        }
        mode = mode_mapping.get(edit_mode, EditMode.INPAINT_INSERT.value)

        return EditPlan(
            mode=mode,
            inpaint_prompt=_truncate_prompt(inpaint_prompt or sculpt_prompt[:200]),
            reasoning="Fallback: used SCULPT template due to AIDesigner failure",
            target_description=f"Fix: {violations[0][:50]}" if violations else "Fix violations",
        )
    except Exception as fallback_err:
        logger.error("[AIDesigner] SCULPT fallback also failed: %s", fallback_err)
        # Last resort: return a minimal plan
        return EditPlan(
            mode=EditMode.INPAINT_INSERT.value,
            inpaint_prompt="Replace non-compliant content with culturally appropriate compliant alternative",
            reasoning="Emergency fallback: both AIDesigner and SCULPT failed",
            target_description="Fix compliance violations",
        )

