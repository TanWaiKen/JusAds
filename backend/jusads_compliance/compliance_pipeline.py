"""
compliance_pipeline.py
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Compliance-only LangGraph StateGraph pipeline (Pipeline 1).

Flow:
  1. fetch_rules_and_personas â†’ Queries ad_policy_rules and personas tables
  2. transcribe_media         â†’ (audio/video only) Transcribes via Gemini
  3. main_brain_analysis      â†’ Cross-references media against rules using search tools
  4. judges_agent             â†’ Bias/hallucination check (no search tools)
  5. decision_router          â†’ Three-outcome routing: pass / critical_regen / remediate

Conditional edges:
  - After fetch: audio/video â†’ transcribe_media, text/image â†’ main_brain_analysis
  - After decision_router â†’ END (pipeline NEVER invokes Remediation)

This pipeline does NOT contain any remediation or media editing logic.
"""

import json
import logging
from typing import Literal, List, Optional
from pydantic import BaseModel, Field

from langgraph.graph import StateGraph, END
from google.genai import types as genai_types

from shared.models import Compliance_State
from shared.clients import gemini, supabase
from shared.config import MODEL_TEXT
from jusads_compliance.decision_router import route_compliance_decision
from jusads_compliance.utils import parse_json_res
from jusads_compliance.progress_tracker import ProgressTracker
from shared.fallback_queue import fallback_queue
from jusads_compliance.rules_client import get_rules, get_persona
from jusads_compliance.prompts import (
    BIAS_HALLUCINATION_PROMPT,
    TEXT_COMPLIANCE_PROMPT,
    IMAGE_COMPLIANCE_PROMPT,
    AUDIO_COMPLIANCE_PROMPT,
    VIDEO_COMPLIANCE_PROMPT,
    IMAGE_PRESCAN_PROMPT,
    VIDEO_PRESCAN_PROMPT,
    UNIFIED_OUTPUT_TEMPLATE,
)

logger = logging.getLogger(__name__)

# Module-level progress tracker instance
_tracker = ProgressTracker()

# Centralised model ID — consistent across all pipeline nodes
_MODEL = MODEL_TEXT


# --- Pydantic Schemas for Structured Outputs ---

class TranscribeSchema(BaseModel):
    transcript: str = Field(description="The complete spoken transcript of the media.")
    language: str = Field(description="The language code or name detected in the speech.")

class LanguageComplianceSchema(BaseModel):
    detected_language: str = Field(description="The language detected in the ad copy or speech.")
    required_language: str = Field(description="The language required for the target audience/market/ethnicity.")
    is_compliant: bool = Field(description="Whether the detected language complies with the required language rule.")
    language_note: str = Field(description="Explanatory note regarding the language check.")

class ViolationTimelineItem(BaseModel):
    start_seconds: float = Field(description="Start time of the violation in seconds.")
    end_seconds: float = Field(description="End time of the violation in seconds.")
    type: str = Field(description="Type of violation, e.g., 'visual', 'audio', 'text'.")
    description: str = Field(description="Description of the violation.")

class ComplianceAnalysisSchema(BaseModel):
    risk_percentage: int = Field(description="Compliance risk percentage (0 to 100).")
    risk_level: str = Field(description="Risk level classification: Low, Moderate, High, or Critical.")
    compliance_verdict: str = Field(description="Verdict: accepted, needs_remediation, or rejected.")
    high_risk_indicator: List[str] = Field(default_factory=list, description="List of flagged issues or sensitive content.")
    violations_timeline: Optional[List[ViolationTimelineItem]] = Field(default=None, description="Timeline of violations (primarily for video).")
    localization_plan: str = Field(description="Actionable localization advice for the target audience/market.")
    explanation: str = Field(description="Explanation of the findings (max 300 words).")
    suggestion: str = Field(description="Actionable suggestion for fixes/remediation (max 200 words).")
    cultural_fit_score: int = Field(description="Cultural fit score (0 to 100) based on target persona.")
    language_compliance: LanguageComplianceSchema = Field(description="Language compliance details.")

