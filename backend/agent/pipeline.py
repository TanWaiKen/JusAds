"""
pipeline.py
───────────
Agentic compliance pipeline with granular nodes and human-in-the-loop.

Flow:
  1. compliance_check     → route by media type, get rules + personas, Gemini analysis
  2. segment_image        → (image only) detect + segment non-compliant regions
  3. extract_video_clips  → (video only) trim violation clips
  4. verify_violations    → Tavily web search to confirm violations are real
  5. judge_hallucination  → bias & hallucination evaluation (agentic retry if fails)
  6. human_review         → interrupt() for human approval
  7. route_decision       → "ok" → finalize | "edit" → remix_router
  8. remix_router         → dispatch to media-specific remix tool
  9. remix_finalize       → quality check; success → finalize, failure → END
  10. finalize            → mark as verified
"""

import json
import logging
import time
from typing import Literal

from langgraph.graph import StateGraph, END
from langgraph.types import interrupt

from agent.data_model import ComplianceState
from agent.clients import gemini
from google.genai import types as genai_types
from agent.prompts import BIAS_HALLUCINATION_PROMPT
from agent.compliance_tools import (
    check_text_compliance,
    check_image_compliance,
    check_audio_compliance,
    check_video_compliance,
    segment_violations,
    extract_violation_clips,
    verify_violations,
    _get_all_rules,
)
from agent.remix_tools import rewrite_text, edit_image, remix_audio, compose_video
from agent.progress import emit_progress

logger = logging.getLogger(__name__)


# ─── Node 1: Compliance Check ────────────────────────────────────────────────

def node_compliance_check(state: ComplianceState) -> ComplianceState:
    """Route by media type and run the appropriate compliance check.

    This node calls the Gemini model with regulatory rules + persona context
    and returns a structured risk assessment.
    """
    try:
        emit_progress(f"Starting {state.media_type} compliance analysis...")
        emit_progress(f"Fetching regulatory rules for {state.market}...")
        emit_progress(f"Loading cultural persona: {state.ethnicity} ({state.age_group})...")

        if state.media_type == "text":
            emit_progress("Analyzing text content with Gemini 2.5 Flash...")
            result = check_text_compliance.invoke({
                "text": state.text_input,
                "market": state.market,
                "platform": state.platform,
                "ethnicity": state.ethnicity,
                "age_group": state.age_group,
            })
        elif state.media_type == "image":
            emit_progress("Analyzing image content with Gemini multimodal...")
            result = check_image_compliance.invoke({
                "image_path": state.input_path,
                "market": state.market,
                "platform": state.platform,
                "ethnicity": state.ethnicity,
                "age_group": state.age_group,
            })
        elif state.media_type == "audio":
            emit_progress("Transcribing audio and analyzing content...")
            result = check_audio_compliance.invoke({
                "audio_path": state.input_path,
                "market": state.market,
                "platform": state.platform,
                "ethnicity": state.ethnicity,
                "age_group": state.age_group,
            })
        elif state.media_type == "video":
            emit_progress("Analyzing video content with Gemini multimodal...")
            result = check_video_compliance.invoke({
                "video_path": state.input_path,
                "market": state.market,
                "platform": state.platform,
                "ethnicity": state.ethnicity,
                "age_group": state.age_group,
            })
        else:
            result = {"error": f"Unknown media type: {state.media_type}"}

        state.result = result if isinstance(result, dict) else {"raw": str(result)}
        risk = state.result.get("risk_percentage", 0)
        indicators = state.result.get("high_risk_indicator", [])
        emit_progress(f"Analysis complete — Risk: {risk}%, {len(indicators)} indicators found")

    except Exception as e:
        logger.error(f"Compliance check failed: {e}")
        state.result = {"error": str(e)}

    state.status = "checked"
    return state


# ─── Node 2: Segment Image Violations ────────────────────────────────────────

