"""
🌟 CORE COMPLIANCE ENGINE - MAIN ENTRY POINT 🌟

JusAds Text Compliance Checker
================================

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

from config import VERTEX_PROJECT_ID, VERTEX_LOCATION, LLM_MODEL_ID
from .embeddings import embed_text
from .qdrant_client import JusAdsQdrantClient

logger = logging.getLogger(__name__)

# Initialize Google GenAI Client
client = genai.Client(vertexai=True, project=VERTEX_PROJECT_ID, location=VERTEX_LOCATION)


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
        logger.info("Retrieving structured persona for %s/%s...", market, ethnicity)
        try:
            import json
            from pathlib import Path
            persona_file = Path(__file__).parent / "personas" / f"{market}_personas.json"
            if persona_file.exists():
                with open(persona_file, "r", encoding="utf-8") as f:
                    all_personas = json.load(f)

                if ethnicity != "all":
                    # Load ethnicity-specific persona
                    if ethnicity in all_personas:
                        base_persona = all_personas[ethnicity].copy()
                        
                        # Layer on age-specific overrides if applicable
                        if age_group != "all_ages" and "age_groups" in base_persona:
                            if age_group in base_persona["age_groups"]:
                                age_layer = base_persona["age_groups"][age_group]
                                resolved_persona = {
                                    "base": base_persona,
                                    "targeted": age_layer
                                }
                                # Clean up the output to avoid dumping all age groups to the LLM
                                if "age_groups" in resolved_persona["base"]:
                                    del resolved_persona["base"]["age_groups"]
                                
                                persona_text = json.dumps(resolved_persona, indent=2, ensure_ascii=False)
                            else:
                                logger.warning("Age group %s not found for %s/%s, defaulting to base", age_group, market, ethnicity)
                                if "age_groups" in base_persona:
                                    del base_persona["age_groups"]
                                persona_text = json.dumps(base_persona, indent=2, ensure_ascii=False)
                        else:
                            if "age_groups" in base_persona:
                                del base_persona["age_groups"]
                            persona_text = json.dumps(base_persona, indent=2, ensure_ascii=False)
                else:
                    # ethnicity == "all" → load nation-level context from _meta._nation_notes
                    meta = all_personas.get("_meta", {})
                    nation_notes = meta.get("_nation_notes")
                    if nation_notes:
                        persona_text = json.dumps({
                            "country": meta.get("country", market.title()),
                            "scope": "nation-level (all ethnicities)",
                            "nation_notes": nation_notes
                        }, indent=2, ensure_ascii=False)
                    else:
                        logger.warning("No _nation_notes found in _meta for %s", market)

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
            "risk_percentage": evaluation.get("RISK_PERCENTAGE", 50),
            "risk_band": evaluation.get("RISK_BAND", "Moderate"),
            "confidence": evaluation.get("CONFIDENCE", "low"),
            "risk_level": evaluation.get("RISK_BAND", "Moderate"),  # backward compat
            "score": 100 - evaluation.get("RISK_PERCENTAGE", 50),   # backward compat
            "high_risk_indicators": evaluation.get("high_risk_indicator", evaluation.get("high_risk_indicators", [])),
            "explanation": evaluation.get("explanation", ""),
            "suggestion": evaluation.get("suggestion", ""),
            "persona_used": persona_text if persona_text else "No specific persona (ethnicity: all)",
            "regulatory_rules_count": len(regulatory_rules),
            "cultural_rules_count": len(cultural_guidelines),
            "processing_time_ms": duration_ms,
        }

        logger.info(
            "Compliance check completed in %dms: risk_band=%s, risk_percentage=%d%%",
            duration_ms,
            result["risk_band"],
            result["risk_percentage"],
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
            # Enforce JSON output at the API level via Google GenAI SDK
            response = client.models.generate_content(
                model=LLM_MODEL_ID,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            result_text = response.text

            # Parse the LLM response
            evaluation = self._parse_llm_response(result_text)
            return evaluation

        except Exception as e:
            logger.error("LLM evaluation failed: %s", str(e))
            return {
                "RISK_PERCENTAGE": 50,
                "RISK_BAND": "Moderate",
                "CONFIDENCE": "low",
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

        prompt = f"""You are a {market.title()} Cultural Appropriateness Evaluator. Your job is to take a transcript/ad text and determine whether it is culturally appropriate for a {market.title()} audience (target ethnicity: {ethnicity}).

INPUT (transcript/ad text):
{ad_text}

REGULATORY & CULTURAL GUIDELINES (from {market.title()} Communications and Multimedia Content Code & Cultural Norms):
To inform your evaluation, consider the following chunks of documents, which provide guidance on content standards in {market.title()}.

### Regulatory Guidelines
{reg_text if reg_text else "No specific regulatory rules retrieved."}

### Cultural Guidelines
{cultural_text if cultural_text else "No specific cultural guidelines retrieved."}
{persona_section}