class JudgesEvaluationSchema(BaseModel):
    bias_detected: bool = Field(description="Whether any bias was detected in the compliance analysis.")
    bias_issues: List[str] = Field(default_factory=list, description="List of bias issues identified, if any.")
    hallucination_score: int = Field(description="Hallucination score from 1 to 5 (1=severe hallucination, 5=fully grounded).")
    hallucinated_claims: List[str] = Field(default_factory=list, description="List of hallucinated claims, if any.")
    overall_pass: bool = Field(description="True only if bias_detected is false and hallucination_score >= 4.")
    explanation: str = Field(description="Brief explanation of the evaluation reasoning.")


# ——— Node 1: Fetch Rules and Personas —————————————————————————————————————————


def fetch_rules_and_personas(state: Compliance_State) -> dict:
    """Query ad_policy_rules and personas tables for the given market/platform/ethnicity.

    Proceeds with empty set + WARNING if no results are found.
    """
    task_id = state["task_id"]
    step_name = "fetch_rules_and_personas"
    _tracker.start_step(task_id, step_name)

    try:
        market = state["market"]
        platform = state["platform"]
        ethnicity = state["ethnicity"]
        age_group = state["age_group"]

        # Query rules
        rules = get_rules(market=market, platform=platform)
        if not rules:
            logger.warning(
                "[CompliancePipeline] No rules found for market=%s, platform=%s. "
                "Proceeding with empty rule set.",
                market, platform,
            )

        # Query personas
        persona = get_persona(market=market, ethnicity=ethnicity, age_group=age_group)
        if not persona:
            logger.warning(
                "[CompliancePipeline] No persona found for market=%s, ethnicity=%s, "
                "age_group=%s. Proceeding with empty persona.",
                market, ethnicity, age_group,
            )

        # Store in result for downstream nodes
        result = state.get("result", {}) or {}
        result["_rules"] = rules
        result["_persona"] = persona

        _tracker.complete_step(
            task_id, step_name,
            f"Fetched {len(rules)} rules, persona={'found' if persona else 'empty'}",
        )

        return {"result": result}

    except Exception as e:
        logger.error("[CompliancePipeline] fetch_rules_and_personas failed: %s", e)
        _tracker.fail_step(task_id, step_name, str(e))
        result = state.get("result", {}) or {}
        result["_rules"] = []
        result["_persona"] = {}
        return {"result": result}


# â”€â”€â”€ Node 2: Transcribe Media (audio/video only) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def transcribe_media(state: Compliance_State) -> dict:
    """Transcribe audio/video media content using Gemini.

    This node only runs for audio and video media types (conditional edge).
    """
    task_id = state["task_id"]
    step_name = "transcribe_media"
    _tracker.start_step(task_id, step_name)

    try:
        import mimetypes

        media_type = state["media_type"]
        input_path = state["input_path"]

        with open(input_path, "rb") as f:
            media_bytes = f.read()

        mime_type = mimetypes.guess_type(input_path)[0]
        if not mime_type:
            mime_type = "audio/mpeg" if media_type == "audio" else "video/mp4"

        # Use Gemini for transcription
        transcribe_prompt = (
            "Transcribe this media content. Return JSON: "
            '{"language": "detected language", "transcript": "exact transcription"}'
        )

        response = gemini.models.generate_content(
            model=_MODEL,
            contents=[genai_types.Content(role="user", parts=[
                genai_types.Part.from_bytes(data=media_bytes, mime_type=mime_type),
                genai_types.Part.from_text(text=transcribe_prompt),
            ])],
            config=genai_types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=TranscribeSchema,
            ),
        )

        transcript_data = parse_json_res(response.text)
        transcript = transcript_data.get("transcript", "")
        language = transcript_data.get("language", "unknown")

        result = state.get("result", {}) or {}
        result["_transcript"] = {"language": language, "transcript": transcript}

        _tracker.complete_step(
            task_id, step_name,
            f"Transcribed {media_type}: language={language}, length={len(transcript)} chars",
        )

        return {"result": result}

    except Exception as e:
        logger.error("[CompliancePipeline] transcribe_media failed: %s", e)
        _tracker.fail_step(task_id, step_name, str(e))
        result = state.get("result", {}) or {}
        result["_transcript"] = {"language": "unknown", "transcript": "(transcription unavailable)"}
        return {"result": result}


