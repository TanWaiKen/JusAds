"""
remix_graph.py
──────────────
LangGraph StateGraph for the JusAds Remix Pipeline.

Orchestrates human-in-the-loop remix generation across all media types
(text, image, audio, video) with interrupt points for user decisions.

Graph structure:
  START → route_media → [await_image_choice | generate_remix]
  await_image_choice → generate_remix
  generate_remix → await_user_decision
  await_user_decision → route_decision → [finalize | generate_remix | END]

Usage:
  from jusads_remix_pipeline.remix_graph import RemixState, remix_graph
"""

from typing import TypedDict

import logging

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt

from jusads_remix_pipeline.text_remixer import remix_text
from jusads_remix_pipeline.audio_remixer import remix_audio
from jusads_remix_pipeline.image_remixer import remix_image
from jusads_remix_pipeline.segment_planner import plan_segments
from jusads_remix_pipeline.storyboard_generator import generate_storyboard
from jusads_remix_pipeline.video_interpolator import interpolate_video
from jusads_remix_pipeline.script_generator import generate_script_and_voiceover
from jusads_remix_pipeline.video_composer import compose_video

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STATE SCHEMA
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class RemixState(TypedDict):
    """Full state for the remix pipeline graph.

    Fields are grouped by purpose:
    - Identity: links this remix run to a compliance check and thread
    - Input context: the media and violations to be remixed
    - Intermediate results: populated by generation nodes
    - Video-specific intermediate state: sub-pipeline outputs
    - Human-in-the-loop: user decisions at interrupt points
    - Iteration tracking: enforce max regeneration loops
    - Output: finalized result and status
    """

    # Identity
    check_id: str
    thread_id: str
    media_type: str  # "text" | "image" | "audio" | "video"

    # Input context
    file_path: str
    text_input: str
    violations: list[dict]
    target_audience: dict  # { market, ethnicity, age_group }

    # Intermediate results (populated by nodes)
    remix_result: dict
    generation_progress: list[dict]

    # Video-specific intermediate state
    segment_plan: list[dict]
    storyboard_frames: list[dict]
    interpolated_clips: list[dict]
    script_and_voiceover: dict
    composed_video_path: str

    # Human-in-the-loop
    user_decision: str  # "accept" | "reject" | "regenerate"
    user_feedback: str
    image_remix_choice: str  # "edit" | "regenerate"

    # Iteration tracking
    iteration_count: int
    max_iterations: int  # default: 5

    # Output
    final_output: dict
    status: str  # "generating" | "awaiting_decision" | "finalized" | "rejected" | "error"
    error: str


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# NODE STUBS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def route_media(state: RemixState) -> dict:
    """Entry node — logs entry and returns empty dict.

    Routing logic is handled by the conditional edge function
    `route_by_media`, not by this node itself.
    """
    logger.info(
        "route_media: entering remix pipeline for media_type=%s, check_id=%s",
        state.get("media_type"),
        state.get("check_id"),
    )
    return {}


def route_by_media(state: RemixState) -> str:
    """Conditional edge function — routes to the appropriate next node
    based on media_type.

    Returns:
        "await_image_choice" for image media type
        "generate_remix" for text, audio, and video media types
    """
    media_type = state.get("media_type", "text")
    if media_type == "image":
        return "await_image_choice"
    return "generate_remix"


def await_image_choice(state: RemixState) -> dict:
    """For image media: interrupts the graph to collect the user's choice
    of remediation method ('edit' or 'regenerate') before generation.

    Calls interrupt() to pause graph execution. When resumed, the user's
    choice is extracted and stored in state as image_remix_choice.
    """
    user_input = interrupt(
        {
            "type": "image_method_choice",
            "violations": state["violations"],
            "message": "Choose how to remix this image: edit (inpaint) or regenerate entirely.",
        }
    )
    return {
        "image_remix_choice": user_input["choice"],
    }