PRIMARY TASK:
1. Read the full transcript and detect phrases, sentences or themes that may be culturally sensitive, offensive, or inappropriate for audiences in {market.title()}, paying close attention to the regulatory guidelines and persona provided above.
2. Produce ONLY a single JSON object (no extra text, no explanation outside the JSON) with the exact fields below:
   - RISK_PERCENTAGE: integer 0–100 (probability that this ad will cause cultural backlash; 0 = completely safe, 100 = certain backlash)
   - RISK_BAND: one of "Low" (0-30%), "Moderate" (31-60%), "High" (61-80%), "Critical" (81-100%)
   - CONFIDENCE: one of "high", "moderate", "low" (how confident you are in this risk assessment based on available evidence)
   - high_risk_indicator: array of strings (words/phrases or short snippets that were flagged). Include up to the top 10 flagged items, ranked by severity.
   - explanation: concise reasoning (max ~300 words) describing why the content has that RISK_PERCENTAGE. Reference which categories drove the rating and, where applicable, cite the provided REGULATORY GUIDELINES or PERSONA to justify your assessment (e.g., "This violates the guideline on..."). Note any contextual factors (e.g., satire, educational intent).
   - suggestion: clear, actionable advice (max ~200 words) for how to modify or adjust the content to reduce the cultural backlash risk for a {market.title()} audience (e.g., remove or rephrase flagged terms, replace insensitive jokes with neutral humor, provide cultural context, or add disclaimers).

**Risk Assessment Logic:**
- Start at 0% risk (completely safe)
- Add risk for each issue found:
  - Severe regulatory violation: +30%
  - Moderate regulatory violation: +20%
  - Minor regulatory violation: +10%
  - Severe cultural taboo: +25%
  - Moderate cultural sensitivity: +15%
  - Minor cultural concern: +8%
- Cap at 100%. Multiple issues compound.
- Risk Band: Low (0-30%), Moderate (31-60%), High (61-80%), Critical (81-100%)
- Confidence: "high" if clear regulatory violations with strong evidence from provided rules, "moderate" if cultural nuances that could go either way, "low" if borderline/ambiguous cases

**Important:**
- Return ONLY valid JSON.
- If no issues are found, return RISK_PERCENTAGE 0, RISK_BAND "Low", CONFIDENCE "high", and empty high_risk_indicator array.
- Limit high_risk_indicator to maximum 10 items, ranked by severity (most severe first).

CONTEXTUAL RULES (how to treat context & intent):
- Quoted, reported, or critical context reduces severity by one level.
- Satire or parody: treat as contextual but only reduce if clear from transcript indicators.
- Repetition or emphasis increases severity.
- If unsure about speaker identity or target, err on the side of conservatism (raise severity).

FLAGGING RULES (for high_risk_indicator):
- Provide the exact phrase or short snippet (3–12 words) that triggered the flag.
- Exclude benign mentions of sensitive words used neutrally unless used disrespectfully.

OUTPUT FORMAT (strict):
Return exactly one JSON object and nothing else. Example structure:

{{
  "RISK_PERCENTAGE": 63,
  "RISK_BAND": "High",
  "CONFIDENCE": "moderate",
  "high_risk_indicator": [
    "insulting phrase 1",
    "derogatory stereotype about ethnicity",
    "explicit sexual description"
  ],
  "explanation": "63% probability of cultural backlash. Short, clear reasoning (max ~300 words)...",
  "suggestion": "Concrete advice (max ~200 words)..."
}}

### ONE-SHOT EXAMPLE

**Transcript Input:**  
This comedian says, "Malaysians are lazy and always late, it's just in their culture."
Later in the show, he makes a joke about religious fasting being pointless.
Finally, he uses mild profanity when complaining about traffic: "This damn traffic jam every day!"

**Expected Output (JSON only):**  
```json
{{
  "RISK_PERCENTAGE": 58,
  "RISK_BAND": "Moderate",
  "CONFIDENCE": "moderate",
  "high_risk_indicator": [
    "Malaysians are lazy and always late",
    "fasting being pointless",
    "damn traffic jam"
  ],
  "explanation": "58% risk of cultural backlash. The transcript includes an ethnic stereotype ('Malaysians are lazy' +20%), a dismissive religious comment ('fasting being pointless' +25%), and mild profanity ('damn' +8%). Contextual reduction of -5% applied for comedy context. Total risk: 58%, placing it in the Moderate band.",
  "suggestion": "Remove or rephrase the ethnic stereotype to avoid portraying Malaysians negatively, replace the dismissive joke about fasting with a neutral or positive cultural observation, and substitute profanity with lighter language."
}}
```
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
                "RISK_PERCENTAGE": 50,
                "RISK_BAND": "Moderate",
                "CONFIDENCE": "low",
                "high_risk_indicators": [],
                "explanation": "Failed to parse JSON response from LLM. Defaulting to moderate risk.",
                "suggestion": "Try again."
            }

    def _error_result(self, error_message: str) -> dict[str, Any]:
        """Return a standardized error result."""
        return {
            "risk_percentage": 50,
            "risk_band": "Moderate",
            "confidence": "low",
            "risk_level": "Moderate",
            "score": 50,
            "high_risk_indicators": [],
            "explanation": error_message,
            "suggestion": "Please check your configuration and try again.",
            "persona_used": None,
            "regulatory_rules_count": 0,
            "cultural_rules_count": 0,
            "processing_time_ms": 0,
        }