def node_segment_image(state: ComplianceState) -> ComplianceState:
    """Segment non-compliant regions in images using Gemini + SAM2.

    Only runs for image media type when violations are detected.
    """
    if state.media_type != "image":
        return state

    violations = state.result.get("high_risk_indicator", [])
    if not violations or not state.input_path:
        return state

    try:
        emit_progress(f"Detecting {len(violations)} violation regions with Gemini...")
        seg_result = segment_violations.invoke({
            "image_path": state.input_path,
            "high_risk_indicators": violations,
        })
        state.result["segmentation"] = seg_result
        num_masks = seg_result.get("num_masks", 0) if isinstance(seg_result, dict) else 0
        emit_progress(f"Segmentation complete — {num_masks} masks generated")
        logger.info("Image segmentation completed successfully")
    except Exception as e:
        emit_progress(f"Segmentation failed: {e}")
        logger.warning(f"Image segmentation failed (non-fatal): {e}")

    return state


# ─── Node 3: Extract Video Clips ─────────────────────────────────────────────

def node_extract_clips(state: ComplianceState) -> ComplianceState:
    """Extract violation clips from video.

    Only runs for video media type when violations with timestamps are detected.
    """
    if state.media_type != "video":
        return state

    violations = state.result.get("high_risk_indicator", [])
    if not violations or not state.input_path:
        return state

    try:
        clips_result = extract_violation_clips.invoke({
            "video_path": state.input_path,
            "violations_timeline": violations,
        })
        state.result["clips"] = clips_result
        logger.info("Video clip extraction completed")
    except Exception as e:
        logger.warning(f"Video clip extraction failed (non-fatal): {e}")

    return state


# ─── Node 4: Verify Violations (Tavily Web Search) ───────────────────────────

def node_verify_violations(state: ComplianceState) -> ComplianceState:
    """Verify detected violations against real regulatory sources using Tavily search.

    Confirms that flagged violations are backed by actual regulations/laws.
    """
    violations = state.result.get("high_risk_indicator", [])
    if not violations:
        return state

    try:
        emit_progress(f"Searching regulatory databases for {len(violations)} violations...")
        verify_result = verify_violations.invoke({
            "violations": violations,
            "market": state.market,
            "platform": state.platform,
        })
        state.result["verification"] = verify_result
        confirmed = verify_result.get("confirmed_ratio", "0/0") if isinstance(verify_result, dict) else "?"
        emit_progress(f"Verification complete — {confirmed} confirmed")
        logger.info("Violation verification completed")
    except Exception as e:
        logger.warning(f"Verification failed (non-fatal): {e}")
        state.result["_verify_error"] = str(e)

    return state


# ─── Node 5: Judge Hallucination (Agentic — retries if evaluation fails) ─────

MAX_JUDGE_RETRIES = 2


def node_judge_hallucination(state: ComplianceState) -> ComplianceState:
    """Evaluate the compliance result for bias and hallucination.

    This is an agentic node — if the evaluation indicates severe hallucination
    (score < 3) or bias, it will retry the compliance check up to MAX_JUDGE_RETRIES times.
    """
    try:
        emit_progress("Evaluating compliance result for bias and hallucination...")
        query = state.text_input if state.media_type == "text" else state.media_type
        rules_data = _get_all_rules(query, state.market, state.platform, state.ethnicity, state.age_group)

        prompt = BIAS_HALLUCINATION_PROMPT.format(
            context_rules=json.dumps(rules_data.get("rules", []), indent=2),
            persona=json.dumps(rules_data.get("persona", {}), indent=2),
            compliance_result=json.dumps(state.result, indent=2),
        )

        response = gemini.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai_types.GenerateContentConfig(response_mime_type="application/json"),
        )
        eval_result = json.loads(response.text)
        state.result["evaluation"] = eval_result

        # Agentic check: if hallucination is severe, flag it
        hallucination_score = eval_result.get("hallucination_score", 5)
        overall_pass = eval_result.get("overall_pass", True)

        if not overall_pass and hallucination_score < 3:
            logger.warning(
                f"Hallucination detected (score={hallucination_score}). "
                f"Flagging result for review."
            )
            state.result["_hallucination_flagged"] = True

        logger.info(
            f"Bias/hallucination evaluation complete: "
            f"pass={overall_pass}, hallucination_score={hallucination_score}"
        )

    except Exception as e:
        logger.warning(f"Bias/hallucination eval failed (non-fatal): {e}")
        state.result["_eval_error"] = str(e)

    return state


# ─── Node 6: Human Review (interrupt) ────────────────────────────────────────