def generate_remix(state: RemixState) -> dict:
    """Executes the actual remix generation based on media_type.

    - text: single-step text rewrite
    - audio: transcript correction + voice regeneration
    - image: edit or regenerate based on image_remix_choice
    - video: 5-step sub-pipeline (segment → storyboard → interpolation →
      script/voiceover → composition)

    Incorporates user_feedback into regeneration prompts when iteration_count > 0.
    """
    media = state.get("media_type", "text")
    iteration_count = state.get("iteration_count", 0)
    user_feedback = state.get("user_feedback", "")

    logger.info(
        "generate_remix: media_type=%s, iteration=%d", media, iteration_count
    )

    if media == "text":
        # Incorporate feedback into violations context for regeneration
        violations = state["violations"]
        if iteration_count > 0 and user_feedback:
            violations = _augment_violations_with_feedback(violations, user_feedback)

        result = remix_text(
            state["text_input"], violations, state["target_audience"]
        )
        return {
            "remix_result": result.model_dump() if hasattr(result, "model_dump") else result,
            "status": "awaiting_decision",
            "iteration_count": iteration_count + 1,
        }

    elif media == "audio":
        violations = state["violations"]
        if iteration_count > 0 and user_feedback:
            violations = _augment_violations_with_feedback(violations, user_feedback)

        # Use a default duration of 30.0 seconds if not derivable from state
        original_duration = 30.0
        result = remix_audio(
            state["text_input"], violations, state["target_audience"], original_duration
        )
        return {
            "remix_result": result.model_dump() if hasattr(result, "model_dump") else result,
            "status": "awaiting_decision",
            "iteration_count": iteration_count + 1,
        }

    elif media == "image":
        violations = state["violations"]
        if iteration_count > 0 and user_feedback:
            violations = _augment_violations_with_feedback(violations, user_feedback)

        result = remix_image(
            state["file_path"],
            violations,
            state["target_audience"],
            state["image_remix_choice"],
        )
        return {
            "remix_result": result.model_dump() if hasattr(result, "model_dump") else result,
            "status": "awaiting_decision",
            "iteration_count": iteration_count + 1,
        }

    elif media == "video":
        violations = state["violations"]
        if iteration_count > 0 and user_feedback:
            violations = _augment_violations_with_feedback(violations, user_feedback)

        # Step 1: Segment Planning
        # Extract video_duration from state or use a default
        video_duration = 30.0  # Default; in production, extract from file_path
        logger.info("generate_remix [video]: Step 1 — Segment Planning")
        segment_plan = plan_segments(violations, video_duration)

        # If plan_segments returned an error dict, propagate it
        if isinstance(segment_plan, dict) and "error" in segment_plan:
            return {
                "remix_result": segment_plan,
                "status": "error",
                "error": segment_plan.get("error", "Segment planning failed"),
                "iteration_count": iteration_count + 1,
            }

        generation_progress = [
            {"step": "segment_planning", "status": "complete"}
        ]

        # Step 2: Storyboard Generation — generate frames for each chunk
        logger.info("generate_remix [video]: Step 2 — Storyboard Generation")
        all_frames: list[dict] = []
        for chunk in segment_plan:
            frames = generate_storyboard(
                chunk, state["target_audience"], {}
            )
            all_frames.append(frames)

        generation_progress.append(
            {"step": "storyboard", "status": "complete"}
        )

        # Step 3: Video Interpolation — generate clips from frames
        logger.info("generate_remix [video]: Step 3 — Video Interpolation")
        all_clips: list[dict] = []
        for frame_set in all_frames:
            frame_images = frame_set.get("frames", [])
            clip = interpolate_video(frame_images, state["file_path"])
            all_clips.append(clip)

        generation_progress.append(
            {"step": "interpolation", "status": "complete"}
        )

        # Step 4: Script & Voiceover
        logger.info("generate_remix [video]: Step 4 — Script & Voiceover")
        script_vo = generate_script_and_voiceover(
            all_clips, state["target_audience"]
        )

        generation_progress.append(
            {"step": "script_voiceover", "status": "complete"}
        )

        # Step 5: Composition (FFmpeg)
        logger.info("generate_remix [video]: Step 5 — Video Composition")
        voiceover_segments = script_vo.get("voiceover_segments", [])
        composed = compose_video(
            segment_plan, all_clips, voiceover_segments, state["file_path"]
        )

        generation_progress.append(
            {"step": "composition", "status": "complete"}
        )

        composed_path = composed.get("output_path", "")

        return {
            "segment_plan": segment_plan,
            "storyboard_frames": all_frames,
            "interpolated_clips": all_clips,
            "script_and_voiceover": script_vo,
            "composed_video_path": composed_path,
            "generation_progress": generation_progress,
            "remix_result": {"video_path": composed_path, "type": "video"},
            "status": "awaiting_decision",
            "iteration_count": iteration_count + 1,
        }

    else:
        logger.error("generate_remix: unsupported media_type=%s", media)
        return {
            "status": "error",
            "error": f"Unsupported media type: {media}",
        }


