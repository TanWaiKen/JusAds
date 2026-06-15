"""
pipeline.py
───────────
Rule-based compliance pipeline with human-in-the-loop and remix remediation.

Flow:
  1. compliance_check   → route by media type, get rules + personas, Gemini analysis
  2. post_process       → Tavily verify + bias/hallucination evaluation
  3. human_review       → interrupt() for human approval
  4. route_decision     → "ok" → finalize | "edit" → remix_router
  5. remix_router       → dispatch to media-specific remix tool (text/image/audio/video)
  6. remix_finalize     → quality check; success → finalize, failure → END
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

logger = logging.getLogger(__name__)


# ─── Node 1: Compliance Check ────────────────────────────────────────────────

def node_compliance_check(state: ComplianceState) -> ComplianceState:
    """Route by media type and run the appropriate compliance check."""
    try:
        if state.media_type == "text":
            result = check_text_compliance.invoke({
                "text": state.text_input,
                "market": state.market,
                "platform": state.platform,
                "ethnicity": state.ethnicity,
                "age_group": state.age_group,
            })
        elif state.media_type == "image":
            result = check_image_compliance.invoke({
                "image_path": state.input_path,
                "market": state.market,
                "platform": state.platform,
                "ethnicity": state.ethnicity,
                "age_group": state.age_group,
            })
        elif state.media_type == "audio":
            result = check_audio_compliance.invoke({
                "audio_path": state.input_path,
                "market": state.market,
                "platform": state.platform,
                "ethnicity": state.ethnicity,
                "age_group": state.age_group,
            })
        elif state.media_type == "video":
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

    except Exception as e:
        logger.error(f"Compliance check failed: {e}")
        state.result = {"error": str(e)}

    state.status = "checked"
    return state


# ─── Node 2: Post-Process (verify + bias/hallucination eval) ──────────────────

def node_post_process(state: ComplianceState) -> ComplianceState:
    """Run verification (Tavily) and bias/hallucination evaluation."""

    # --- Step A: Media-specific post-processing ---
    try:
        violations = state.result.get("high_risk_indicator", [])
        risk = state.result.get("risk_percentage", 0)

        if state.media_type == "image" and violations and state.input_path:
            seg_result = segment_violations.invoke({
                "image_path": state.input_path,
                "high_risk_indicators": violations,
            })
            state.result["segmentation"] = seg_result

        elif state.media_type == "video" and violations and state.input_path:
            # Extract clips — auto-parses timestamps, merges close violations
            clips_result = extract_violation_clips.invoke({
                "video_path": state.input_path,
                "violations_timeline": violations,
            })
            state.result["clips"] = clips_result

    except Exception as e:
        logger.warning(f"Media post-processing failed (non-fatal): {e}")

    # --- Step B: Tavily verification ---
    try:
        violations = state.result.get("high_risk_indicator", [])
        if violations:
            verify_result = verify_violations.invoke({
                "violations": violations,
                "market": state.market,
                "platform": state.platform,
            })
            state.result["verification"] = verify_result
    except Exception as e:
        logger.warning(f"Verification failed (non-fatal): {e}")
        state.result["_verify_error"] = str(e)

    # --- Step C: Bias + Hallucination evaluation ---
    try:
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
    except Exception as e:
        logger.warning(f"Bias/hallucination eval failed (non-fatal): {e}")
        state.result["_eval_error"] = str(e)

    return state


# ─── Node 3: Human Review (interrupt) ────────────────────────────────────────

def node_human_review(state: ComplianceState) -> ComplianceState:
    """Pause for human review. Human can approve or request edits."""
    # Present the compliance result to the human
    human_response = interrupt({
        "message": "Compliance check complete. Please review the result.",
        "result": state.result,
        "options": ["ok", "edit"],
    })

    # Store human decision in result
    state.result["human_decision"] = human_response
    return state


# ─── Node 4: Route human decision ────────────────────────────────────────────

def route_human_decision(state: ComplianceState) -> Literal["approved", "edit_requested"]:
    """Route based on human's response."""
    decision = state.result.get("human_decision", "ok")
    if isinstance(decision, str) and decision.strip().lower() in ("edit", "remix", "yes"):
        return "edit_requested"
    return "approved"


