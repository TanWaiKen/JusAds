"""
Video Remediator — Takes compliance results and produces a compliant script + visual edit guide.
"""

import json
import logging
import mimetypes
from typing import Any

from google import genai
from google.genai import types

from config import VERTEX_PROJECT_ID, VERTEX_LOCATION

logger = logging.getLogger(__name__)

client = genai.Client(vertexai=True, project=VERTEX_PROJECT_ID, location=VERTEX_LOCATION)


class VideoRemediator:
    """Produces a compliant rewrite of a video ad (script + visual edit guide)."""

    def remediate(
        self,
        video_path: str,
        compliance_result: dict[str, Any],
        market: str = "malaysia",
        ethnicity: str = "all",
        age_group: str = "all_ages",
    ) -> dict[str, Any]:
        """Generate a compliant script and visual edit guide for a flagged video.

        Args:
            video_path: Path to the original video.
            compliance_result: The output from VideoComplianceChecker.check_compliance().
            market: Target market.
            ethnicity: Target ethnicity.
            age_group: Target age group.

        Returns:
            Dict with rewritten_script, visual_edit_guide, and changes_made.
        """
        # Load original video bytes so Gemini can reference the visuals
        try:
            with open(video_path, "rb") as f:
                video_bytes = f.read()
            mime_type, _ = mimetypes.guess_type(video_path)
            if not mime_type:
                mime_type = "video/mp4"
        except Exception as e:
            logger.error(f"Failed to load video: {e}")
            return {
                "rewritten_script": "",
                "visual_edit_guide": [],
                "changes_made": [f"Failed to load video: {e}"],
            }

        prompt = self._build_prompt(compliance_result, market, ethnicity)

        try:
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=prompt),
                        types.Part.from_bytes(data=video_bytes, mime_type=mime_type),
                    ],
                )
            ]

            response = client.models.generate_content(
                model="gemini-3.1-flash-lite",
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=8192,
                    safety_settings=[
                        types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
                        types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
                        types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
                        types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
                    ],
                    thinking_config=types.ThinkingConfig(thinking_level="MEDIUM"),
                ),
            )
            return self._parse_response(response.text)
        except Exception as e:
            logger.error(f"Video remediation failed: {e}")
            return {
                "rewritten_script": "",
                "visual_edit_guide": [],
                "changes_made": [f"Remediation failed: {e}"],
            }

    def _build_prompt(
        self,
        compliance_result: dict[str, Any],
        market: str,
        ethnicity: str,
    ) -> str:
        transcript = compliance_result.get("transcript_used", "")
        indicators = compliance_result.get("high_risk_indicators", [])
        explanation = compliance_result.get("explanation", "")
        suggestion = compliance_result.get("suggestion", "")

        return f"""You are an expert video advertising director specializing in culturally compliant commercials for {market.title()} audiences (target ethnicity: {ethnicity}).

## TASK
Watch the attached video advertisement. It has been flagged for cultural compliance issues. Produce:
1. A **rewritten spoken script** that fixes all flagged audio/dialogue issues while preserving the product pitch.
2. A **scene-by-scene visual edit guide** describing what visual changes are needed at each point in the video.
3. A summary of all changes made.

## ORIGINAL TRANSCRIPT
{transcript}

## COMPLIANCE ISSUES DETECTED
**High Risk Indicators:**
{json.dumps(indicators, indent=2, ensure_ascii=False)}

**Explanation:**
{explanation}

**Suggestion:**
{suggestion}

## RULES
1. Fix every flagged issue (both audio and visual).
2. Preserve the core product pitch and brand identity.
3. Keep the rewritten script roughly the same duration as the original.
4. For the visual edit guide, reference approximate timestamps (e.g., "0:05-0:10").
5. Be specific about clothing changes, pose adjustments, and any elements to add/remove.

## OUTPUT FORMAT
Return ONLY a JSON object:
{{
  "rewritten_script": "The full corrected voiceover script...",
  "visual_edit_guide": [
    {{
      "timestamp": "0:00-0:05",
      "current": "Woman in sleeveless top introduces herself",
      "change_to": "Woman in modest long-sleeved blouse introduces herself",
      "reason": "Modesty standards require covered shoulders"
    }}
  ],
  "changes_made": [
    "Replaced 'gynecologists' reference with 'dermatologists recommend'",
    "Changed wardrobe to modest long-sleeved clothing throughout"
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
            logger.error(f"Failed to parse video remediation JSON: {e}")
            return {
                "rewritten_script": "",
                "visual_edit_guide": [],
                "changes_made": [f"Parse error: {e}"],
            }
