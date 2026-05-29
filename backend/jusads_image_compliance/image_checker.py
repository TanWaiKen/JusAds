import json
import logging
import time
from typing import Any, Optional


from google import genai
from google.genai import types

from config import VERTEX_PROJECT_ID, VERTEX_LOCATION
from jusads_text_compliance.qdrant_client import JusAdsQdrantClient

logger = logging.getLogger(__name__)

# Initialize Google GenAI Client
client = genai.Client(vertexai=True, project=VERTEX_PROJECT_ID, location=VERTEX_LOCATION)

class ImageComplianceChecker:
    """Simple image compliance checker for Malaysian/Singaporean advertising."""

    def __init__(self):
        """Initialize the checker with Qdrant client."""
        self.qdrant = JusAdsQdrantClient()
        logger.info("Initialized ImageComplianceChecker")

    def check_compliance(
        self,
        image_path: str,
        market: str = "malaysia",
        ethnicity: str = "all",
        age_group: str = "all_ages",
    ) -> dict[str, Any]:
        """Check compliance of an ad image against regulatory and cultural guidelines.

        Args:
            image_path: The absolute or relative path to the image file.
            market: Target market ('malaysia' or 'singapore').
            ethnicity: Target ethnicity ('malay', 'chinese', 'indian', 'all').
            age_group: Target age group.

        Returns:
            Dictionary containing risk level, score, explanations, and flagged issues.
        """
        start_time = time.time()
        
        try:
            # Step 1: Attempt to load the image
            import mimetypes
            with open(image_path, "rb") as f:
                image_bytes = f.read()
            mime_type, _ = mimetypes.guess_type(image_path)
            if not mime_type:
                mime_type = "image/jpeg"
        except Exception as e:
            logger.error(f"Failed to load image at {image_path}: {str(e)}")
            return self._error_result(image_path, market, ethnicity, age_group, f"Failed to load image: {str(e)}")

        # Step 2: Use Qdrant to retrieve default market rules (since we don't have text to search yet,
        # we do a generic query or we can just fetch top guidelines using a generic placeholder).
        # For an image, a generic query like "advertising regulations and cultural taboos" works well.
        search_query = "advertising regulations, cultural taboos, modesty, offensive symbols"
        
        try:
            logger.info(f"Retrieving rules for market='{market}', ethnicity='{ethnicity}'")
            regulatory_rules = self.qdrant.search_regulatory_rules(
                query_text=search_query,
                market=market,
                limit=5
            )
            
            cultural_guidelines = self.qdrant.search_cultural_guidelines(
                query_text=search_query,
                market=market,
                ethnicity=ethnicity,
                limit=5
            )
        except Exception as e:
            logger.warning(f"Failed to retrieve rules from Qdrant: {e}. Proceeding without context.")
            regulatory_rules = []
            cultural_guidelines = []

        # Step 3: Get Persona Context
        persona_text = None
        logger.info(f"Retrieving structured persona for {market}/{ethnicity}...")
        try:
            from pathlib import Path
            persona_file = Path(__file__).parent.parent / "jusads_text_compliance" / "personas" / f"{market}_personas.json"
            if persona_file.exists():
                with open(persona_file, "r", encoding="utf-8") as f:
                    all_personas = json.load(f)

                if ethnicity != "all":
                    if ethnicity in all_personas:
                        base_persona = all_personas[ethnicity].copy()
                        if age_group != "all_ages" and "age_groups" in base_persona:
                            if age_group in base_persona["age_groups"]:
                                age_layer = base_persona["age_groups"][age_group]
                                resolved_persona = {"base": base_persona, "targeted": age_layer}
                                if "age_groups" in resolved_persona["base"]:
                                    del resolved_persona["base"]["age_groups"]
                                persona_text = json.dumps(resolved_persona, indent=2, ensure_ascii=False)
                            else:
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

            if not persona_text:
                logger.warning(f"No structured persona found for {market}/{ethnicity}")
        except Exception as e:
            logger.warning(f"Failed to load persona: {e}")

        # Step 4: Build Evaluation Prompt
        prompt = self._build_evaluation_prompt(
            regulatory_rules=regulatory_rules,
            cultural_guidelines=cultural_guidelines,
            persona_text=persona_text,
            market=market,
            ethnicity=ethnicity,
        )

        # Step 5: Evaluate with Gemini Multimodal Model
        evaluation = self._evaluate_with_llm(image_bytes, mime_type, prompt)

        # Step 6: Format result
        duration_ms = int((time.time() - start_time) * 1000)
        
        result = {
            "image_path": image_path,
            "market": market,
            "ethnicity": ethnicity,
            "age_group": age_group,
            "risk_level": evaluation.get("RISK", evaluation.get("risk_level", "Unknown")),
            "score": evaluation.get("SCORE", evaluation.get("score", 0)),
            "high_risk_indicators": evaluation.get("high_risk_indicator", evaluation.get("high_risk_indicators", [])),
            "explanation": evaluation.get("explanation", ""),
            "suggestion": evaluation.get("suggestion", ""),
            "persona_used": persona_text if persona_text else "No specific persona (ethnicity: all)",
            "regulatory_rules_count": len(regulatory_rules),
            "cultural_rules_count": len(cultural_guidelines),
            "processing_time_ms": duration_ms,
        }

        return result

    def _build_evaluation_prompt(
        self,
        regulatory_rules: list[dict],
        cultural_guidelines: list[dict],
        persona_text: Optional[str],
        market: str,
        ethnicity: str,
    ) -> str:
        """Build the prompt for Gemini LLM evaluation."""
        
        reg_text = "\n".join([
            f"- [{r['category']}] (Severity: {r['severity']}): {r['guideline_text']}"
            for r in regulatory_rules
        ])

        cultural_text = "\n".join([
            f"- [{g['category']}] (Severity: {g['severity']}, Ethnicity: {g['ethnicity']}): {g['guideline_text']}"
            for g in cultural_guidelines
        ])

        persona_section = ""
        if persona_text:
            persona_section = f"""
## Target Audience Persona (Structured Profile)
```json
{persona_text}
```
"""

        prompt = f"""You are a {market.title()} Cultural Appropriateness Evaluator. Your job is to analyze the provided image advertisement and determine whether it is culturally appropriate for a {market.title()} audience (target ethnicity: {ethnicity}).

REGULATORY & CULTURAL GUIDELINES (from {market.title()} Communications and Multimedia Content Code & Cultural Norms):
To inform your evaluation, consider the following rules, which provide guidance on content standards in {market.title()}.

### Regulatory Guidelines
{reg_text if reg_text else "No specific regulatory rules retrieved."}

### Cultural Guidelines
{cultural_text if cultural_text else "No specific cultural guidelines retrieved."}
{persona_section}

PRIMARY TASK:
1. Carefully inspect the visual elements of the image (e.g., clothing modesty, physical gestures, symbols, colors, character interactions).
2. Read and analyze any text or copy present in the image.
3. Detect elements that may be culturally sensitive, offensive, taboo, or inappropriate for audiences in {market.title()}, paying close attention to the regulatory guidelines and persona provided above.
4. Produce ONLY a single JSON object (no extra text, no explanation outside the JSON) with the exact fields below:
   - RISK: one of "High", "Medium", "Low"
   - SCORE: integer 0–100 (Cultural Appropriateness Score; 100 = fully appropriate)
   - high_risk_indicator: array of strings (describe specific visual elements or text phrases that were flagged). Include up to the top 10 flagged items, ranked by severity.
   - explanation: concise reasoning (max ~300 words) describing why the image received that SCORE and RISK. Reference which visual/text elements and categories drove the rating and, where applicable, cite the provided REGULATORY GUIDELINES or PERSONA to justify your assessment (e.g., "The exposed clothing violates the guideline on modesty..."). Note any contextual factors.
   - suggestion: clear, actionable advice (max ~200 words) for how to modify or adjust the image to make it more culturally appropriate for a {market.title()} audience (e.g., change clothing to be more modest, remove or rephrase flagged terms, change colors, etc.).

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
- If no issues are found, return SCORE 100, RISK "Low", and empty high_risk_indicator array.
- Limit high_risk_indicator to maximum 10 items, ranked by severity (most severe first).

CONTEXTUAL RULES (how to treat context & intent):
- Quoted, reported, or critical context reduces severity by one level.
- Satire or parody: treat as contextual but only reduce if clear.
- If unsure about target demographic, err on the side of conservatism (raise severity).

FLAGGING RULES (for high_risk_indicator):
- Provide a clear, short description of the visual element or exact text snippet that triggered the flag (e.g., "Exposed armpits on model", "Price tag of $4.44").
- Exclude benign elements.

OUTPUT FORMAT (strict):
Return exactly one JSON object and nothing else. Example structure:

{{
  "RISK": "Medium",
  "SCORE": 63,
  "high_risk_indicator": [
    "Exposed armpits on model",
    "Derogatory phrase in the background"
  ],
  "explanation": "Short, clear reasoning (max ~300 words)...",
  "suggestion": "Concrete advice (max ~200 words)..."
}}
"""
        return prompt

    def _evaluate_with_llm(self, image_bytes: bytes, mime_type: str, prompt: str) -> dict[str, Any]:
        """Send the image and prompt to Gemini and parse the JSON response."""
        try:
            logger.info("Sending image and prompt to Gemini for evaluation...")
            model = "gemini-3.1-flash-lite"
            
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=prompt),
                        types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
                    ]
                )
            ]

            generate_content_config = types.GenerateContentConfig(
                temperature=0.2, # Low temperature for consistent compliance checks
                top_p=0.95,
                max_output_tokens=8192,
                safety_settings=[
                    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
                    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
                    types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
                    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF")
                ],
                thinking_config=types.ThinkingConfig(thinking_level="MEDIUM"),
            )

            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=generate_content_config
            )

            result_text = response.text
            return self._parse_llm_response(result_text)

        except Exception as e:
            logger.error(f"Gemini API error during image compliance check: {str(e)}")
            return {
                "RISK": "High",
                "SCORE": 0,
                "high_risk_indicator": ["API Error"],
                "explanation": f"Failed to evaluate image. Error: {str(e)}",
                "suggestion": "Please check the system logs and try again."
            }

    def _parse_llm_response(self, text: str) -> dict[str, Any]:
        """Clean and parse the JSON response from the LLM."""
        try:
            clean_text = text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            elif clean_text.startswith("```"):
                clean_text = clean_text[3:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            
            clean_text = clean_text.strip()
            return json.loads(clean_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON: {e}\nRaw output: {text}")
            return {
                "RISK": "High",
                "SCORE": 0,
                "high_risk_indicator": ["Output Parsing Error"],
                "explanation": "The model failed to return valid JSON format.",
                "suggestion": "Retry the request."
            }

    def _error_result(self, image_path: str, market: str, ethnicity: str, age_group: str, error_msg: str) -> dict[str, Any]:
        """Return a structured error response matching the expected payload."""
        return {
            "image_path": image_path,
            "market": market,
            "ethnicity": ethnicity,
            "age_group": age_group,
            "risk_level": "High",
            "score": 0,
            "high_risk_indicators": ["System Error"],
            "explanation": error_msg,
            "suggestion": "Check system logs or input file path.",
            "persona_used": "None",
            "regulatory_rules_count": 0,
            "cultural_rules_count": 0,
            "processing_time_ms": 0,
        }
