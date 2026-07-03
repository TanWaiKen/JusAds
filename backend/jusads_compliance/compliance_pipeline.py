"""
compliance_pipeline.py
──────────────────────
Compliance-only LangGraph StateGraph pipeline (Pipeline 1).

Flow:
  1. fetch_rules_and_personas → Queries ad_policy_rules and personas tables
  2. transcribe_media         → (audio/video only) Transcribes via Gemini
  3. main_brain_analysis      → Cross-references media against rules using search tools
  4. judges_agent             → Bias/hallucination check (no search tools)
  5. decision_router          → Three-outcome routing: pass / critical_regen / remediate

Conditional edges:
  - After fetch: audio/video → transcribe_media, text/image → main_brain_analysis
  - After decision_router → END (pipeline NEVER invokes Remediation)

This pipeline does NOT contain any remediation or media editing logic.
"""

import json
import logging
from typing import Literal

from langgraph.graph import StateGraph, END
from google.genai import types as genai_types

from shared.models import Compliance_State
from shared.clients import gemini, supabase
from jusads_compliance.decision_router import route_compliance_decision
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


# ─── Node 1: Fetch Rules and Personas ────────────────────────────────────────


def fetch_rules_and_personas(state: Compliance_State) -> dict:
    """Query ad_policy_rules and personas tables for the given market/platform/ethnicity.

    Proceeds with empty set + WARNING if no results are found.
    """
    check_id = state["check_id"]
    step_name = "fetch_rules_and_personas"
    _tracker.start_step(check_id, step_name)

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
            check_id, step_name,
            f"Fetched {len(rules)} rules, persona={'found' if persona else 'empty'}",
        )

        return {"result": result}

    except Exception as e:
        logger.error("[CompliancePipeline] fetch_rules_and_personas failed: %s", e)
        _tracker.fail_step(check_id, step_name, str(e))
        result = state.get("result", {}) or {}
        result["_rules"] = []
        result["_persona"] = {}
        return {"result": result}


# ─── Node 2: Transcribe Media (audio/video only) ─────────────────────────────


def transcribe_media(state: Compliance_State) -> dict:
    """Transcribe audio/video media content using Gemini.

    This node only runs for audio and video media types (conditional edge).
    """
    check_id = state["check_id"]
    step_name = "transcribe_media"
    _tracker.start_step(check_id, step_name)

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
            model="gemini-2.5-flash",
            contents=[genai_types.Content(role="user", parts=[
                genai_types.Part.from_bytes(data=media_bytes, mime_type=mime_type),
                genai_types.Part.from_text(text=transcribe_prompt),
            ])],
            config=genai_types.GenerateContentConfig(response_mime_type="application/json"),
        )

        transcript_data = json.loads(response.text)
        transcript = transcript_data.get("transcript", "")
        language = transcript_data.get("language", "unknown")

        result = state.get("result", {}) or {}
        result["_transcript"] = {"language": language, "transcript": transcript}

        _tracker.complete_step(
            check_id, step_name,
            f"Transcribed {media_type}: language={language}, length={len(transcript)} chars",
        )

        return {"result": result}

    except Exception as e:
        logger.error("[CompliancePipeline] transcribe_media failed: %s", e)
        _tracker.fail_step(check_id, step_name, str(e))
        result = state.get("result", {}) or {}
        result["_transcript"] = {"language": "unknown", "transcript": "(transcription unavailable)"}
        return {"result": result}


# ─── Node 3: Main Brain Analysis ─────────────────────────────────────────────


def main_brain_analysis(state: Compliance_State) -> dict:
    """Cross-reference media content against regulatory rules using search tools.

    Uses Gemini multimodal for image/video, text prompt for text/audio.
    Injects business profile context for smart, context-aware evaluation.
    """
    check_id = state["check_id"]
    step_name = "main_brain_analysis"
    _tracker.start_step(check_id, step_name)

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
        business_context = "No business profile available — evaluate conservatively."
        user_prompt_context = state.get("user_prompt_context", "")
        if user_prompt_context:
            business_context = user_prompt_context
        else:
            try:
                # Try to get business profile from session or check record
                check_resp = supabase.table("compliance_checks").select("user_email").eq("check_id", check_id).execute()
                if check_resp.data:
                    email = check_resp.data[0].get("user_email", "")
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
                model="gemini-2.5-flash",
                contents=prompt,
                config=genai_types.GenerateContentConfig(response_mime_type="application/json"),
            )
            analysis = json.loads(response.text)

        elif media_type == "image":
            with open(input_path, "rb") as f:
                image_bytes = f.read()
            mime_type = mimetypes.guess_type(input_path)[0] or "image/jpeg"

            # Pre-scan: describe the image
            prescan = gemini.models.generate_content(
                model="gemini-2.5-flash",
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
                model="gemini-2.5-flash",
                contents=[genai_types.Content(role="user", parts=[
                    genai_types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    genai_types.Part.from_text(text=prompt),
                ])],
                config=genai_types.GenerateContentConfig(response_mime_type="application/json"),
            )
            analysis = json.loads(response.text)

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
                model="gemini-2.5-flash",
                contents=[genai_types.Content(role="user", parts=[
                    genai_types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                    genai_types.Part.from_text(text=prompt),
                ])],
                config=genai_types.GenerateContentConfig(response_mime_type="application/json"),
            )
            analysis = json.loads(response.text)

        elif media_type == "video":
            # Video uses the transcript from the transcribe_media node
            with open(input_path, "rb") as f:
                video_bytes = f.read()
            mime_type = mimetypes.guess_type(input_path)[0] or "video/mp4"

            # Pre-scan: describe the video
            prescan = gemini.models.generate_content(
                model="gemini-2.5-flash",
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
                model="gemini-2.5-flash",
                contents=[genai_types.Content(role="user", parts=[
                    genai_types.Part.from_bytes(data=video_bytes, mime_type=mime_type),
                    genai_types.Part.from_text(text=prompt),
                ])],
                config=genai_types.GenerateContentConfig(response_mime_type="application/json"),
            )
            analysis = json.loads(response.text)

        else:
            analysis = {"error": f"Unknown media type: {media_type}"}

        # Merge analysis into result, preserving internal fields
        for key, value in analysis.items():
            result[key] = value

        risk = result.get("risk_percentage", 0)
        indicators = result.get("high_risk_indicator", [])

        _tracker.complete_step(
            check_id, step_name,
            f"Analysis complete — Risk: {risk}%, {len(indicators)} indicators found",
        )

        return {"result": result}

    except Exception as e:
        logger.error("[CompliancePipeline] main_brain_analysis failed: %s", e)
        _tracker.fail_step(check_id, step_name, str(e))
        result = state.get("result", {}) or {}
        result["error"] = str(e)
        return {"result": result}


