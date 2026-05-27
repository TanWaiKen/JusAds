"""Step 6: Compliance evaluation node for the content compliance pipeline.

Invokes Google Gemini LLM with unified content and retrieved guidelines to
produce a structured compliance evaluation. Constructs a market-specific
prompt requesting JSON output with risk level, score, high_risk_indicators
(with localization), explanation, and suggestion.
"""

import json
import logging
import re
import time
from typing import Optional

from ..config import LLM_MODEL_ID
from ..models.schemas import Market, PipelineState
from ..scoring import get_scoring_config
from ..gemini_client import generate_text

logger = logging.getLogger(__name__)



def _parse_llm_json(raw: str) -> Optional[dict]:
    """Parse LLM output as JSON, handling markdown code blocks.

    Attempts direct JSON parsing first, then falls back to extracting
    a JSON object from surrounding text (e.g., markdown code fences).

    Args:
        raw: Raw text output from the LLM.

    Returns:
        Parsed dict if successful, None if parsing fails.
    """
    if not raw or not raw.strip():
        return None

    text = raw.strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code block
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding any JSON object in the text
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None


def _build_scoring_instructions(market: Market) -> str:
    """Build market-specific scoring category instructions.

    Args:
        market: The target regulatory market.

    Returns:
        A formatted string describing the scoring categories and weights.
    """
    scoring_config = get_scoring_config(market)
    categories_text = "\n".join(
        f"- {cat.name}: weight {cat.weight}" for cat in scoring_config
    )
    return categories_text


