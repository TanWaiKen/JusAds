"""
prompts.py
──────────
All fixed prompts used by the compliance pipeline.

This module re-exports prompts loaded from ``docs/prompts/*.md`` via the
centralised ``shared.prompts`` registry.  Downstream code can continue to
import from ``jusads_compliance.prompts`` without changes.
"""

from shared.prompts import (
    COMPLIANCE_FRAMEWORK as CONTEXT_FRAMEWORK,
    TEXT_COMPLIANCE_PROMPT,
    IMAGE_COMPLIANCE_PROMPT,
    AUDIO_COMPLIANCE_PROMPT,
    VIDEO_COMPLIANCE_PROMPT,
    BIAS_HALLUCINATION_PROMPT,
    REMEDIATION_TEXT_REWRITE_PROMPT as TEXT_REWRITE_PROMPT,
    COMPLIANCE_SEGMENTATION_PROMPT as SEGMENTATION_PROMPT,
    COMPLIANCE_SCULPT_TEMPLATE as SCULPT_PROMPT_TEMPLATE,
    IMAGE_PRESCAN_PROMPT,
    VIDEO_PRESCAN_PROMPT,
)

# -- Unified output template (shared across all compliance checks) -------------
UNIFIED_OUTPUT_TEMPLATE = """{"risk_percentage": 35, "risk_level": "Moderate", "compliance_verdict": "needs_remediation", "high_risk_indicator": ["flagged item 1", "flagged item 2"], "violations_timeline": null, "localization_plan": "Use appropriate model, translate to target language, target relevant platform", "explanation": "35% risk due to...", "suggestion": "Replace or modify...", "cultural_fit_score": 70, "language_compliance": {"detected_language": "english", "required_language": "malay", "is_compliant": false, "language_note": "Target audience (Malay Baby Boomers) requires Bahasa Melayu"}}"""

__all__ = [
    "CONTEXT_FRAMEWORK",
    "UNIFIED_OUTPUT_TEMPLATE",
    "IMAGE_PRESCAN_PROMPT",
    "VIDEO_PRESCAN_PROMPT",
    "TEXT_COMPLIANCE_PROMPT",
    "IMAGE_COMPLIANCE_PROMPT",
    "AUDIO_COMPLIANCE_PROMPT",
    "VIDEO_COMPLIANCE_PROMPT",
    "BIAS_HALLUCINATION_PROMPT",
    "TEXT_REWRITE_PROMPT",
    "SEGMENTATION_PROMPT",
    "SCULPT_PROMPT_TEMPLATE",
]