def _augment_violations_with_feedback(
    violations: list[dict], feedback: str
) -> list[dict]:
    """Augment violation data with user feedback for regeneration.

    Adds user feedback as context to help the remixer address the user's
    specific concerns in the next iteration.
    """
    augmented = []
    for v in violations:
        augmented_v = dict(v)
        augmented_v["user_feedback"] = feedback
        augmented.append(augmented_v)
    return augmented


def await_user_decision(state: RemixState) -> dict:
    """Interrupts the graph after generation to present the remix result
    for user review. Waits for accept/reject/regenerate decision."""
    user_input = interrupt(
        {
            "type": "review_remix",
            "remix_result": state["remix_result"],
            "message": "Review the generated remix. Accept, reject, or request changes.",
        }
    )
    return {
        "user_decision": user_input["decision"],
        "user_feedback": user_input.get("feedback", ""),
    }


def route_decision(state: RemixState) -> str:
    """Conditional edge function — routes based on user_decision.

    Returns:
        "accept" when user_decision == "accept" → maps to "finalize" node
        "regenerate" when user_decision == "regenerate" AND iteration_count < max_iterations → maps to "generate_remix" node
        "reject" when user_decision == "regenerate" but max_iterations reached → maps to END
        "reject" when user_decision == "reject" or default → maps to END
    """
    decision = state.get("user_decision", "reject")
    max_iterations = state.get("max_iterations", 5)
    iteration_count = state.get("iteration_count", 0)

    if decision == "accept":
        return "accept"
    elif decision == "regenerate":
        if iteration_count < max_iterations:
            return "regenerate"
        else:
            logger.warning(
                "route_decision: max iterations (%d) reached, ending pipeline",
                max_iterations,
            )
            return "reject"
    else:
        # "reject" or any unknown value → END
        return "reject"


def finalize(state: RemixState) -> dict:
    """Copies remix_result to final_output, sets status to 'finalized',
    and persists the final asset."""
    logger.info(
        "finalize: persisting final output for check_id=%s",
        state.get("check_id"),
    )
    return {
        "final_output": state["remix_result"],
        "status": "finalized",
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GRAPH DEFINITION (compiled in task 13.7)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

remix_workflow = StateGraph(RemixState)

# Add nodes
remix_workflow.add_node("route_media", route_media)
remix_workflow.add_node("await_image_choice", await_image_choice)
remix_workflow.add_node("generate_remix", generate_remix)
remix_workflow.add_node("await_user_decision", await_user_decision)
remix_workflow.add_node("finalize", finalize)

# Entry point
remix_workflow.set_entry_point("route_media")

# Conditional: route by media type
remix_workflow.add_conditional_edges("route_media", route_by_media, {
    "image": "await_image_choice",
    "text": "generate_remix",
    "audio": "generate_remix",
    "video": "generate_remix",
})

# Image choice → generate
remix_workflow.add_edge("await_image_choice", "generate_remix")

# Generate → await decision
remix_workflow.add_edge("generate_remix", "await_user_decision")

# Decision → conditional routing
remix_workflow.add_conditional_edges("await_user_decision", route_decision, {
    "accept": "finalize",
    "regenerate": "generate_remix",
    "reject": END,
})

# Finalize → END
remix_workflow.add_edge("finalize", END)

# Compile with MemorySaver for development (swap to PostgresSaver for production)
checkpointer = MemorySaver()
remix_graph = remix_workflow.compile(checkpointer=checkpointer)