# ─── Node 5: Finalize (approved) ─────────────────────────────────────────────

def node_finalize(state: ComplianceState) -> ComplianceState:
    """Mark as verified and done."""
    state.status = "verified"
    state.iteration = 1
    return state


# ─── Node 6: Edit requested (placeholder) ────────────────────────────────────

def node_edit_requested(state: ComplianceState) -> ComplianceState:
    """Placeholder for remix/edit functionality."""
    state.result["edit_response"] = "Understood. Edit/remix functionality will be implemented in the next phase."
    state.status = "edit_pending"
    state.iteration = 1
    return state


# ─── Node 7: Remix Router ─────────────────────────────────────────────────────

def node_remix_router(state: ComplianceState) -> ComplianceState:
    """Route to appropriate remediation tool based on media type.

    Reads state.media_type and dispatches to the correct remix tool,
    passing violations and context from state. Updates state with
    remediation results on success or error details on failure.
    """
    start_time = time.time()

    # Extract context from state
    media_type = state.media_type
    market = state.market
    platform = state.platform
    ethnicity = state.ethnicity
    age_group = state.age_group

    # Extract violations from the compliance check result
    violations = state.result.get("high_risk_indicator", [])
    if not violations:
        # Fallback: try to extract from other result keys
        violations = state.result.get("violations", [])

    # Increment remix iteration
    state.remix_iteration += 1

    try:
        if media_type == "text":
            # Invoke text rewriter
            result = rewrite_text.invoke({
                "text": state.text_input,
                "violations": violations,
                "market": market,
                "platform": platform,
                "ethnicity": ethnicity,
                "age_group": age_group,
            })

            # Check for error in result
            if "error" in result:
                raise RuntimeError(result["error"])

            duration = time.time() - start_time
            state.status = "remediated"
            state.remediated_path = ""  # Text has no file path
            state.result["remix"] = {
                "tool_used": "text_rewriter",
                "output_path": "",
                "changes_made": result.get("changes_made", []),
                "duration_seconds": round(duration, 2),
            }
            # Store rewritten text for downstream use
            state.result["remix"]["rewritten_text"] = result.get("rewritten_text", "")

        elif media_type == "image":
            # Invoke image editor
            result = edit_image.invoke({
                "image_path": state.input_path,
                "violations": violations,
                "market": market,
                "platform": platform,
                "ethnicity": ethnicity,
                "age_group": age_group,
            })

            # Check for error in result
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
            # Invoke audio remixer
            # Extract replacement text from violations or use a default
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

            # Check for error in result
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
            # Video requires both visual and audio edits composed together
            # First run image edits on visual violations, then audio remixes
            visual_edits = []
            audio_edits = []

            for v in violations:
                if isinstance(v, dict):
                    # Attempt visual edit for violations with visual component
                    if v.get("type") == "visual" or "image" in str(v.get("description", "")).lower():
                        visual_edits.append({
                            "start": v.get("start", v.get("start_seconds", 0)),
                            "end": v.get("end", v.get("end_seconds", 0)),
                            "replacement_path": "",
                            "success": False,
                        })
                    # Attempt audio edit for violations with audio component
                    if v.get("type") == "audio" or "audio" in str(v.get("description", "")).lower():
                        audio_edits.append({
                            "start": v.get("start", v.get("start_seconds", 0)),
                            "end": v.get("end", v.get("end_seconds", 0)),
                            "replacement_path": "",
                            "success": False,
                        })

            # If no specific type annotations, treat all as needing both
            if not visual_edits and not audio_edits:
                for v in violations:
                    if isinstance(v, dict) and ("start" in v or "start_seconds" in v):
                        start = v.get("start", v.get("start_seconds", 0))
                        end = v.get("end", v.get("end_seconds", 0))
                        visual_edits.append({
                            "start": start,
                            "end": end,
                            "replacement_path": "",
                            "success": False,
                        })
                        audio_edits.append({
                            "start": start,
                            "end": end,
                            "replacement_path": "",
                            "success": False,
                        })

            # Invoke compose_video with the edits
            result = compose_video.invoke({
                "video_path": state.input_path,
                "visual_edits": visual_edits,
                "audio_edits": audio_edits,
            })

            # Check for error in result
            if "error" in result:
                raise RuntimeError(result["error"])

            duration = time.time() - start_time
            output_path = result.get("output_path", "")
            segments_replaced = result.get("segments_replaced", 0)
            state.status = "remediated"
            state.remediated_path = output_path
            state.result["remix"] = {
                "tool_used": "video_composer",
                "output_path": output_path,
                "changes_made": [
                    f"Video composed with {segments_replaced} segments replaced",
                    *result.get("warnings", []),
                ],
                "duration_seconds": round(duration, 2),
            }

        else:
            raise ValueError(f"Unsupported media type for remix: {media_type}")

        logger.info(
            f"Remix router completed successfully for media_type={media_type} "
            f"in {state.result['remix']['duration_seconds']}s"
        )

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Remix router failed for media_type={media_type}: {e}")
        state.status = "remix_failed"
        # Preserve original asset
        state.result["remix"] = {
            "tool_used": f"{media_type}_remixer",
            "output_path": state.input_path if media_type != "text" else "",
            "changes_made": [],
            "duration_seconds": round(duration, 2),
            "error": str(e),
        }

    return state