def _build_prompt(
    content: str,
    content_type: str,
    market: str,
    ethnicity: str = "all",
    age_group: str = "all_ages",
    regulatory_guidelines: Optional[str] = None,
    cultural_guidelines: Optional[str] = None,
    guidelines: Optional[str] = None,
) -> str:
    """Construct the compliance evaluation prompt.

    Builds a prompt that includes the unified content, retrieved guidelines
    (split into clearly labeled regulatory and cultural sections), market-specific
    scoring categories, and instructions for structured JSON output with localized
    issue indicators and guideline source tagging.

    Args:
        content: The unified content to evaluate.
        content_type: The type of content ("text", "image", "video").
        market: The target market ("malaysia", "singapore").
        regulatory_guidelines: Formatted regulatory guidelines string (from step5).
        cultural_guidelines: Formatted cultural guidelines string (from step5).
        guidelines: Fallback combined guidelines string (used when separate
            regulatory/cultural strings are not available).

    Returns:
        The complete prompt string for LLM invocation.
    """
    # Resolve market for scoring config
    try:
        market_enum = Market(market.lower())
    except (ValueError, AttributeError):
        market_enum = Market.MALAYSIA

    scoring_categories = _build_scoring_instructions(market_enum)
    market_name = market.title() if market else "Malaysia"

    # Build the guidelines section with clearly labeled regulatory and cultural parts
    if regulatory_guidelines is not None or cultural_guidelines is not None:
        # Use separate labeled sections when available (preferred path from step5)
        reg_section = regulatory_guidelines or "No relevant regulatory guidelines found."
        cult_section = cultural_guidelines or "No relevant cultural guidelines found."
        guidelines_section = (
            "=== REGULATORY GUIDELINES ===\n\n"
            f"{reg_section}\n\n"
            "=== CULTURAL GUIDELINES ===\n\n"
            f"{cult_section}"
        )
    else:
        # Fallback: use the combined guidelines string as-is
        guidelines_section = guidelines or "No guidelines available."

    # Build localization instructions based on content type
    if content_type == "text":
        localization_instructions = (
            "For each high_risk_indicator, provide:\n"
            '- "phrase": the exact verbatim problematic substring '
            "from the input (max 200 chars)\n"
            '- "char_offset": 0-based character offset of the phrase '
            "in the original text\n"
            '- "category": one of the scoring categories listed above\n'
            '- "severity": one of "Severe", "Moderate", "Minor"\n'
            '- "guideline_source": "regulatory" if the violation comes from a '
            'regulatory guideline, "cultural" if it comes from a cultural guideline'
        )
    elif content_type == "image":
        localization_instructions = (
            "For each high_risk_indicator, provide:\n"
            '- "bounding_box": {"x": %, "y": %, "width": %, "height": %} '
            "as percentage (0-100) of image dimensions\n"
            '- "description": description of the flagged visual element '
            "(max 200 chars)\n"
            '- "category": one of the scoring categories listed above\n'
            '- "severity": one of "Severe", "Moderate", "Minor"\n'
            '- "guideline_source": "regulatory" if the violation comes from a '
            'regulatory guideline, "cultural" if it comes from a cultural guideline'
        )
    else:  # video
        localization_instructions = (
            "For each high_risk_indicator, provide:\n"
            '- "timestamp": in "MM:SS" format '
            '(or "HH:MM:SS" for videos >= 60 min)\n'
            '- "description": description of what is happening at that '
            "moment (max 200 chars)\n"
            '- "category": one of the scoring categories listed above\n'
            '- "severity": one of "Severe", "Moderate", "Minor"\n'
            '- "guideline_source": "regulatory" if the violation comes from a '
            'regulatory guideline, "cultural" if it comes from a cultural guideline'
        )

    prompt = f"""\
You are a {market_name} Cultural Appropriateness Evaluator. Your job is to evaluate \
content against both regulatory guidelines and cultural guidelines, and produce a \
structured compliance assessment.

CONTENT TYPE: {content_type}
TARGET MARKET: {market_name}
TARGET ETHNICITY: {ethnicity.upper()}
TARGET AGE GROUP: {age_group.upper()}

INPUT CONTENT:
{content}

GUIDELINES:
{guidelines_section}

INSTRUCTIONS:
1. Compare the 'INPUT CONTENT' strictly against the 'GUIDELINES'.
2. Pay extremely close attention to the 'VISUAL AUDIT TAGS' in the input content. If a detected visual element (e.g., specific body exposure, food, or gesture) contradicts a retrieved cultural or regulatory guideline, you MUST flag it as a violation.
3. Do not use outside knowledge; base your violations solely on the provided guidelines.

CULTURAL SEVERITY MAPPING:
When a violation is detected from a CULTURAL GUIDELINE, map the cultural severity to \
compliance severity as follows:
- Cultural severity "high"   -> Compliance severity "Severe"
- Cultural severity "medium" -> Compliance severity "Moderate"
- Cultural severity "low"    -> Compliance severity "Minor"

SCORING CATEGORIES AND WEIGHTS:
{scoring_categories}

SCORING METHOD:
Start from 100 points. For each category, apply severity penalties:
- No issues = 0 penalty
- Minor = 0.25 x weight
- Moderate = 0.6 x weight
- Severe = 1.0 x weight
SCORE = max(0, round(100 - total_penalty))
Apply this formula equally to both regulatory and cultural violations.

RISK LEVEL MAPPING:
- SCORE >= 75 -> "Low"
- 40 <= SCORE < 75 -> "Medium"
- SCORE < 40 -> "High"

ISSUE LOCALIZATION:
{localization_instructions}

OUTPUT FORMAT:
Produce ONLY a single JSON object (no extra text, no explanation outside the JSON) \
with these exact fields:
{{
  "risk_level": "High" | "Medium" | "Low",
  "score": integer 0-100,
  "high_risk_indicators": [array of up to 10 localized issue objects, ranked by severity \
(Severe first, then Moderate, then Minor)],
  "explanation": "concise reasoning (max 500 characters)",
  "suggestion": "clear, actionable advice (max 400 characters)"
}}

RULES:
- Return ONLY valid JSON, no markdown code fences, no extra text.
- If no issues are found, return score 100, risk_level "Low", and empty \
high_risk_indicators array.
- Limit high_risk_indicators to maximum 10 items, ranked by severity (most severe first).
- Each high_risk_indicator MUST include a "guideline_source" field set to "regulatory" \
or "cultural" based on which section the violated guideline came from.
- Violations from the REGULATORY GUIDELINES section must have guideline_source "regulatory".
- Violations from the CULTURAL GUIDELINES section must have guideline_source "cultural".
- Ensure explanation is at most 500 characters and suggestion is at most 400 characters.
"""
    return prompt