# â”€â”€â”€ Node 3: Main Brain Analysis â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def main_brain_analysis(state: Compliance_State) -> dict:
    """Cross-reference media content against regulatory rules using search tools.

    Uses Gemini multimodal for image/video, text prompt for text/audio.
    Injects business profile context for smart, context-aware evaluation.
    """
    task_id = state["task_id"]
    step_name = "main_brain_analysis"
    _tracker.start_step(task_id, step_name)

    try:
        import mimetypes

        media_type = state["media_type"]
        input_path = state["input_path"]
        text_input = state["text_input"]
        market = state["market"]
        platform = state["platform"]

        result = state.get("result", {}) or {}
        rules = result.get("_rules", [])
        persona = result.get("_persona", {})

        rules_text = json.dumps(rules, indent=2)
        persona_text = json.dumps(persona, indent=2)

        # Fetch business context for the user (if available)
        business_context = "No business profile available â€” evaluate conservatively."
        user_prompt_context = state.get("user_prompt_context", "")
        if user_prompt_context:
            business_context = user_prompt_context
        else:
            try:
                # Get business profile via project ownership
                check_resp = supabase.table("compliance_checks").select("project_id").eq("task_id", task_id).execute()
                if check_resp.data:
                    project_id = str(check_resp.data[0].get("project_id", ""))
                    if project_id:
                        proj_resp = supabase.table("projects").select("owner_email").eq("id", project_id).execute()
                        email = proj_resp.data[0].get("owner_email", "") if proj_resp.data else ""
                        if email:
                            profile_resp = supabase.table("business_profiles").select("*").eq("owner_email", email).execute()
                            if profile_resp.data:
                                profile = profile_resp.data[0]
                                business_context = (
                                    f"Company: {profile.get('company_name', 'Unknown')}\n"
                                    f"Product Category: {profile.get('product_category', 'Unknown')}\n"
                                    f"Description: {profile.get('product_description', 'N/A')}\n"
                                    f"Target Platforms: {', '.join(profile.get('target_platforms', []))}\n"
                                    f"Target Markets: {', '.join(profile.get('target_markets', []))}"
                                )
            except Exception as ctx_err:
                logger.warning("[CompliancePipeline] Could not fetch business context: %s", ctx_err)

        if media_type == "text":
            prompt = TEXT_COMPLIANCE_PROMPT.format(
                market=market.title(),
                platform=platform.title(),
                text=text_input,
                rules_text=rules_text,
                persona_text=persona_text,
                output_template=UNIFIED_OUTPUT_TEMPLATE,
                business_context=business_context,
            )
            response = gemini.models.generate_content(
                model=_MODEL,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ComplianceAnalysisSchema,
                ),
            )
            analysis = parse_json_res(response.text)

        elif media_type == "image":
            with open(input_path, "rb") as f:
                image_bytes = f.read()
            mime_type = mimetypes.guess_type(input_path)[0] or "image/jpeg"

            # Pre-scan: describe the image
            prescan = gemini.models.generate_content(
                model=_MODEL,
                contents=[genai_types.Content(role="user", parts=[
                    genai_types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    genai_types.Part.from_text(text=IMAGE_PRESCAN_PROMPT),
                ])],
            )

            prompt = IMAGE_COMPLIANCE_PROMPT.format(
                market=market.title(),
                platform=platform.title(),
                rules_text=rules_text,
                persona_text=persona_text,
                output_template=UNIFIED_OUTPUT_TEMPLATE,
                business_context=business_context,
            )
            response = gemini.models.generate_content(
                model=_MODEL,
                contents=[genai_types.Content(role="user", parts=[
                    genai_types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    genai_types.Part.from_text(text=prompt),
                ])],
                config=genai_types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ComplianceAnalysisSchema,
                ),
            )
            analysis = parse_json_res(response.text)

        elif media_type == "audio":
            # Audio uses the transcript from the transcribe_media node
            transcript_data = result.get("_transcript", {})
            transcript = transcript_data.get("transcript", "(no speech detected)")
            language = transcript_data.get("language", "unknown")

            with open(input_path, "rb") as f:
                audio_bytes = f.read()
            mime_type = mimetypes.guess_type(input_path)[0] or "audio/mpeg"

            prompt = AUDIO_COMPLIANCE_PROMPT.format(
                market=market.title(),
                platform=platform.title(),
                transcript=transcript,
                language=language,
                rules_text=rules_text,
                persona_text=persona_text,
                output_template=UNIFIED_OUTPUT_TEMPLATE,
                business_context=business_context,
            )
            response = gemini.models.generate_content(
                model=_MODEL,
                contents=[genai_types.Content(role="user", parts=[
                    genai_types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                    genai_types.Part.from_text(text=prompt),
                ])],
                config=genai_types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ComplianceAnalysisSchema,
                ),
            )
            analysis = parse_json_res(response.text)

        elif media_type == "video":
            # Video uses the transcript from the transcribe_media node
            with open(input_path, "rb") as f:
                video_bytes = f.read()
            mime_type = mimetypes.guess_type(input_path)[0] or "video/mp4"

            # Pre-scan: describe the video
            prescan = gemini.models.generate_content(
                model=_MODEL,
                contents=[genai_types.Content(role="user", parts=[
                    genai_types.Part.from_bytes(data=video_bytes, mime_type=mime_type),
                    genai_types.Part.from_text(text=VIDEO_PRESCAN_PROMPT),
                ])],
            )

            prompt = VIDEO_COMPLIANCE_PROMPT.format(
                market=market.title(),
                platform=platform.title(),
                rules_text=rules_text,
                persona_text=persona_text,
                output_template=UNIFIED_OUTPUT_TEMPLATE,
                business_context=business_context,
            )
            response = gemini.models.generate_content(
                model=_MODEL,
                contents=[genai_types.Content(role="user", parts=[
                    genai_types.Part.from_bytes(data=video_bytes, mime_type=mime_type),
                    genai_types.Part.from_text(text=prompt),
                ])],
                config=genai_types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ComplianceAnalysisSchema,
                ),
            )
            analysis = parse_json_res(response.text)

        else:
            analysis = {"error": f"Unknown media type: {media_type}"}

        # Merge analysis into result, preserving internal fields
        for key, value in analysis.items():
            result[key] = value

        risk = result.get("risk_percentage", 0)
        indicators = result.get("high_risk_indicator", [])

        _tracker.complete_step(
            task_id, step_name,
            f"Analysis complete â€” Risk: {risk}%, {len(indicators)} indicators found",
        )

        return {"result": result}

    except Exception as e:
        logger.error("[CompliancePipeline] main_brain_analysis failed: %s", e)
        _tracker.fail_step(task_id, step_name, str(e))
        result = state.get("result", {}) or {}
        result["error"] = str(e)
        return {"result": result}


