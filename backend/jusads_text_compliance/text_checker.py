"""JusAds Text Compliance Checker

Simple, transparent text compliance evaluation using:
1. Qdrant retrieval for relevant rules + persona
2. Gemini LLM for compliance scoring

No LangGraph - just straightforward function calls.
"""

import logging
import time
from typing import Any, Optional

from google import genai
from google.genai import types

from .config import GOOGLE_API_KEY, LLM_MODEL_ID
from .embeddings import embed_text
from .qdrant_client import JusAdsQdrantClient

logger = logging.getLogger(__name__)

# Initialize Gemini client
client = genai.Client(api_key=GOOGLE_API_KEY)


class TextComplianceChecker:
    """Simple text compliance checker for Malaysian advertising."""

    def __init__(self):
        """Initialize the checker with Qdrant client."""
        self.qdrant = JusAdsQdrantClient()
        logger.info("Initialized TextComplianceChecker")

    def check_compliance(
        self,
        ad_text: str,
        market: str = "malaysia",
        ethnicity: str = "all",
        age_group: str = "all_ages",
    ) -> dict[str, Any]:
        """Check compliance of ad text against regulatory and cultural guidelines.

        Args:
            ad_text: The advertisement text to evaluate.
            market: Target market ('malaysia' or 'singapore').
            ethnicity: Target ethnicity ('malay', 'chinese', 'indian', 'all').
            age_group: Target age group ('all_ages', 'adults_only', 'children').

        Returns:
            Compliance result dict with:
            - risk_level: 'Low', 'Medium', 'High'
            - score: 0-100 (100 = fully compliant)
            - violations: List of detected issues
            - explanation: Summary of findings
            - persona_used: Persona narrative used for evaluation
            - regulatory_rules: Retrieved regulatory guidelines
            - cultural_rules: Retrieved cultural guidelines
        """
        start_time = time.time()

        # Step 1: Generate embedding for the ad text
        logger.info("Generating embedding for ad text...")
        query_vector = embed_text(ad_text)
        if not query_vector:
            return self._error_result("Failed to generate text embedding")

        # Step 2: Retrieve regulatory rules
        logger.info("Retrieving regulatory rules for %s...", market)
        regulatory_rules = self.qdrant.get_regulatory_rules(
            query_vector=query_vector, market=market
        )

        # Step 3: Retrieve cultural guidelines
        logger.info(
            "Retrieving cultural guidelines for %s/%s/%s...", market, ethnicity, age_group
        )
        cultural_guidelines = self.qdrant.get_cultural_guidelines(
            query_vector=query_vector,
            market=market,
            ethnicity=ethnicity,
            age_group=age_group,
        )

        # Step 4: Retrieve persona (if specific ethnicity is targeted)
        persona_text = None
        if ethnicity != "all":
            logger.info("Retrieving structured persona for %s/%s...", market, ethnicity)
            try:
                import json
                from pathlib import Path
                persona_file = Path(__file__).parent / "personas" / f"{market}_personas.json"
                if persona_file.exists():
                    with open(persona_file, "r", encoding="utf-8") as f:
                        all_personas = json.load(f)
                        if ethnicity in all_personas:
                            # Format as JSON string for the LLM prompt
                            persona_text = json.dumps(all_personas[ethnicity], indent=2, ensure_ascii=False)
                if not persona_text:
                    logger.warning("No structured persona found for %s/%s", market, ethnicity)
            except Exception as e:
                logger.error("Failed to load local persona: %s", str(e))

        # Step 5: Evaluate compliance using LLM
        logger.info("Evaluating compliance with Gemini LLM...")
        evaluation = self._evaluate_with_llm(
            ad_text=ad_text,
            regulatory_rules=regulatory_rules,
            cultural_guidelines=cultural_guidelines,
            persona_text=persona_text,
            market=market,
            ethnicity=ethnicity,
        )

        duration_ms = int((time.time() - start_time) * 1000)

        # Step 6: Format result
        result = {
            "ad_text": ad_text,
            "market": market,
            "ethnicity": ethnicity,
            "age_group": age_group,
            "risk_level": evaluation.get("risk_level", "Unknown"),
            "score": evaluation.get("score", 0),
            "violations": evaluation.get("violations", []),
            "explanation": evaluation.get("explanation", ""),
            "suggestion": evaluation.get("suggestion", ""),
            "persona_used": persona_text if persona_text else "No specific persona (ethnicity: all)",
            "regulatory_rules_count": len(regulatory_rules),
            "cultural_rules_count": len(cultural_guidelines),
            "regulatory_rules": regulatory_rules,
            "cultural_rules": cultural_guidelines,
            "processing_time_ms": duration_ms,
        }

        logger.info(
            "Compliance check completed in %dms: risk_level=%s, score=%d",
            duration_ms,
            result["risk_level"],
            result["score"],
        )

        return result

    def _evaluate_with_llm(
        self,
        ad_text: str,
        regulatory_rules: list[dict],
        cultural_guidelines: list[dict],
        persona_text: Optional[str],
        market: str,
        ethnicity: str,
    ) -> dict[str, Any]:
        """Use Gemini LLM to evaluate ad text against retrieved rules.

        Args:
            ad_text: The advertisement text.
            regulatory_rules: Retrieved regulatory guidelines.
            cultural_guidelines: Retrieved cultural guidelines.
            persona_text: Optional persona narrative.
            market: Target market.
            ethnicity: Target ethnicity.

        Returns:
            Evaluation dict with risk_level, score, violations, explanation.
        """
        # Build the prompt
        prompt = self._build_evaluation_prompt(
            ad_text=ad_text,
            regulatory_rules=regulatory_rules,
            cultural_guidelines=cultural_guidelines,
            persona_text=persona_text,
            market=market,
            ethnicity=ethnicity,
        )

        try:
            response = client.models.generate_content(
                model=LLM_MODEL_ID,
                contents=prompt,
            )
            result_text = response.text

            # Parse the LLM response (expecting structured format)
            evaluation = self._parse_llm_response(result_text)
            return evaluation

        except Exception as e:
            logger.error("LLM evaluation failed: %s", str(e))
            return {
                "risk_level": "Unknown",
                "score": 0,
                "violations": [],
                "explanation": f"LLM evaluation error: {str(e)}",
                "suggestion": "Please retry or contact support.",
            }

    def _build_evaluation_prompt(
        self,
        ad_text: str,
        regulatory_rules: list[dict],
        cultural_guidelines: list[dict],
        persona_text: Optional[str],
        market: str,
        ethnicity: str,
    ) -> str:
        """Build the prompt for Gemini LLM evaluation."""
        # Format regulatory rules
        reg_text = "\n".join([
            f"- [{r['category']}] (Severity: {r['severity']}): {r['guideline_text']}"
            for r in regulatory_rules
        ])

        # Format cultural guidelines
        cultural_text = "\n".join([
            f"- [{g['category']}] (Severity: {g['severity']}, Ethnicity: {g['ethnicity']}): {g['guideline_text']}"
            for g in cultural_guidelines
        ])

        # Build persona section
        persona_section = ""
        if persona_text:
            persona_section = f"""
## Target Audience Persona (Structured Profile)

```json
{persona_text}
```
"""

        prompt = f"""You are a compliance expert evaluating advertising content for the {market.upper()} market (target ethnicity: {ethnicity}).

## Advertisement Text to Evaluate

{ad_text}

## Regulatory Guidelines ({len(regulatory_rules)} rules)

{reg_text if reg_text else "No regulatory rules retrieved."}

## Cultural Guidelines ({len(cultural_guidelines)} guidelines)

{cultural_text if cultural_text else "No cultural guidelines retrieved."}
{persona_section}

## Your Task

Evaluate the advertisement text against ALL the regulatory guidelines and cultural guidelines listed above. Consider the target audience persona if provided.

**Output Format (JSON-like structure):**

Risk Level: [Low/Medium/High]
Score: [0-100, where 100 = fully compliant]

Violations:
- [Category] (Severity: [Severe/Moderate/Minor], Source: [regulatory/cultural]): Brief description of the violation and which specific phrase or concept violates which guideline.

Explanation: A 2-3 sentence summary of the overall compliance status.

Suggestion: Concrete recommendation to fix the violations (if any).

**Scoring Logic:**
- Start at 100
- Deduct points for each violation:
  - Severe regulatory: -30 points
  - Moderate regulatory: -20 points
  - Minor regulatory: -10 points
  - Severe cultural: -25 points
  - Moderate cultural: -15 points
  - Minor cultural: -8 points
- Risk Level: Low (75-100), Medium (40-74), High (0-39)

**Important:**
- Only flag violations that are CLEARLY present in the ad text
- Quote the specific phrase or word that violates the guideline
- Be precise and avoid false positives
- If no violations are found, state "No violations detected"
"""

        return prompt

    def _parse_llm_response(self, response_text: str) -> dict[str, Any]:
        """Parse the LLM response into structured evaluation dict.

        Args:
            response_text: Raw text response from Gemini.

        Returns:
            Evaluation dict with risk_level, score, violations, explanation.
        """
        # Simple text parsing (assuming LLM follows the format)
        lines = response_text.strip().split("\n")

        result = {
            "risk_level": "Unknown",
            "score": 0,
            "violations": [],
            "explanation": "",
            "suggestion": "",
        }

        current_section = None
        violation_buffer = []

        for line in lines:
            line = line.strip()

            # Extract Risk Level
            if line.lower().startswith("risk level:"):
                risk = line.split(":", 1)[1].strip()
                result["risk_level"] = risk

            # Extract Score
            elif line.lower().startswith("score:"):
                score_text = line.split(":", 1)[1].strip()
                try:
                    result["score"] = int(score_text.split()[0])
                except (ValueError, IndexError):
                    result["score"] = 0

            # Section markers
            elif line.lower().startswith("violations:"):
                current_section = "violations"
            elif line.lower().startswith("explanation:"):
                current_section = "explanation"
                explanation_text = line.split(":", 1)[1].strip()
                if explanation_text:
                    result["explanation"] = explanation_text
            elif line.lower().startswith("suggestion:"):
                current_section = "suggestion"
                suggestion_text = line.split(":", 1)[1].strip()
                if suggestion_text:
                    result["suggestion"] = suggestion_text

            # Content lines
            elif current_section == "violations" and line.startswith("-"):
                violation_buffer.append(line[1:].strip())
            elif current_section == "explanation" and line:
                if result["explanation"]:
                    result["explanation"] += " " + line
                else:
                    result["explanation"] = line
            elif current_section == "suggestion" and line:
                if result["suggestion"]:
                    result["suggestion"] += " " + line
                else:
                    result["suggestion"] = line

        # Process violations
        result["violations"] = [{"description": v} for v in violation_buffer if v]

        # Fallbacks
        if not result["explanation"]:
            result["explanation"] = "No explanation provided by LLM."
        if not result["suggestion"]:
            result["suggestion"] = "Review the ad against the guidelines listed above."

        return result

    def _error_result(self, error_message: str) -> dict[str, Any]:
        """Return a standardized error result."""
        return {
            "risk_level": "Unknown",
            "score": 0,
            "violations": [],
            "explanation": error_message,
            "suggestion": "Please check your configuration and try again.",
            "persona_used": None,
            "regulatory_rules_count": 0,
            "cultural_rules_count": 0,
            "regulatory_rules": [],
            "cultural_rules": [],
            "processing_time_ms": 0,
        }
