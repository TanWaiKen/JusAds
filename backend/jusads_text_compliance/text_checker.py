"""JusAds Text Compliance Checker

Simple, transparent text compliance evaluation using:
1. Qdrant retrieval for relevant rules + persona
2. Gemini LLM for compliance scoring

No LangGraph - just straightforward function calls.
"""

import logging
import time
from typing import Any, Optional

import vertexai
from vertexai.generative_models import GenerativeModel

from .config import VERTEX_PROJECT_ID, VERTEX_LOCATION, LLM_MODEL_ID
from .embeddings import embed_text
from .qdrant_client import JusAdsQdrantClient

logger = logging.getLogger(__name__)

# Initialize Vertex AI
vertexai.init(project=VERTEX_PROJECT_ID, location=VERTEX_LOCATION)
model = GenerativeModel(LLM_MODEL_ID)


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
            "high_risk_indicators": evaluation.get("high_risk_indicators", []),
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
            # Enforce JSON output at the API level via Vertex AI
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            result_text = response.text

            # Parse the LLM response
            evaluation = self._parse_llm_response(result_text)
            return evaluation

        except Exception as e:
            logger.error("LLM evaluation failed: %s", str(e))
            return {
                "risk_level": "Unknown",
                "score": 0,
                "high_risk_indicators": [],
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

**Output Format:**
Produce ONLY a single JSON object (no extra text, no explanation outside the JSON) with these exact fields:
{{
  "risk_level": "High" | "Medium" | "Low",
  "score": integer 0-100,
  "high_risk_indicators": [{{"description": "category, severity, and explanation of violation"}}],
  "explanation": "concise reasoning (max 500 characters)",
  "suggestion": "clear, actionable advice (max 400 characters)"
}}

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
- Return ONLY valid JSON.
- If no issues are found, return score 100, risk_level "Low", and empty high_risk_indicators array.
- Limit high_risk_indicators to maximum 10 items, ranked by severity (most severe first).
"""

        return prompt

    def _parse_llm_response(self, response_text: str) -> dict[str, Any]:
        """Parse the LLM response into structured evaluation dict.

        Args:
            response_text: Raw text response from Gemini (JSON).

        Returns:
            Evaluation dict with risk_level, score, high_risk_indicators, explanation.
        """
        import json
        try:
            # Sometimes LLMs still wrap in markdown even when told not to
            clean_text = response_text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.startswith("```"):
                clean_text = clean_text[3:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
                
            return json.loads(clean_text)
            
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON response: %s", str(e))
            return {
                "risk_level": "Unknown",
                "score": 0,
                "high_risk_indicators": [],
                "explanation": "Failed to parse JSON response from LLM.",
                "suggestion": "Try again."
            }

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