# ─── Node 8: Remix Finalize ───────────────────────────────────────────────────

def node_remix_finalize(state: ComplianceState) -> ComplianceState:
    """Finalize remix result with quality validation.

    Checks if remediation succeeded (state.status == "remediated") and
    performs quality validation for image edits. If the quality score
    is below 70, sets status to "remix_failed".
    """
    if state.status != "remediated":
        # Already in a failed state — nothing to validate
        logger.info("Remix finalize: status is not 'remediated', skipping quality check.")
        return state

    # For image edits, validate quality score
    remix_result = state.result.get("remix", {})
    if state.media_type == "image":
        quality_score = remix_result.get("quality_score", 100)

        if quality_score < 70:
            logger.warning(
                f"Remix finalize: image quality check failed (score={quality_score} < 70). "
                f"Setting status to 'remix_failed'."
            )
            state.status = "remix_failed"
            state.result["remix"]["quality_issues"] = (
                f"Quality score {quality_score} is below the minimum threshold of 70."
            )
            return state

    logger.info(f"Remix finalize: remediation successful for media_type={state.media_type}.")
    return state


def route_remix_result(state: ComplianceState) -> Literal["success", "failure"]:
    """Route based on remix result: success → finalize, failure → END."""
    if state.status == "remediated":
        return "success"
    return "failure"


# ─── Build the pipeline ──────────────────────────────────────────────────────

_graph = StateGraph(ComplianceState)

# Nodes
_graph.add_node("compliance_check", node_compliance_check)
_graph.add_node("post_process", node_post_process)
_graph.add_node("human_review", node_human_review)
_graph.add_node("finalize", node_finalize)
_graph.add_node("remix_router", node_remix_router)
_graph.add_node("remix_finalize", node_remix_finalize)

# Edges
_graph.set_entry_point("compliance_check")
_graph.add_edge("compliance_check", "post_process")
_graph.add_edge("post_process", "human_review")
_graph.add_conditional_edges("human_review", route_human_decision, {
    "approved": "finalize",
    "edit_requested": "remix_router",
})
_graph.add_edge("remix_router", "remix_finalize")
_graph.add_conditional_edges("remix_finalize", route_remix_result, {
    "success": "finalize",
    "failure": END,
})
_graph.add_edge("finalize", END)

# Compile and export
compliance_pipeline = _graph.compile()

