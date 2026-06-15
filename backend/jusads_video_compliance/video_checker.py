import json
import logging
import time
import mimetypes
from typing import Any, Optional

from google import genai
from google.genai import types

from config import VERTEX_PROJECT_ID, VERTEX_LOCATION
from jusads_text_compliance.qdrant_client import JusAdsQdrantClient
from jusads_transcription.transcriber import Transcriber

logger = logging.getLogger(__name__)

# Initialize Google GenAI Client
client = genai.Client(vertexai=True, project=VERTEX_PROJECT_ID, location=VERTEX_LOCATION)

class VideoComplianceChecker:
    """Simple video compliance checker for Malaysian/Singaporean advertising."""

    def __init__(self):
        """Initialize the checker with Qdrant client and Transcriber."""
        self.qdrant = JusAdsQdrantClient()
        self.transcriber = Transcriber()
        logger.info("Initialized VideoComplianceChecker")

    def check_compliance(
        self,
        video_path: str,
        market: str = "malaysia",
        ethnicity: str = "all",
        age_group: str = "all_ages",
    ) -> dict[str, Any]:
        """Check compliance of a video ad against regulatory and cultural guidelines.

        Args:
            video_path: The absolute or relative path to the video file.
            market: Target market ('malaysia' or 'singapore').
            ethnicity: Target ethnicity ('malay', 'chinese', 'indian', 'all').
            age_group: Target age group.

        Returns:
            Dictionary containing risk level, score, explanations, and flagged issues.
        """
        start_time = time.time()
        
        try:
            # Step 1: Transcribe the spoken audio using AWS Transcribe
            logger.info(f"Extracting and transcribing audio from {video_path}...")
            transcript = self.transcriber.transcribe_media(video_path)
            logger.info(f"Transcription successful. Transcript: {transcript[:100]}...")
        except Exception as e:
            logger.error(f"Failed to transcribe video at {video_path}: {str(e)}")
            return self._error_result(video_path, market, ethnicity, age_group, f"Failed to transcribe video: {str(e)}")

        try:
            # Step 2: Attempt to load the video bytes for Gemini
            with open(video_path, "rb") as f:
                video_bytes = f.read()
            mime_type, _ = mimetypes.guess_type(video_path)
            if not mime_type:
                mime_type = "video/mp4"
        except Exception as e:
            logger.error(f"Failed to load video file at {video_path}: {str(e)}")
            return self._error_result(video_path, market, ethnicity, age_group, f"Failed to load video: {str(e)}")

        # Step 3a: Gemini pre-scan — describe the video visuals for Qdrant retrieval
        logger.info("Running Gemini pre-scan to describe video visuals...")
        visual_description = self._prescan_video(video_bytes, mime_type)
        logger.info(f"Pre-scan visual description: {visual_description}")

        # Step 3b: Combine transcript + visual description for a comprehensive query
        combined_query = f"{transcript} {visual_description}"

        # Step 3c: Embed the combined text for Qdrant vector search
        from jusads_text_compliance.embeddings import embed_text
        query_vector = embed_text(combined_query)

        # Step 3d: Retrieve regulatory and cultural rules from Qdrant
        regulatory_rules = []
        cultural_guidelines = []
        if query_vector:
            try:
                logger.info(f"Retrieving rules for market='{market}', ethnicity='{ethnicity}' based on transcript + visuals...")
                regulatory_rules = self.qdrant.get_regulatory_rules(
                    query_vector=query_vector,
                    market=market,
                )
                cultural_guidelines = self.qdrant.get_cultural_guidelines(
                    query_vector=query_vector,
                    market=market,
                    ethnicity=ethnicity,
                    age_group=age_group,
                )
            except Exception as e:
                logger.warning(f"Failed to retrieve rules from Qdrant: {e}. Proceeding without context.")
        else:
            logger.warning("Failed to generate embedding. Proceeding without Qdrant rules.")

        # Step 4: Get Persona Context
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
                        # Remove strict_taboos — handled as soft guidance in ethnicity focus
                        base_persona.pop("strict_taboos", None)
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

        # Step 5: Build Evaluation Prompt
        prompt = self._build_evaluation_prompt(
            transcript=transcript,
            regulatory_rules=regulatory_rules,
            cultural_guidelines=cultural_guidelines,
            persona_text=persona_text,
            market=market,
            ethnicity=ethnicity,
        )

        # Step 6: Evaluate with Gemini Multimodal Model
        evaluation = self._evaluate_with_llm(video_bytes, mime_type, prompt)

        # Step 7: Format result
        duration_ms = int((time.time() - start_time) * 1000)
        
        result = {
            "video_path": video_path,
            "transcript_used": transcript,
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
            "localization": evaluation.get("localization", {}),
            "persona_used": persona_text if persona_text else "No specific persona (ethnicity: all)",
            "regulatory_rules_count": len(regulatory_rules),
            "cultural_rules_count": len(cultural_guidelines),
            "processing_time_ms": duration_ms,
        }

        return result

    def _build_evaluation_prompt(
        self,
        transcript: str,
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

        prompt = f"""You are a {market.title()} Cultural Appropriateness Evaluator. Your job is to analyze the provided video advertisement along with its spoken transcript and determine whether it is culturally appropriate for a {market.title()} audience (target ethnicity: {ethnicity}).

## Accurate Transcript
The following is the highly accurate spoken transcript extracted from the video. Rely on this to analyze any spoken dialogue or claims:
"{transcript}"

REGULATORY & CULTURAL GUIDELINES (from {market.title()} Communications and Multimedia Content Code & Cultural Norms):
To inform your evaluation, consider the following rules, which provide guidance on content standards in {market.title()}.

### Regulatory Guidelines
{reg_text if reg_text else "No specific regulatory rules retrieved."}

### Cultural Guidelines
{cultural_text if cultural_text else "No specific cultural guidelines retrieved."}
{persona_section}

PRIMARY TASK:
1. Watch the video carefully, observing all visual elements (e.g., clothing modesty, physical gestures, symbols, colors, character interactions, and on-screen text).
2. Analyze the provided spoken transcript to evaluate any verbal claims or dialogue.
3. Detect elements (both visual and auditory) that may be culturally sensitive, offensive, taboo, or inappropriate for audiences in {market.title()}, paying close attention to the regulatory guidelines and persona provided above.
4. Produce ONLY a single JSON object (no extra text, no explanation outside the JSON) with the exact fields below:
   - RISK_PERCENTAGE: integer 0–100 (probability that this ad will cause cultural backlash; 0 = completely safe, 100 = certain backlash)
   - RISK_BAND: one of "Low" (0-30%), "Moderate" (31-60%), "High" (61-80%), "Critical" (81-100%)
   - CONFIDENCE: one of "high", "moderate", "low" (how confident you are in this risk assessment)
   - high_risk_indicator: array of strings. You MUST include the exact timestamp (e.g. [00:04-00:06]) at the beginning of each string to pinpoint exactly when the visual or auditory violation occurred. Example: "[00:10-00:12] Sleeveless tank top on model (Visual)". Include up to the top 10 flagged items, ranked by severity.
   - explanation: concise reasoning (max ~300 words) describing why the video has that RISK_PERCENTAGE. Reference which visual/auditory elements drove the rating and cite the provided REGULATORY GUIDELINES or PERSONA to justify your assessment (e.g., "The exposed clothing at 0:15 violates the guideline on modesty...").
   - suggestion: clear, actionable advice (max ~200 words) for how to modify or adjust the video to reduce cultural backlash risk for a {market.title()} audience (e.g., change clothing, remove or rephrase spoken lines, blur explicit elements).
   - localization: an object with specific recommendations for localizing this ad for the {ethnicity} audience in {market.title()}. Must include:
     - language: what language(s) the ad should be in (e.g. "Mandarin with English subtitles")
     - model_talent: what the talent/model should look like (ethnicity, appearance, style)
     - script_adaptation: how to adapt the script/voiceover for this audience
     - visual_style: any visual style changes needed (colors, settings, aesthetics)
     - platform: recommended platforms/channels for this audience

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
- Confidence: "high" if clear regulatory violations with strong evidence, "moderate" if cultural nuances, "low" if borderline/ambiguous

**Important:**
- Return ONLY valid JSON.
- If no issues are found, return RISK_PERCENTAGE 0, RISK_BAND "Low", CONFIDENCE "high", and empty high_risk_indicator array.
- Limit high_risk_indicator to maximum 10 items, ranked by severity (most severe first).
- You MUST provide timestamps for every issue found in high_risk_indicator. This is critical for downstream editing.

CONTEXTUAL RULES (how to treat context & intent):
- Quoted, reported, or critical context reduces severity by one level.
- Satire or parody: treat as contextual but only reduce if clear.
- If unsure about target demographic, err on the side of conservatism (raise severity).

OUTPUT FORMAT (strict):
Return exactly one JSON object and nothing else. Example structure:

{{
  "RISK_PERCENTAGE": 63,
  "RISK_BAND": "High",
  "CONFIDENCE": "moderate",
  "high_risk_indicator": [
    "[00:05-00:08] Sleeveless tank top on model (Visual)",
    "[00:12-00:15] Unsubstantiated health claim (Audio)"
  ],
  "explanation": "63% risk of cultural backlash. Short, clear reasoning (max ~300 words)...",
  "suggestion": "Concrete advice (max ~200 words)...",
  "localization": {{
    "language": "Mandarin with English subtitles for Gen Z",
    "model_talent": "Replace with Chinese Malaysian female talent, modern casual style",
    "script_adaptation": "Translate script to Mandarin, use colloquial tone, remove clinical references",
    "visual_style": "Bright, aesthetic product shots, pastel/clean tones popular on XiaoHongShu",
    "platform": "TikTok, Instagram Reels, XiaoHongShu (RED)"
  }}
}}
"""
        return prompt

    def _get_ethnicity_focus(self, ethnicity: str, market: str) -> str:
        """Return ethnicity-specific evaluation guidance.

        Focuses on what ACTUALLY matters for each audience in modern context:
        - Model/talent selection (representation)
        - Language and script choice
        - Regulatory rules (from RAG)
        - Persona-driven insights (not outdated taboos)
        - Globalized modern audience awareness
        """
        ethnicity_lower = ethnicity.lower()

        if ethnicity_lower == "chinese":
            return """
**For Malaysian Chinese audience, focus your evaluation on:**

1. **MODEL/TALENT SELECTION (HIGH PRIORITY):**
   - Are the models/actors representative of the Chinese Malaysian audience?
   - Chinese audience expects to see Chinese faces in ads targeting them
   - Mixed-race casting is acceptable but at least one Chinese talent should be featured

2. **LANGUAGE & SCRIPT (HIGH PRIORITY):**
   - Is the ad in a language the Chinese Malaysian audience connects with? (Mandarin, Cantonese, English, or a mix)
   - If the ad is purely in Malay with no Chinese language elements, flag as a localization issue
   - Code-switching (Manglish + Mandarin) is natural and preferred for younger audiences

3. **REGULATORY COMPLIANCE (from RAG rules above):**
   - Apply only the actual regulatory rules retrieved above
   - These are legal requirements, not cultural preferences

4. **CULTURAL AWARENESS (SOFT GUIDANCE — not hard rules):**
   - Number 4 in pricing/branding is worth noting but NOT a severe violation in modern context
   - Traditional taboos (clocks as gifts, white = mourning) are generational — younger audiences are less strict
   - DO NOT apply Malay Islamic modesty standards (hijab, aurat) to Chinese audience
   - Chinese Malaysians are generally more liberal about clothing/body exposure in advertising

5. **MODERN CONTEXT:**
   - Malaysian Chinese are globally connected (consume content from China, Taiwan, Korea, West)
   - They are pragmatic consumers — focus on whether the ad is effective and respectful
   - Suggestive/sexual content standards should match what's acceptable on Malaysian broadcast (MCMC rules), not religious standards
"""

        elif ethnicity_lower == "malay":
            return """
**For Malay Muslim audience, focus your evaluation on:**

1. **MODEL/TALENT SELECTION (HIGH PRIORITY):**
   - Models should represent the Malay audience appropriately
   - Female models should observe modest dressing (hijab preferred, arms/legs covered)
   - Mixed-gender interactions should be appropriate (no intimate physical contact between non-mahram)

2. **LANGUAGE & SCRIPT (HIGH PRIORITY):**
   - Bahasa Melayu is preferred; English is acceptable for urban audiences
   - Avoid crude or vulgar language even in English

3. **REGULATORY COMPLIANCE (from RAG rules above):**
   - Apply the actual regulatory rules retrieved above (these are legal requirements)
   - Halal compliance is mandatory for food/beverage/cosmetics

4. **ISLAMIC SENSITIVITY (IMPORTANT):**
   - No pork, alcohol, or non-halal references
   - Modesty in dress and behavior (aurat guidelines)
   - No suggestive/sexual content or double entendres
   - No misuse of Islamic symbols or references

5. **MODERN CONTEXT:**
   - Urban Malay millennials/Gen Z are more moderate but still value Islamic principles
   - Product application on intimate body areas should not be shown directly
   - Focus on whether content would be acceptable on Malaysian TV (MCMC broadcast standards)
"""

        elif ethnicity_lower == "indian":
            return """
**For Malaysian Indian audience, focus your evaluation on:**

1. **MODEL/TALENT SELECTION (HIGH PRIORITY):**
   - Are Indian Malaysian faces represented in the ad?
   - Indian audience expects representation — all-Chinese or all-Malay casting is a miss

2. **LANGUAGE & SCRIPT (HIGH PRIORITY):**
   - Tamil or English preferred; Malaysian English (Manglish) is natural
   - If ad is purely in Malay/Mandarin with no English/Tamil, flag as localization issue

3. **REGULATORY COMPLIANCE (from RAG rules above):**
   - Apply the actual regulatory rules retrieved above

4. **CULTURAL AWARENESS (SOFT GUIDANCE):**
   - Respect for Hindu religious symbols (don't use as commercial props)
   - Family values and respect for elders are important themes
   - Generally more liberal about clothing/body exposure than Malay audience
   - Vegetarianism is common — be sensitive with meat product ads during religious periods

5. **MODERN CONTEXT:**
   - Malaysian Indians are globally connected, consume Bollywood + Western content
   - Younger generation is progressive and values authenticity
"""

        else:
            return """
**General evaluation (no specific ethnicity):**
- Apply regulatory rules from RAG
- Focus on general Malaysian broadcast standards (MCMC)
- Consider whether content is appropriate for a diverse Malaysian audience
- Flag anything that would be offensive to ANY major ethnic group
"""

    def _prescan_video(self, video_bytes: bytes, mime_type: str) -> str:
        """Lightweight Gemini call to describe the video visuals for Qdrant retrieval."""
        try:
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(
                            text="Describe the visual content of this video advertisement in 2-3 sentences. "
                                 "Focus on: what the characters are wearing, their actions, any on-screen text, "
                                 "the setting, and any symbols or gestures. "
                                 "Do NOT evaluate or judge. Just describe factually."
                        ),
                        types.Part.from_bytes(data=video_bytes, mime_type=mime_type),
                    ],
                )
            ]
            response = client.models.generate_content(
                model="gemini-3.1-flash-lite",
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=256,
                ),
            )
            return response.text.strip()
        except Exception as e:
            logger.warning(f"Video pre-scan failed: {e}. Using transcript only for Qdrant.")
            return ""

    def _evaluate_with_llm(self, video_bytes: bytes, mime_type: str, prompt: str) -> dict[str, Any]:
        """Send the video and prompt to Gemini and parse the JSON response."""
        try:
            logger.info("Sending video and prompt to Gemini for evaluation...")
            model = "gemini-3.1-flash-lite"
            
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=prompt),
                        types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
                    ]
                )
            ]

            generate_content_config = types.GenerateContentConfig(
                temperature=0.2,
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
            logger.error(f"Gemini API error during video compliance check: {str(e)}")
            return {
                "RISK": "High",
                "SCORE": 0,
                "high_risk_indicator": ["API Error"],
                "explanation": f"Failed to evaluate video. Error: {str(e)}",
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

    def _error_result(self, video_path: str, market: str, ethnicity: str, age_group: str, error_msg: str) -> dict[str, Any]:
        """Return a structured error response matching the expected payload."""
        return {
            "video_path": video_path,
            "transcript_used": "",
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
