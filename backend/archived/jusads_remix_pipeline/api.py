"""
api.py
──────
FastAPI endpoints for the JusAds Remix Pipeline.

Provides HTTP interface for the LangGraph-based remix workflow:
  POST /remix/start        → Start a new remix pipeline run
  GET  /remix/{id}/status  → Get current graph state
  POST /remix/{id}/decision → Submit user decision (accept/reject/regenerate)
  GET  /remix/{id}/stream  → SSE stream of generation progress

The router is mounted at prefix="/remix" in langgraph_api.py.
"""

import asyncio
import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Literal

from langgraph.types import Command

from jusads_remix_pipeline.remix_graph import remix_graph, RemixState

logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# REQUEST / RESPONSE MODELS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TargetAudience(BaseModel):
    """Target audience for the remix."""

    market: str = Field(..., description="Target market (e.g., Malaysia)")
    ethnicity: str = Field(..., description="Target ethnicity (e.g., Malay, Chinese)")
    age_group: str = Field(default="all_ages", description="Target age group")


class RemixStartRequest(BaseModel):
    """Request body for POST /remix/start."""

    check_id: str = Field(..., min_length=1, description="Compliance check ID")
    media_type: Literal["text", "image", "audio", "video"] = Field(
        ..., description="Media type to remix"
    )
    file_path: Optional[str] = Field(
        default=None, description="Path to the media file (required for image/audio/video)"
    )
    text_input: Optional[str] = Field(
        default=None, description="Text content (required for text media type)"
    )
    violations: list[dict] = Field(
        ..., min_length=1, description="List of violation records"
    )
    target_audience: TargetAudience = Field(
        ..., description="Target audience information"
    )


class RemixStartResponse(BaseModel):
    """Response body for POST /remix/start."""

    thread_id: str
    status: str
    message: str


class RemixStatusResponse(BaseModel):
    """Response body for GET /remix/{thread_id}/status."""

    thread_id: str
    status: str
    interrupt_type: Optional[str] = None
    remix_result: Optional[dict] = None
    iteration_count: int = 0
    generation_progress: Optional[list[dict]] = None


class DecisionRequest(BaseModel):
    """Request body for POST /remix/{thread_id}/decision."""

    decision: Literal["accept", "reject", "regenerate"] = Field(
        ..., description="User decision on the remix result"
    )
    feedback: Optional[str] = Field(
        default=None, description="Optional feedback for regeneration"
    )


class DecisionResponse(BaseModel):
    """Response body for POST /remix/{thread_id}/decision."""

    thread_id: str
    status: str
    final_output: Optional[dict] = None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ROUTER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