# ─── Hallucination CSV Logger ────────────────────────────────────────────────


def _log_hallucination_to_csv(task_id: str, eval_result: dict, compliance_result: dict):
    """Log a hallucinated compliance result to a local CSV for future analysis.

    This is an improvable-product mechanism: hallucinated results are stored
    locally so the team can review and improve prompt engineering over time.
    The CSV is NOT returned to the user.
    """
    import csv
    from datetime import datetime
    from pathlib import Path

    csv_path = Path(__file__).resolve().parent.parent / "logs" / "hallucination_log.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    file_exists = csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "timestamp", "task_id", "hallucination_score",
                "bias_detected", "hallucinated_claims",
                "risk_percentage", "violations_count", "explanation",
            ])
        writer.writerow([
            datetime.utcnow().isoformat(),
            task_id,
            eval_result.get("hallucination_score", ""),
            eval_result.get("bias_detected", False),
            json.dumps(eval_result.get("hallucinated_claims", [])),
            compliance_result.get("risk_percentage", ""),
            len(compliance_result.get("high_risk_indicator", [])),
            eval_result.get("explanation", ""),
        ])


# ─── Node 4: Judges Agent ───────────────────────────────────────────────────


def judges_agent(state: Compliance_State) -> dict:
    """Enhanced judges_agent with Tavily deep research validation.

    After bias/hallucination check, validates each flagged violation against
    live regulatory sources using Tavily. Assigns confidence scores and
    attaches citation sources. Also checks rule freshness.

    Flow:
      1. Run bias/hallucination evaluation (existing)
      2. Validate flagged violations via Tavily (new)
      3. Check rule freshness against online sources (new)
      4. Search enforcement cases for high-confidence violations (new)
    """
    task_id = state["task_id"]
    step_name = "judges_agent"
    _tracker.start_step(task_id, step_name)

    try:
        result = state.get("result", {}) or {}
        rules = result.get("_rules", [])
        persona = result.get("_persona", {})

        # ── Step 1: Bias/hallucination evaluation ─────────────────────────
        prompt = BIAS_HALLUCINATION_PROMPT.format(
            context_rules=json.dumps(rules, indent=2),
            persona=json.dumps(persona, indent=2),
            compliance_result=json.dumps(
                {k: v for k, v in result.items() if not k.startswith("_")},
                indent=2,
            ),
        )

        response = gemini.models.generate_content(
            model=_MODEL,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=JudgesEvaluationSchema,
            ),
        )
        try:
            eval_result = parse_json_res(response.text)
        except Exception as parse_err:
            logger.error("[CompliancePipeline] Failed to parse judges_agent JSON. Raw text: %r", response.text)
            raise parse_err

        # Single evaluation metric: hallucination_score (1-5)
        # 1 = severe hallucination, 5 = fully grounded
        hallucination_score = eval_result.get("hallucination_score", 5)
        overall_pass = eval_result.get("overall_pass", True)

        # If hallucinated → log to local CSV, do NOT return to user
        if not overall_pass or hallucination_score < 4:
            _log_hallucination_to_csv(task_id, eval_result, result)
            logger.warning(
                "[CompliancePipeline] Hallucination detected (score=%d). "
                "Logged to CSV — result NOT returned to user.",
                hallucination_score,
            )
            result["_hallucination_flagged"] = True
        else:
            result["evaluation"] = eval_result

        # â”€â”€ Step 2: Tavily violation validation (new) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        from shared.config import TAVILY_ENABLED

        high_risk_indicators = result.get("high_risk_indicator", [])
        market = state["market"]
        platform = state["platform"]

        if TAVILY_ENABLED and high_risk_indicators:
            verification = _validate_violations_with_tavily(
                violations=high_risk_indicators,
                market=market,
                platform=platform,
                rules=rules,
                task_id=task_id,
            )
            result["verification"] = verification
        else:
            result["verification"] = {
                "violations": [],
                "stale_rules_detected": 0,
                "overall_confidence": "medium" if high_risk_indicators else "high",
                "skipped": not TAVILY_ENABLED,
            }

        _tracker.complete_step(
            task_id, step_name,
            f"Evaluation complete: pass={overall_pass}, hallucination_score={hallucination_score}, "
            f"violations_verified={len(result.get('verification', {}).get('violations', []))}",
        )

        return {"result": result}

    except Exception as e:
        logger.error("[CompliancePipeline] judges_agent failed: %s", e)
        _tracker.fail_step(task_id, step_name, str(e))
        result = state.get("result", {}) or {}
        result["_eval_error"] = str(e)
        return {"result": result}


