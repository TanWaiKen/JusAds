"""
state.py
────────
LangGraph orchestration state for the Agentic Ad Studio generation module.

All state is defined as ``TypedDict`` (never dataclasses), per project steering
conventions for LangGraph pipelines (Req 1.3).
"""

from typing import Literal, Optional, TypedDict

# Supported media output types (Req 4.1).
MediaType = Literal["text", "image", "audio", "video"]

# Per-node streaming status values emitted over the SSE stream (Req 4.5).
NodeStatus = Literal["in-progress", "completed", "failed"]


class GeneratedAdRef(TypedDict):
    """A pointer to one persisted Generated_Ad plus its live compliance status."""

    ad_id: str  # generated_ads.id
    media_type: MediaType
    platform: str
    s3_media_key: Optional[str]
    public_url: Optional[str]
    caption: Optional[str]
    gen_status: str  # 'completed' | 'failed'
    compliance_status: str  # 'final-compliant' | 'final-non-compliant' | 'non-final'
    compliance_persisted: bool  # False when result returned but not saved (Req 8.4)
    compliance_reasons: dict  # compact "why" surfaced to the UI (risk, explanation, etc.)


class GenerationState(TypedDict):
    """LangGraph state channel for the generation orchestrator graph."""

    # Inputs
    project_id: str
    task_id: str
    user_message: str
    reference_urls: list[str]
    target_platform: str  # resolved, validated (Req 7.4-7.6)
    # Memory
    history: list[dict]  # last 20 turns (Req 6.6)
    # Routing
    detected_media_types: list[MediaType]  # (Req 4.1)
    needs_clarification: bool  # (Req 4.3)
    # Outputs
    generated_ads: list[GeneratedAdRef]
    # Canvas
    pipeline_state: dict  # nodes/edges/viewport for the frontend
    # Streaming sink (events appended by nodes, drained by the route)
    events: list[dict]