remix_router = APIRouter()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# POST /remix/start
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@remix_router.post("/start", response_model=RemixStartResponse)
async def start_remix(request: RemixStartRequest, background_tasks: BackgroundTasks):
    """Start a new remix pipeline run.

    Validates input, generates a thread_id, and invokes the remix graph.
    The graph runs until the first interrupt point (awaiting user decision).
    """
    # Validate media-type-specific requirements
    if request.media_type == "text" and not request.text_input:
        raise HTTPException(
            status_code=400,
            detail={"error": "text_input is required for text media type", "field": "text_input"},
        )
    if request.media_type in ("image", "audio", "video") and not request.file_path:
        raise HTTPException(
            status_code=400,
            detail={
                "error": f"file_path is required for {request.media_type} media type",
                "field": "file_path",
            },
        )

    # Generate unique thread_id
    thread_id = str(uuid.uuid4())

    # Build initial state
    initial_state: RemixState = {
        "check_id": request.check_id,
        "thread_id": thread_id,
        "media_type": request.media_type,
        "file_path": request.file_path or "",
        "text_input": request.text_input or "",
        "violations": request.violations,
        "target_audience": request.target_audience.model_dump(),
        "remix_result": {},
        "generation_progress": [],
        "segment_plan": [],
        "storyboard_frames": [],
        "interpolated_clips": [],
        "script_and_voiceover": {},
        "composed_video_path": "",
        "user_decision": "",
        "user_feedback": "",
        "image_remix_choice": "",
        "iteration_count": 0,
        "max_iterations": 5,
        "final_output": {},
        "status": "generating",
        "error": "",
    }

    config = {"configurable": {"thread_id": thread_id}}

    # Invoke graph asynchronously — it will run until the first interrupt
    try:
        await remix_graph.ainvoke(initial_state, config=config)
    except Exception as e:
        logger.error("Failed to start remix pipeline: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail={"error": f"Failed to start remix pipeline: {str(e)}"},
        )

    return RemixStartResponse(
        thread_id=thread_id,
        status="generating",
        message="Remix pipeline started",
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET /remix/{thread_id}/status
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@remix_router.get("/{thread_id}/status", response_model=RemixStatusResponse)
async def get_remix_status(thread_id: str):
    """Get the current state of a remix pipeline run.

    Reads the graph state from the checkpointer and returns status info
    including interrupt type (if awaiting decision), remix result, and progress.
    """
    config = {"configurable": {"thread_id": thread_id}}

    try:
        state_snapshot = await remix_graph.aget_state(config)
    except Exception as e:
        logger.error("Failed to get state for thread %s: %s", thread_id, str(e))
        raise HTTPException(
            status_code=404,
            detail={"error": f"Thread not found: {thread_id}"},
        )

    if state_snapshot is None or state_snapshot.values is None:
        raise HTTPException(
            status_code=404,
            detail={"error": f"Thread not found: {thread_id}"},
        )

    values = state_snapshot.values

    # Determine interrupt type from the snapshot's next nodes
    interrupt_type = None
    if state_snapshot.next:
        # Graph is paused at an interrupt — determine which type
        next_nodes = state_snapshot.next
        if "await_user_decision" in next_nodes:
            interrupt_type = "review_remix"
        elif "await_image_choice" in next_nodes:
            interrupt_type = "image_method_choice"

    return RemixStatusResponse(
        thread_id=thread_id,
        status=values.get("status", "unknown"),
        interrupt_type=interrupt_type,
        remix_result=values.get("remix_result") or None,
        iteration_count=values.get("iteration_count", 0),
        generation_progress=values.get("generation_progress") or None,
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# POST /remix/{thread_id}/decision
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@remix_router.post("/{thread_id}/decision", response_model=DecisionResponse)
async def submit_decision(thread_id: str, request: DecisionRequest):
    """Submit a user decision for a remix that is awaiting review.

    Resumes the graph from its interrupt point with the user's decision.
    Returns the updated status after the graph processes the decision.
    """
    config = {"configurable": {"thread_id": thread_id}}

    # Verify graph is in an interrupted state
    try:
        state_snapshot = await remix_graph.aget_state(config)
    except Exception as e:
        logger.error("Failed to get state for thread %s: %s", thread_id, str(e))
        raise HTTPException(
            status_code=404,
            detail={"error": f"Thread not found: {thread_id}"},
        )

    if state_snapshot is None or state_snapshot.values is None:
        raise HTTPException(
            status_code=404,
            detail={"error": f"Thread not found: {thread_id}"},
        )

    # Check that the graph is actually at an interrupt point
    if not state_snapshot.next:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "Graph is not in an interruptible state. "
                "The pipeline may have already completed or not yet reached an interrupt point."
            },
        )

    # Resume graph with user decision
    resume_payload = {
        "decision": request.decision,
        "feedback": request.feedback or "",
    }

    try:
        await remix_graph.ainvoke(
            Command(resume=resume_payload),
            config=config,
        )
    except Exception as e:
        logger.error("Failed to resume graph for thread %s: %s", thread_id, str(e))
        raise HTTPException(
            status_code=500,
            detail={"error": f"Failed to process decision: {str(e)}"},
        )

    # Read updated state after resuming
    try:
        updated_snapshot = await remix_graph.aget_state(config)
    except Exception:
        updated_snapshot = None

    updated_values = updated_snapshot.values if updated_snapshot else {}

    # Determine final status
    status = updated_values.get("status", "unknown")
    final_output = updated_values.get("final_output") or None

    return DecisionResponse(
        thread_id=thread_id,
        status=status,
        final_output=final_output,
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET /remix/{thread_id}/stream (SSE)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@remix_router.get("/{thread_id}/stream")
async def stream_remix(thread_id: str):
    """Stream remix generation progress as Server-Sent Events.

    Uses LangGraph's astream_events to capture node execution events and
    forwards them as SSE with event types: 'progress' and 'interrupt'.
    """
    config = {"configurable": {"thread_id": thread_id}}

    # Verify thread exists
    try:
        state_snapshot = await remix_graph.aget_state(config)
    except Exception:
        raise HTTPException(
            status_code=404,
            detail={"error": f"Thread not found: {thread_id}"},
        )

    if state_snapshot is None or state_snapshot.values is None:
        raise HTTPException(
            status_code=404,
            detail={"error": f"Thread not found: {thread_id}"},
        )

    async def event_generator():
        """Generate SSE events from LangGraph stream."""
        try:
            async for event in remix_graph.astream_events(
                None, config=config, version="v2"
            ):
                event_type = event.get("event", "")
                event_data = event.get("data", {})

                # Forward custom progress events
                if event_type == "on_custom_event":
                    sse_data = json.dumps(event_data)
                    yield f"event: progress\ndata: {sse_data}\n\n"

                # Detect node start/end for progress tracking
                elif event_type == "on_chain_start":
                    name = event.get("name", "")
                    if name and name not in ("LangGraph", "__start__"):
                        sse_data = json.dumps({
                            "step": name,
                            "status": "in_progress",
                            "detail": f"Executing {name}...",
                        })
                        yield f"event: progress\ndata: {sse_data}\n\n"

                elif event_type == "on_chain_end":
                    name = event.get("name", "")
                    if name and name not in ("LangGraph", "__start__"):
                        # Check if this is an interrupt event
                        data_str = str(event_data)
                        if "interrupt" in data_str.lower():
                            interrupt_data = json.dumps({
                                "type": "review_remix",
                                "message": "Remix generation complete. Awaiting user review.",
                            })
                            yield f"event: interrupt\ndata: {interrupt_data}\n\n"
                        else:
                            sse_data = json.dumps({
                                "step": name,
                                "status": "complete",
                                "detail": f"{name} completed",
                            })
                            yield f"event: progress\ndata: {sse_data}\n\n"

        except Exception as e:
            error_data = json.dumps({"error": str(e)})
            yield f"event: error\ndata: {error_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