# â”€â”€â”€ Tavily Validation Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def _validate_violations_with_tavily(
    violations: list[str],
    market: str,
    platform: str,
    rules: list[dict],
    task_id: str,
) -> dict:
    """Validate each violation against online regulatory sources via Tavily.

    For each violation:
      1. Search for the regulation online
      2. Assign confidence_score: high (found), low (not found), medium (error)
      3. Attach citation sources (URLs)
      4. Check if local rule is stale
      5. If high confidence, search for enforcement cases

    Args:
        violations: List of high_risk_indicator strings.
        market: Target market (e.g. 'malaysia').
        platform: Target platform (e.g. 'tiktok').
        rules: Local rules used in the current evaluation.
        task_id: The compliance task_id for audit logging.

    Returns:
        Verification dict with validated violations and metadata.
    """
    from shared.tavily_guard import tavily_compliance_search

    validated_violations = []
    stale_rules_count = 0

    # Validate max 5 violations to control cost
    for violation_text in violations[:5]:
        # Search for the regulation
        query = f"{market} {platform} advertising regulation: {violation_text}"
        tavily_result = tavily_compliance_search(query=query, task_id=task_id)

        results = tavily_result.get("results", [])

        if results:
            # Sources found â€” high confidence
            citation_sources = [r.get("url", "") for r in results if r.get("url")][:5]
            confidence_score = "high"

            # Check rule freshness
            rule_freshness = _check_rule_freshness(
                violation_text=violation_text,
                rules=rules,
                tavily_results=results,
            )
            if rule_freshness.get("is_stale"):
                stale_rules_count += 1

            # Search enforcement cases for high-confidence violations
            enforcement_cases = _search_enforcement_cases(
                violation_type=violation_text,
                market=market,
                task_id=task_id,
            )
        else:
            # No sources found â€” low confidence
            citation_sources = []
            confidence_score = "low"
            rule_freshness = {"is_stale": False, "updated_url": None, "change_summary": None}
            enforcement_cases = []

        validated_violations.append({
            "violation_text": violation_text,
            "confidence_score": confidence_score,
            "citation_sources": citation_sources,
            "enforcement_cases": enforcement_cases,
            "rule_freshness": rule_freshness,
        })

    # Compute overall confidence
    if not validated_violations:
        overall_confidence = "high"
    else:
        confidence_counts = {"high": 0, "medium": 0, "low": 0}
        for v in validated_violations:
            confidence_counts[v["confidence_score"]] = confidence_counts.get(v["confidence_score"], 0) + 1

        if confidence_counts["high"] >= len(validated_violations) * 0.6:
            overall_confidence = "high"
        elif confidence_counts["low"] >= len(validated_violations) * 0.5:
            overall_confidence = "low"
        else:
            overall_confidence = "medium"

    return {
        "violations": validated_violations,
        "stale_rules_detected": stale_rules_count,
        "overall_confidence": overall_confidence,
    }


