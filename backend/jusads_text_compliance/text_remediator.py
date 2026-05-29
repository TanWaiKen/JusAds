"""
Text Remediator — Takes compliance results and rewrites ad text to be compliant.
"""

import json
import logging
from typing import Any

from google import genai
from google.genai import types

from config import VERTEX_PROJECT_ID, VERTEX_LOCATION

logger = logging.getLogger(__name__)

client = genai.Client(vertexai=True, project=VERTEX_PROJECT_ID, location=VERTEX_LOCATION)


class TextRemediator:
    """Rewrites ad text to fix compliance violations."""

    def remediate(
        self,
        original_text: str,
        compliance_result: dict[str, Any],
        market: str = "malaysia",
        ethnicity: str = "all",
        age_group: str = "all_ages",
    ) -> dict[str, Any]:
        """Rewrite ad text to resolve flagged compliance issues.

        Args:
            original_text: The original ad text that failed compliance.
            compliance_result: The output from TextComplianceChecker.check_compliance().
            market: Target market.
            ethnicity: Target ethnicity.
            age_group: Target age group.

        Returns:
            Dict with rewritten_text and changes_made.
        """
        prompt = self._build_prompt(original_text, compliance_result, market, ethnicity)

        try:
            response = client.models.generate_content(
                model="gemini-3.1-flash-lite",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=8192,
                    thinking_config=types.ThinkingConfig(thinking_level="MEDIUM"),
                ),
            )
            return self._parse_response(response.text)
        except Exception as e:
            logger.error(f"Text remediation failed: {e}")
            return {
                "rewritten_text": original_text,
                "changes_made": [f"Remediation failed: {e}"],
            }

    def _build_prompt(
        self,
        original_text: str,
        compliance_result: dict[str, Any],
        market: str,
        ethnicity: str,
    ) -> str:
        indicators = compliance_result.get("high_risk_indicators", [])
        explanation = compliance_result.get("explanation", "")
        suggestion = compliance_result.get("suggestion", "")

        return f"""You are an expert ad copywriter specializing in culturally sensitive advertising for {market.title()} audiences (target ethnicity: {ethnicity}).

## TASK
Rewrite the following advertisement text to fix ALL compliance violations while preserving the original marketing intent and brand voice.

## ORIGINAL TEXT
{original_text}

## COMPLIANCE ISSUES DETECTED
**High Risk Indicators:**
{json.dumps(indicators, indent=2, ensure_ascii=False)}

**Explanation:**
{explanation}

**Suggestion:**
{suggestion}

## RULES
1. Fix every flagged issue.
2. Preserve the core marketing message and product benefits.
3. Keep the same tone and style (formal/casual) as the original.
4. Keep roughly the same length (±20%).
5. If the original uses a specific language (e.g., Bahasa Melayu, Mandarin), keep that language.

## OUTPUT FORMAT
Return ONLY a JSON object with these fields:
{{
  "rewritten_text": "The corrected ad text here...",
  "changes_made": [
    "Changed X to Y because Z",
    "Removed reference to A because B"
  ]
}}
"""

    def _parse_response(self, text: str) -> dict[str, Any]:
        clean = text.strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        elif clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        try:
            return json.loads(clean.strip())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse remediation JSON: {e}")
            return {
                "rewritten_text": "",
                "changes_made": [f"Parse error: {e}"],
            }
