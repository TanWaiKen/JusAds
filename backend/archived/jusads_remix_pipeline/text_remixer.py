"""
Text Remixer — Rewrites non-compliant ad text using Gemini.

Takes violation data from the compliance audit and generates a compliant
version of the text while preserving brand voice, tone register, and
message intent. Localizes language based on target audience ethnicity.
"""

import json
import logging
from typing import Any

from google import genai
from google.genai import types

from jusads_remix_pipeline.config import (
    GEMINI_API_KEY,
    VERTEX_PROJECT_ID,
    VERTEX_LOCATION,
    get_language_for_ethnicity,
)
from jusads_remix_pipeline.models import TextRemixOutput, TextChange

logger = logging.getLogger(__name__)

# Initialize Gemini client via Vertex AI
client = genai.Client(vertexai=True, project=VERTEX_PROJECT_ID, location=VERTEX_LOCATION)

# Model used for text remix
TEXT_REMIX_MODEL = "gemini-3.1-flash-lite"

# Timeout in seconds for the Gemini API call
REMIX_TIMEOUT_SECONDS = 30


def remix_text(
    original_text: str,
    violations: list[dict],
    target_audience: dict,
) -> TextRemixOutput:
    """Rewrite ad text to eliminate compliance violations.

    Uses Gemini to produce a compliant version of the text that preserves
    brand voice, tone register, and message intent. Localizes language
    based on target audience ethnicity.

    Args:
        original_text: The original ad text (up to 5000 characters).
        violations: List of violation dicts, each containing at minimum
            'phrase', 'reason', and 'suggested_replacement'.
        target_audience: Dict with 'market', 'ethnicity', and 'age_group'.

    Returns:
        TextRemixOutput with original_text, compliant_text, and changes list.
    """
    # Requirement 1.5: Empty violations → return original unchanged
    if not violations:
        return TextRemixOutput(
            original_text=original_text,
            compliant_text=original_text,
            changes=[],
        )

    # Requirement 1.6: Filter out violations whose phrase doesn't exist in text
    applicable_violations = [
        v for v in violations
        if v.get("phrase", "") and v["phrase"] in original_text
    ]

    # If no applicable violations remain after filtering, return original
    if not applicable_violations:
        return TextRemixOutput(
            original_text=original_text,
            compliant_text=original_text,
            changes=[],
        )

    # Determine target language based on audience ethnicity
    ethnicity = target_audience.get("ethnicity")
    target_language = get_language_for_ethnicity(ethnicity)
    market = target_audience.get("market", "Malaysia")
    age_group = target_audience.get("age_group", "all_ages")

    # Build the prompt for Gemini
    prompt = _build_remix_prompt(
        original_text=original_text,
        violations=applicable_violations,
        target_language=target_language,
        market=market,
        ethnicity=ethnicity or "general",
        age_group=age_group,
    )

    try:
        # Requirement 1.7: 30-second timeout
        response = client.models.generate_content(
            model=TEXT_REMIX_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=8192,
                http_options=types.HttpOptions(timeout=REMIX_TIMEOUT_SECONDS * 1000),
            ),
        )

        result = _parse_remix_response(response.text, original_text)
        return result

    except TimeoutError as e:
        logger.error(f"Text remix timed out after {REMIX_TIMEOUT_SECONDS}s: {e}")
        return TextRemixOutput(
            original_text=original_text,
            compliant_text=original_text,
            changes=[
                TextChange(
                    original="",
                    replacement="",
                    reason=f"Remix failed: timeout after {REMIX_TIMEOUT_SECONDS} seconds",
                )
            ],
        )
    except Exception as e:
        logger.error(f"Text remix failed: {e}")
        return TextRemixOutput(
            original_text=original_text,
            compliant_text=original_text,
            changes=[
                TextChange(
                    original="",
                    replacement="",
                    reason=f"Remix failed: {str(e)}",
                )
            ],
        )


def _build_remix_prompt(
    original_text: str,
    violations: list[dict],
    target_language: str,
    market: str,
    ethnicity: str,
    age_group: str,
) -> str:
    """Build the Gemini prompt for text remix.

    Constructs a detailed prompt that instructs Gemini to rewrite the text
    while preserving brand voice, eliminating violations, and localizing
    to the target audience language.
    """
    violations_formatted = json.dumps(
        [
            {
                "phrase": v.get("phrase", ""),
                "reason": v.get("reason", ""),
                "suggested_replacement": v.get("suggested_replacement", ""),
            }
            for v in violations
        ],
        indent=2,
        ensure_ascii=False,
    )

    return f"""You are an expert advertising copywriter specializing in culturally sensitive, regulation-compliant advertising for {market} audiences.

## TASK
Rewrite the following advertisement text to eliminate ALL identified compliance violations while preserving the original brand voice, message intent, and tone register.

## ORIGINAL TEXT
{original_text}

## VIOLATIONS TO FIX
{violations_formatted}

## REQUIREMENTS
1. Eliminate every violation phrase listed above by replacing it with a compliant alternative.
2. Preserve the same product/service, the same call-to-action, and the same tone register (formal/casual/conversational) as the original.
3. Preserve the original sentence structure and vocabulary level as much as possible.
4. The output language MUST be: {target_language}
5. Target audience: {ethnicity} demographic, {age_group} age group, {market} market.
6. Keep roughly the same length as the original text.
7. Do NOT add new marketing claims not present in the original.

## OUTPUT FORMAT
Return ONLY a valid JSON object with these fields:
{{
  "compliant_text": "The full rewritten compliant text here...",
  "changes": [
    {{
      "original": "the exact original violating phrase",
      "replacement": "the compliant replacement used",
      "reason": "brief explanation of why this change was made"
    }}
  ]
}}

IMPORTANT: The "changes" array must contain one entry for each violation that was fixed. The "original" field must match the exact phrase from the violations list."""


def _parse_remix_response(response_text: str, original_text: str) -> TextRemixOutput:
    """Parse the Gemini JSON response into a TextRemixOutput.

    Handles markdown code blocks and JSON parsing errors gracefully.
    """
    clean = response_text.strip()

    # Strip markdown code fences if present
    if clean.startswith("```json"):
        clean = clean[7:]
    elif clean.startswith("```"):
        clean = clean[3:]
    if clean.endswith("```"):
        clean = clean[:-3]

    clean = clean.strip()

    try:
        data = json.loads(clean)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse remix response JSON: {e}")
        return TextRemixOutput(
            original_text=original_text,
            compliant_text=original_text,
            changes=[
                TextChange(
                    original="",
                    replacement="",
                    reason=f"Failed to parse AI response: {str(e)}",
                )
            ],
        )

    compliant_text = data.get("compliant_text", original_text)
    raw_changes = data.get("changes", [])

    changes = []
    for change in raw_changes:
        if isinstance(change, dict):
            changes.append(
                TextChange(
                    original=change.get("original", ""),
                    replacement=change.get("replacement", ""),
                    reason=change.get("reason", ""),
                )
            )

    return TextRemixOutput(
        original_text=original_text,
        compliant_text=compliant_text,
        changes=changes,
    )