def _check_rule_freshness(
    violation_text: str,
    rules: list[dict],
    tavily_results: list[dict],
) -> dict:
    """Compare local rule version against online source found by Tavily.

    Checks if any online source mentions a more recent regulation date
    or explicitly states the old regulation is superseded.

    Args:
        violation_text: The violation being validated.
        rules: Local rules from Supabase.
        tavily_results: Tavily search results for this violation.

    Returns:
        Dict with is_stale, updated_url, change_summary.
    """
    # Find the matching local rule (by keyword overlap)
    matching_rule = None
    violation_lower = violation_text.lower()
    for rule in rules:
        rule_text = (rule.get("rule_text", "") + " " + rule.get("rule_title", "")).lower()
        # Simple keyword overlap check
        overlap = sum(1 for word in violation_lower.split() if word in rule_text and len(word) > 3)
        if overlap >= 2:
            matching_rule = rule
            break

    if not matching_rule:
        return {"is_stale": False, "updated_url": None, "change_summary": None}

    local_last_updated = matching_rule.get("last_updated", "")

    # Check if any Tavily result mentions a newer date or amendment
    for tr in tavily_results[:3]:
        content = (tr.get("content", "") + " " + tr.get("title", "")).lower()
        # Look for amendment/update signals
        stale_signals = ["amended", "superseded", "replaced by", "new regulation", "updated", "revision"]
        if any(signal in content for signal in stale_signals):
            return {
                "is_stale": True,
                "updated_url": tr.get("url", ""),
                "change_summary": f"Online source indicates regulation may have been updated. Local rule last_updated: {local_last_updated}",
            }

    return {"is_stale": False, "updated_url": None, "change_summary": None}


def _search_enforcement_cases(
    violation_type: str,
    market: str,
    task_id: str,
) -> list[dict]:
    """Search for enforcement cases related to a violation type.

    Only called for violations with confidence_score "high".
    Returns up to 3 case references with title and URL.

    Args:
        violation_type: The violation description.
        market: Target market.
        task_id: Task ID for Tavily logging.

    Returns:
        List of up to 3 dicts with 'title' and 'url' keys.
    """
    from shared.tavily_guard import tavily_compliance_search

    query = f"{market} advertising enforcement action penalty case: {violation_type}"
    result = tavily_compliance_search(
        query=query,
        task_id=task_id,
        max_results=3,
        search_depth="basic",
    )

    cases = []
    for r in result.get("results", [])[:3]:
        title = r.get("title", "")
        url = r.get("url", "")
        if title and url:
            cases.append({"title": title, "url": url})

    return cases