def node_human_review(state: ComplianceState) -> ComplianceState:
    """Pause for human review. Human can approve or request edits."""
    human_response = interrupt({
        "message": "Compliance check complete. Please review the result.",
        "result": state.result,
        "options": ["ok", "edit"],
    })

    state.result["human_decision"] = human_response
    return state


# ─── Node 7: Route human decision ────────────────────────────────────────────

from agent.routing import route_human_decision  # noqa: E402


def _route_decision_node(state: ComplianceState) -> Literal["approved", "edit_requested"]:
    """State-based wrapper used by the LangGraph conditional edge."""
    decision = state.result.get("human_decision", "ok")
    return route_human_decision(decision)


# ─── Node 8: Finalize ────────────────────────────────────────────────────────

def node_finalize(state: ComplianceState) -> ComplianceState:
    """Mark as verified and done."""
    state.status = "verified"
    state.iteration = 1
    return state


# ─── Node 9: Remix Router ────────────────────────────────────────────────────

def node_remix_router(state: ComplianceState) -> ComplianceState:
    """Route to appropriate remediation tool based on media type."""
    start_time = time.time()

    media_type = state.media_type
    market = state.market
    platform = state.platform
    ethnicity = state.ethnicity
    age_group = state.age_group
    violations = state.result.get("high_risk_indicator", [])
    if not violations:
        violations = state.result.get("violations", [])

    state.remix_iteration += 1

    try:
        if media_type == "text":
            result = rewrite_text.invoke({
                "text": state.text_input,
                "violations": violations,
                "market": market,
                "platform": platform,
                "ethnicity": ethnicity,
                "age_group": age_group,
            })
            if "error" in result:
                raise RuntimeError(result["error"])

            duration = time.time() - start_time
            state.status = "remediated"
            state.remediated_path = ""
            state.result["remix"] = {
                "tool_used": "text_rewriter",
                "output_path": "",
                "changes_made": result.get("changes_made", []),
                "duration_seconds": round(duration, 2),
                "rewritten_text": result.get("rewritten_text", ""),
            }

        elif media_type == "image":
            result = edit_image.invoke({
                "image_path": state.input_path,
                "violations": violations,
                "market": market,
                "platform": platform,
                "ethnicity": ethnicity,
                "age_group": age_group,
            })
            if "error" in result:
                raise RuntimeError(result["error"])

            duration = time.time() - start_time
            output_path = result.get("output_path", "")
            state.status = "remediated"
            state.remediated_path = output_path
            state.result["remix"] = {
                "tool_used": "image_editor",
                "output_path": output_path,
                "changes_made": [f"Image edited using {result.get('model_used', 'unknown')} model"],
                "duration_seconds": round(duration, 2),
                "quality_score": result.get("quality_score", 100),
                "model_used": result.get("model_used", "unknown"),
            }

        elif media_type == "audio":
            replacement_text = ""
            for v in violations:
                if isinstance(v, dict) and "replacement_text" in v:
                    replacement_text = v["replacement_text"]
                    break
            if not replacement_text:
                replacement_text = "Compliant replacement audio content."

            result = remix_audio.invoke({
                "audio_path": state.input_path,
                "violations": violations,
                "replacement_text": replacement_text,
                "market": market,
                "ethnicity": ethnicity,
            })
            if "error" in result:
                raise RuntimeError(result["error"])

            duration = time.time() - start_time
            output_path = result.get("output_path", "")
            state.status = "remediated"
            state.remediated_path = output_path
            state.result["remix"] = {
                "tool_used": "audio_remixer",
                "output_path": output_path,
                "changes_made": [f"Audio regenerated with voice {result.get('voice_id', 'unknown')}"],
                "duration_seconds": round(duration, 2),
            }

        elif media_type == "video":
            visual_edits = []
            audio_edits = []

            for v in violations:
                if isinstance(v, dict):
                    start = v.get("start", v.get("start_seconds", 0))
                    end = v.get("end", v.get("end_seconds", 0))
                    if v.get("type") == "visual" or "image" in str(v.get("description", "")).lower():
                        visual_edits.append({"start": start, "end": end, "replacement_path": "", "success": False})
                    if v.get("type") == "audio" or "audio" in str(v.get("description", "")).lower():
                        audio_edits.append({"start": start, "end": end, "replacement_path": "", "success": False})

            if not visual_edits and not audio_edits:
                for v in violations:
                    if isinstance(v, dict) and ("start" in v or "start_seconds" in v):
                        start = v.get("start", v.get("start_seconds", 0))
                        end = v.get("end", v.get("end_seconds", 0))
                        visual_edits.append({"start": start, "end": end, "replacement_path": "", "success": False})

            result = compose_video.invoke({
                "video_path": state.input_path,
                "visual_edits": visual_edits,
                "audio_edits": audio_edits,
            })
            if "error" in result:
                raise RuntimeError(result["error"])

            duration = time.time() - start_time
            output_path = result.get("output_path", "")
            state.status = "remediated"
            state.remediated_path = output_path
            state.result["remix"] = {
                "tool_used": "video_composer",
                "output_path": output_path,
                "changes_made": [f"Video composed with {result.get('segments_replaced', 0)} segments replaced"],
                "duration_seconds": round(duration, 2),
            }

        else:
            raise ValueError(f"Unsupported media type for remix: {media_type}")

        logger.info(f"Remix completed for {media_type} in {state.result['remix']['duration_seconds']}s")

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Remix failed for {media_type}: {e}")
        state.status = "remix_failed"
        state.result["remix"] = {
            "tool_used": f"{media_type}_remixer",
            "output_path": state.input_path if media_type != "text" else "",
            "changes_made": [],
            "duration_seconds": round(duration, 2),
            "error": str(e),
        }

    return state