# ─── Node 4: Judges Agent ────────────────────────────────────────────────────


def judges_agent(state: Compliance_State) -> dict:
    """Bias and hallucination check without search tools.

    Evaluates the compliance result using only the fetched rules and
    persona context. Does NOT invoke any external search tools.
    """
    check_id = state["check_id"]
    step_name = "judges_agent"
    _tracker.start_step(check_id, step_name)

    try:
        result = state.get("result", {}) or {}
        rules = result.get("_rules", [])
        persona = result.get("_persona", {})

        # Build evaluation prompt
        prompt = BIAS_HALLUCINATION_PROMPT.format(
            context_rules=json.dumps(rules, indent=2),
            persona=json.dumps(persona, indent=2),
            compliance_result=json.dumps(
                {k: v for k, v in result.items() if not k.startswith("_")},
                indent=2,
            ),
        )

        response = gemini.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai_types.GenerateContentConfig(response_mime_type="application/json"),
        )
        eval_result = json.loads(response.text)
        result["evaluation"] = eval_result

        hallucination_score = eval_result.get("hallucination_score", 5)
        overall_pass = eval_result.get("overall_pass", True)

        if not overall_pass and hallucination_score < 3:
            logger.warning(
                "[CompliancePipeline] Hallucination detected (score=%d). Flagging result.",
                hallucination_score,
            )
            result["_hallucination_flagged"] = True

        _tracker.complete_step(
            check_id, step_name,
            f"Evaluation complete: pass={overall_pass}, hallucination_score={hallucination_score}",
        )

        return {"result": result}

    except Exception as e:
        logger.error("[CompliancePipeline] judges_agent failed: %s", e)
        _tracker.fail_step(check_id, step_name, str(e))
        result = state.get("result", {}) or {}
        result["_eval_error"] = str(e)
        return {"result": result}


# ─── Node 5: Decision Router ─────────────────────────────────────────────────


def decision_router_node(state: Compliance_State) -> dict:
    """Wraps route_compliance_decision and sets state status.

    Also persists the compliance result to the compliance_checks table.
    On persistence failure, queues in FallbackQueue.
    """
    check_id = state["check_id"]
    step_name = "decision_router"
    _tracker.start_step(check_id, step_name)

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
        _persist_compliance_result(check_id, decision, risk_percentage, persist_result)

        _tracker.complete_step(
            check_id, step_name,
            f"Decision: {decision} (risk_level={risk_level}, risk_percentage={risk_percentage})",
        )

        return {"status": decision, "result": result}

    except Exception as e:
        logger.error("[CompliancePipeline] decision_router_node failed: %s", e)
        _tracker.fail_step(check_id, step_name, str(e))
        return {"status": "remediate"}


# ─── Persistence Helper ──────────────────────────────────────────────────────


def _persist_compliance_result(
    check_id: str,
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
        }).eq("check_id", check_id).execute()

        logger.info("[CompliancePipeline] Persisted result for check_id=%s, status=%s", check_id, status)

    except Exception as e:
        logger.error(
            "[CompliancePipeline] Failed to persist result for check_id=%s: %s. "
            "Queuing in FallbackQueue.",
            check_id, e,
        )
        fallback_queue.enqueue(
            table="compliance_checks",
            operation="update",
            payload={
                "check_id": check_id,
                "status": status,
                "risk_percentage": risk_percentage,
                "result_json": result_json,
            },
        )


# ─── Conditional Edge: Route after fetch_rules_and_personas ───────────────────


def _route_after_fetch(state: Compliance_State) -> Literal["transcribe_media", "main_brain_analysis"]:
    """Route based on media type: audio/video → transcribe, text/image → main_brain."""
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
_graph.add_node("judges_agent", judges_agent)
_graph.add_node("decision_router", decision_router_node)

# Set entry point
_graph.set_entry_point("fetch_rules_and_personas")

# Conditional edge: after fetch → transcribe (audio/video) or main_brain (text/image)
_graph.add_conditional_edges("fetch_rules_and_personas", _route_after_fetch, {
    "transcribe_media": "transcribe_media",
    "main_brain_analysis": "main_brain_analysis",
})

# transcribe_media → main_brain_analysis
_graph.add_edge("transcribe_media", "main_brain_analysis")

# main_brain_analysis → judges_agent
_graph.add_edge("main_brain_analysis", "judges_agent")

# judges_agent → decision_router
_graph.add_edge("judges_agent", "decision_router")

# decision_router → END (pipeline NEVER invokes Remediation)
_graph.add_edge("decision_router", END)

# Compile and export
compliance_pipeline = _graph.compile()