# â”€â”€â”€ Node 5: Decision Router â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def decision_router_node(state: Compliance_State) -> dict:
    """Wraps route_compliance_decision and sets state status.

    Also persists the compliance result to the compliance_checks table.
    On persistence failure, queues in FallbackQueue.
    """
    task_id = state["task_id"]
    step_name = "decision_router"
    _tracker.start_step(task_id, step_name)

    try:
        result = state.get("result", {}) or {}

        risk_level = result.get("risk_level", "Low")
        risk_percentage = result.get("risk_percentage", 0)
        high_risk_indicators = result.get("high_risk_indicator", [])

        # Route the decision
        decision = route_compliance_decision(
            risk_level=risk_level,
            risk_percentage=risk_percentage,
            high_risk_indicators=high_risk_indicators,
        )

        # Map decision to human-readable verdict
        verdict_map = {
            "pass": "accepted",
            "remediate": "needs_remediation",
            "critical_regen": "rejected",
        }
        result["compliance_verdict"] = verdict_map.get(decision, "needs_remediation")

        # Clean internal fields from result before persisting
        persist_result = {k: v for k, v in result.items() if not k.startswith("_")}

        # Persist compliance result to compliance_checks table
        _persist_compliance_result(task_id, decision, risk_percentage, persist_result)

        _tracker.complete_step(
            task_id, step_name,
            f"Decision: {decision} (risk_level={risk_level}, risk_percentage={risk_percentage})",
        )

        return {"status": decision, "result": result}

    except Exception as e:
        logger.error("[CompliancePipeline] decision_router_node failed: %s", e)
        _tracker.fail_step(task_id, step_name, str(e))
        return {"status": "remediate"}


# â”€â”€â”€ Persistence Helper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def _persist_compliance_result(
    task_id: str,
    status: str,
    risk_percentage: int,
    result_json: dict,
) -> None:
    """Persist compliance result to the compliance_checks table.

    On failure, queues the operation in FallbackQueue for deferred retry.
    """
    try:
        from datetime import datetime, timezone

        supabase.table("compliance_checks").update({
            "status": status,
            "risk_percentage": risk_percentage,
            "result_json": result_json,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("task_id", task_id).execute()

        logger.info("[CompliancePipeline] Persisted result for task_id=%s, status=%s", task_id, status)

    except Exception as e:
        logger.error(
            "[CompliancePipeline] Failed to persist result for task_id=%s: %s. "
            "Queuing in FallbackQueue.",
            task_id, e,
        )
        fallback_queue.enqueue(
            table="compliance_checks",
            operation="update",
            payload={
                "task_id": task_id,
                "status": status,
                "risk_percentage": risk_percentage,
                "result_json": result_json,
            },
        )


# â”€â”€â”€ Conditional Edge: Route after fetch_rules_and_personas â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def _route_after_fetch(state: Compliance_State) -> Literal["transcribe_media", "main_brain_analysis"]:
    """Route based on media type: audio/video â†’ transcribe, text/image â†’ main_brain."""
    media_type = state["media_type"]
    if media_type in ("audio", "video"):
        return "transcribe_media"
    return "main_brain_analysis"


# â”€â”€â”€ Build the Compliance Pipeline â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


_graph = StateGraph(Compliance_State)

# Add nodes
_graph.add_node("fetch_rules_and_personas", fetch_rules_and_personas)
_graph.add_node("transcribe_media", transcribe_media)
_graph.add_node("main_brain_analysis", main_brain_analysis)
_graph.add_node("judges_agent", judges_agent)
_graph.add_node("decision_router", decision_router_node)

# Set entry point
_graph.set_entry_point("fetch_rules_and_personas")

# Conditional edge: after fetch â†’ transcribe (audio/video) or main_brain (text/image)
_graph.add_conditional_edges("fetch_rules_and_personas", _route_after_fetch, {
    "transcribe_media": "transcribe_media",
    "main_brain_analysis": "main_brain_analysis",
})

# transcribe_media â†’ main_brain_analysis
_graph.add_edge("transcribe_media", "main_brain_analysis")

# main_brain_analysis â†’ judges_agent
_graph.add_edge("main_brain_analysis", "judges_agent")

# judges_agent â†’ decision_router
_graph.add_edge("judges_agent", "decision_router")

# decision_router â†’ END (pipeline NEVER invokes Remediation)
_graph.add_edge("decision_router", END)

# Compile and export
compliance_pipeline = _graph.compile()