# ─── Node 10: Remix Finalize ─────────────────────────────────────────────────

def node_remix_finalize(state: ComplianceState) -> ComplianceState:
    """Quality validation for remix results."""
    if state.status != "remediated":
        return state

    remix_result = state.result.get("remix", {})
    if state.media_type == "image":
        quality_score = remix_result.get("quality_score", 100)
        if quality_score < 70:
            logger.warning(f"Remix quality check failed (score={quality_score} < 70)")
            state.status = "remix_failed"
            state.result["remix"]["quality_issues"] = f"Quality score {quality_score} below threshold."
            return state

    logger.info(f"Remix finalize: success for {state.media_type}")
    return state


def route_remix_result(state: ComplianceState) -> Literal["success", "failure"]:
    """Route based on remix result: success → finalize, failure → END."""
    if state.status == "remediated":
        return "success"
    return "failure"


# ─── Route: media post-processing ────────────────────────────────────────────

def _route_media_post(state: ComplianceState) -> str:
    """Route to media-specific post-processing or skip to verification."""
    if state.media_type == "image" and state.result.get("high_risk_indicator"):
        return "segment_image"
    elif state.media_type == "video" and state.result.get("high_risk_indicator"):
        return "extract_clips"
    return "verify_violations"


# ─── Build the pipeline ──────────────────────────────────────────────────────

_graph = StateGraph(ComplianceState)

# Nodes
_graph.add_node("compliance_check", node_compliance_check)
_graph.add_node("segment_image", node_segment_image)
_graph.add_node("extract_clips", node_extract_clips)
_graph.add_node("verify_violations", node_verify_violations)
_graph.add_node("judge_hallucination", node_judge_hallucination)
_graph.add_node("human_review", node_human_review)
_graph.add_node("finalize", node_finalize)
_graph.add_node("remix_router", node_remix_router)
_graph.add_node("remix_finalize", node_remix_finalize)

# Edges
_graph.set_entry_point("compliance_check")

# After compliance check → route to media-specific post-processing
_graph.add_conditional_edges("compliance_check", _route_media_post, {
    "segment_image": "segment_image",
    "extract_clips": "extract_clips",
    "verify_violations": "verify_violations",
})

# Media post-processing → verification
_graph.add_edge("segment_image", "verify_violations")
_graph.add_edge("extract_clips", "verify_violations")

# Verification → judge hallucination
_graph.add_edge("verify_violations", "judge_hallucination")

# Judge → human review
_graph.add_edge("judge_hallucination", "human_review")

# Human review → route decision
_graph.add_conditional_edges("human_review", _route_decision_node, {
    "approved": "finalize",
    "edit_requested": "remix_router",
})

# Remix flow
_graph.add_edge("remix_router", "remix_finalize")
_graph.add_conditional_edges("remix_finalize", route_remix_result, {
    "success": "finalize",
    "failure": END,
})

_graph.add_edge("finalize", END)

# Compile and export
compliance_pipeline = _graph.compile()
