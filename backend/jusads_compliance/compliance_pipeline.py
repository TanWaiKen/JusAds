"""
compliance_pipeline.py
──────────────────────
Compliance-only LangGraph StateGraph pipeline (Pipeline 1).

Flow:
  1. fetch_rules_and_personas â†’ Queries ad_policy_rules and personas tables
  2. transcribe_media         â†’ (audio/video only) Transcribes via Gemini
  3. main_brain_analysis      â†’ Gemini performs an initial multimodal assessment
  4. legal_research_agent     â†’ Google grounding, with Tavily as the audited fallback
  5. grounded_compliance_agentâ†’ Reconciles findings with live regulatory evidence
  6. media_evidence_agent     â†’ Produces text, image, video, or audio evidence for the UI
  7. decision_router          â†’ Three-outcome routing: pass / critical_regen / remediate

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
from langgraph.checkpoint.memory import MemorySaver
from google.genai import types as genai_types

from shared.models import Compliance_State
from shared.clients import gemini, supabase
from shared.config import MODEL_TEXT
from jusads_compliance.decision_router import route_compliance_decision
from jusads_compliance.utils import parse_json_res
from jusads_compliance.progress_tracker import ProgressTracker
from shared.fallback_queue import fallback_queue
from jusads_compliance.rules_client import get_rules, get_persona
from jusads_compliance.agents.evidence import media_evidence_agent
from jusads_compliance.agents.research import grounded_compliance_agent, legal_research_agent
from jusads_compliance.prompts import (
    TEXT_COMPLIANCE_PROMPT,
    IMAGE_COMPLIANCE_PROMPT,
    AUDIO_COMPLIANCE_PROMPT,
    VIDEO_COMPLIANCE_PROMPT,
    IMAGE_PRESCAN_PROMPT,
    VIDEO_PRESCAN_PROMPT,
    UNIFIED_OUTPUT_TEMPLATE,
    CONTEXT_FRAMEWORK,
)

logger = logging.getLogger(__name__)

# Module-level progress tracker instance
_tracker = ProgressTracker()

# Centralised model ID — consistent across all pipeline nodes
_MODEL = MODEL_TEXT


# --- Pydantic Schemas for Structured Outputs ---

class TranscriptSegment(BaseModel):
    start_seconds: float = Field(description="Start timestamp of this spoken segment.")
    end_seconds: float = Field(description="End timestamp of this spoken segment.")
    text: str = Field(description="Verbatim transcript for this time range.")


class TranscribeSchema(BaseModel):
    transcript: str = Field(description="The complete spoken transcript of the media.")
    language: str = Field(description="The language code or name detected in the speech.")
    segments: List[TranscriptSegment] = Field(default_factory=list, description="Timestamped spoken segments.")

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

class ImageCopyAction(BaseModel):
    original: str = Field(default="", description="Legible source copy, if any.")
    replacement: str = Field(default="", description="Compliance-safe promotional rewrite, if needed.")
    language: str = Field(default="needs confirmation", description="Language selected for the replacement copy.")
    reason: str = Field(default="", description="Why the copy needs review or replacement.")

class ImageReviewSchema(BaseModel):
    copy_actions: List[ImageCopyAction] = Field(default_factory=list)
    character_assessment: str = Field(default="")
    claims_requiring_evidence: List[str] = Field(default_factory=list)
    sensitive_content: List[str] = Field(default_factory=list)

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
    image_review: Optional[ImageReviewSchema] = Field(default=None, description="Image-specific copy, representation, claim and sensitive-content review.")

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


# ─── Node 2: Transcribe Media (audio/video only) ─────────────────────────────


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
            "Transcribe this media exactly. Return the detected language, full transcript, "
            "and ordered timestamped segments covering each spoken phrase."
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
        result["_transcript"] = {
            "language": language,
            "transcript": transcript,
            "segments": transcript_data.get("segments", []),
        }

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


# ─── Node 3: Main Brain Analysis ─────────────────────────────────────────────


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
                context_framework=CONTEXT_FRAMEWORK,
                research_context="No live regulatory research available for the initial pass.",
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
                image_description=prescan.text.strip(),
                business_context=business_context,
                context_framework=CONTEXT_FRAMEWORK,
                research_context="No live regulatory research available for the initial pass.",
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
                context_framework=CONTEXT_FRAMEWORK,
                research_context="No live regulatory research available for the initial pass.",
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
                context_framework=CONTEXT_FRAMEWORK,
                research_context="No live regulatory research available for the initial pass.",
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

        # ── Step 2: Tavily violation validation (new) ─────────────────────
        from shared.config import TAVILY_ENABLED

        high_risk_indicators = result.get("high_risk_indicator", [])
        
        # Use research data gathered by legal_research_agent
        research_context = result.get("_research_context", "")
        research_sources = result.get("_research_sources", [])
        
        if TAVILY_ENABLED and research_sources:
            # We have research data - use it for verification
            result["verification"] = {
                "research_report": research_context,  # Full research explanation
                "sources": research_sources,  # List of source objects with url/title/snippet
                "citation_urls": [s.get("url") for s in research_sources if s.get("url")],
                "overall_confidence": "high" if len(research_sources) >= 3 else "medium",
                "violations_checked": len(high_risk_indicators),
                "sources_count": len(research_sources),
            }
            logger.info(
                "[CompliancePipeline] Verification built from research: %d sources, %d violations checked",
                len(research_sources), len(high_risk_indicators)
            )
        else:
            # No research data available
            result["verification"] = {
                "research_report": "No regulatory research available for this content.",
                "sources": [],
                "citation_urls": [],
                "overall_confidence": "low",
                "violations_checked": len(high_risk_indicators),
                "sources_count": 0,
                "skipped": not TAVILY_ENABLED,
            }

        _tracker.complete_step(
            task_id, step_name,
            f"Evaluation complete: pass={overall_pass}, hallucination_score={hallucination_score}, "
            f"verification_sources={len(result.get('verification', {}).get('sources', []))}",
        )

        return {"result": result}

    except Exception as e:
        logger.error("[CompliancePipeline] judges_agent failed: %s", e)
        _tracker.fail_step(task_id, step_name, str(e))
        result = state.get("result", {}) or {}
        result["_eval_error"] = str(e)
        return {"result": result}


# --- Node 5: Decision Router ---


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

        # A failed analysis has no valid risk assessment. Do not route or
        # persist it as a compliance verdict; the SSE route returns its error.
        if result.get("error"):
            _tracker.fail_step(task_id, step_name, str(result["error"]))
            return {"status": "failed", "result": result}

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


# ─── Persistence Helper ──────────────────────────────────────────────────────


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


# ─── Conditional Edge: Route after fetch_rules_and_personas ───────────────────


def _route_after_fetch(state: Compliance_State) -> Literal["transcribe_media", "main_brain_analysis"]:
    """Route based on media type: audio/video â†’ transcribe, text/image â†’ main_brain."""
    media_type = state["media_type"]
    if media_type in ("audio", "video"):
        return "transcribe_media"
    return "main_brain_analysis"


# ─── Build the Compliance Pipeline ───────────────────────────────────────────


_graph = StateGraph(Compliance_State)

# Add nodes
_graph.add_node("fetch_rules_and_personas", fetch_rules_and_personas)
_graph.add_node("transcribe_media", transcribe_media)
_graph.add_node("main_brain_analysis", main_brain_analysis)
_graph.add_node("legal_research_agent", legal_research_agent)
_graph.add_node("grounded_compliance_agent", grounded_compliance_agent)
_graph.add_node("media_evidence_agent", media_evidence_agent)
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

# Initial findings â†’ live regulatory research â†’ grounded adjudication â†’ UI evidence
_graph.add_edge("main_brain_analysis", "legal_research_agent")
_graph.add_edge("legal_research_agent", "grounded_compliance_agent")
_graph.add_edge("grounded_compliance_agent", "media_evidence_agent")
_graph.add_edge("media_evidence_agent", "decision_router")

# decision_router â†’ END (pipeline NEVER invokes Remediation)
_graph.add_edge("decision_router", END)

# A checkpointer enables LangGraph task-start/task-finish stream events, which
# the compliance SSE endpoint uses for real-time progress notifications.
compliance_pipeline = _graph.compile(checkpointer=MemorySaver())