def compliance_evaluation(state: PipelineState) -> PipelineState:
    """Invoke LLM for compliance scoring with localized issue detection.

    Constructs a market-specific prompt with the unified content and retrieved
    guidelines (both regulatory and cultural), invokes AWS Bedrock (Claude/Nova
    model) via the Converse API, and parses the structured JSON response.

    The prompt presents guidelines in two clearly labeled sections:
    "=== REGULATORY GUIDELINES ===" and "=== CULTURAL GUIDELINES ===".
    The LLM is instructed to tag each violation with a guideline_source field
    ("regulatory" or "cultural") and to apply the cultural severity mapping
    (high→Severe, medium→Moderate, low→Minor).

    The raw LLM output is stored in state.raw_llm_output. The model ID is
    tracked in state.models_used. Response time is logged in milliseconds.

    Args:
        state: The current pipeline state. Expects:
            - state.unified_content: Combined content for evaluation
            - state.regulatory_guidelines: Formatted regulatory guidelines (from step5)
            - state.cultural_guidelines: Formatted cultural guidelines (from step5)
            - state.retrieved_guidelines: Fallback combined guidelines string
            - state.market: Target market for scoring configuration
            - state.content_type: Content type for localization format

    Returns:
        Updated PipelineState with raw_llm_output set, or with an error
        appended if the LLM invocation or response parsing fails.
    """
    # Validate prerequisites
    if not state.unified_content:
        state.errors.append({
            "node": "compliance_evaluation",
            "error_type": "validation",
            "message": (
                "No unified content available for compliance evaluation. "
                "Ensure content processing ran before evaluation."
            ),
        })
        return state

    # Check that at least some guidelines are available (separate or combined)
    has_separate_guidelines = (
        state.regulatory_guidelines is not None
        or state.cultural_guidelines is not None
    )
    if not has_separate_guidelines and not state.retrieved_guidelines:
        state.errors.append({
            "node": "compliance_evaluation",
            "error_type": "validation",
            "message": (
                "No guidelines available for compliance evaluation. "
                "Ensure guideline retrieval ran before evaluation."
            ),
        })
        return state

    # Build the evaluation prompt.
    # Prefer separate regulatory/cultural strings (set by step5) for clearly
    # labeled sections. Fall back to the combined retrieved_guidelines string
    # when the separate fields are not available (e.g., legacy state).
    if has_separate_guidelines:
        prompt = _build_prompt(
            content=state.unified_content,
            content_type=state.content_type.value,
            market=state.market.value,
            ethnicity=state.target_ethnicity,
            age_group=state.target_age_group,
            regulatory_guidelines=state.regulatory_guidelines,
            cultural_guidelines=state.cultural_guidelines,
        )
    else:
        prompt = _build_prompt(
            content=state.unified_content,
            content_type=state.content_type.value,
            market=state.market.value,
            ethnicity=state.target_ethnicity,
            age_group=state.target_age_group,
            guidelines=state.retrieved_guidelines,
        )

    model_id = LLM_MODEL_ID

    logger.info(
        "Invoking Gemini LLM model '%s' for compliance evaluation", model_id
    )

    # Invoke Gemini LLM and track response time
    start_time_ms = time.time() * 1000

    try:
        raw_text = generate_text(
            prompt=prompt,
            model=model_id,
            json_mode=True,
        )

        # Calculate response time
        end_time_ms = time.time() * 1000
        response_time_ms = int(end_time_ms - start_time_ms)

        logger.info(
            "Gemini LLM '%s' responded in %d ms",
            model_id,
            response_time_ms,
        )

    except Exception as e:
        end_time_ms = time.time() * 1000
        response_time_ms = int(end_time_ms - start_time_ms)

        logger.error(
            "Gemini LLM invocation failed after %d ms: %s",
            response_time_ms,
            str(e),
        )
        state.errors.append({
            "node": "compliance_evaluation",
            "error_type": "service_unavailable",
            "message": f"LLM invocation failed: {str(e)}",
        })
        # Track model even on failure for metadata
        if model_id not in state.models_used:
            state.models_used.append(model_id)
        return state

    # Track model usage
    if model_id not in state.models_used:
        state.models_used.append(model_id)

    # Parse the LLM response as JSON
    parsed_output = _parse_llm_json(raw_text)
    if parsed_output is None:
        logger.error(
            "Failed to parse LLM response as JSON: %s", raw_text[:200]
        )
        state.errors.append({
            "node": "compliance_evaluation",
            "error_type": "parse_error",
            "message": (
                "LLM returned unparseable response. "
                "Could not extract valid JSON from the output."
            ),
        })
        return state

    # Store raw LLM output in state
    state.raw_llm_output = parsed_output

    logger.info(
        "Compliance evaluation complete: risk_level=%s, score=%s",
        parsed_output.get("risk_level", "unknown"),
        parsed_output.get("score", "unknown"),
    )

    return state
