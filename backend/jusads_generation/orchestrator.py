"""
orchestrator.py
────────────────
LangGraph orchestration for the Agentic Ad Studio (Req 4, 5, 6, 7, 8).

This module is the *only* orchestration concern (Req 1.1): it detects the media
types requested in a chat message, resolves the backend-authoritative platform
sizing rules, fans the work out to the four **independent** Media Agents, bridges
each produced ad to the compliance pipeline, and persists the assistant turn and
final canvas state. It never implements an individual agent, HTTP routing, or the
chat-persistence storage itself — those live in their own modules.

Two surfaces are exposed:

* A compiled ``StateGraph(GenerationState)`` (:func:`build_graph`) that encodes the
  routing topology exactly as the design describes — ``load_history →
  resolve_platform → detect_intent`` then a **fan-out** to
  ``text_node``/``image_node``/``audio_node``/``video_node`` that are connected
  *only* through a ``collect`` join (never agent→agent, so no agent can consume
  another's output — Req 5.2, 5.3), followed by ``persist_assistant`` and
  ``emit_pipeline_state``.
* :func:`run_generation`, an async generator used by ``routes/generation.py`` that
  drives those same steps while streaming SSE lines incrementally as each node
  progresses.

All state is a ``TypedDict`` (``GenerationState``); no dataclasses are used
(Req 1.3). Every external call is wrapped in ``try/except`` with the
``[Orchestrator]`` logging prefix and graceful degradation per steering.
"""

import asyncio
import json
import logging
import time
import uuid
from typing import AsyncGenerator, Awaitable, Callable, Optional

from langgraph.graph import END, START, StateGraph

from shared.clients import gemini
from shared.prompts import ASSISTANT_CHAT_PROMPT

from .agents import audio_agent, image_agent, text_agent, video_agent
from .agents import video_v3_grid as video_v3_agent
from .agents.base import NODE_COORDS, AgentResult, load_guide, load_multimodal_reference
from .chat_store import ChatPersistenceError, create_chat_message, list_recent_chat_messages
from .compliance_bridge import run_compliance_for_ad, summarize_reasons
from .intent import detect_media_types
from .platform_rules import (
    MissingRuleError,
    UnsupportedPlatformError,
    normalize_platform,
    resolve_rule,
)
from .state import GeneratedAdRef, GenerationState, MediaType

logger = logging.getLogger(__name__)

# --- Constants ---------------------------------------------------------------

# The canonical media-agent dispatch table. Each entry is the independent
# ``generate(...)`` contract implementation for that media type (Req 5.1). The
# orchestrator only ever calls these through this map — it never wires one
# agent's output into another (Req 5.2, 5.3).
_AGENTS: dict[MediaType, Callable[..., Awaitable[AgentResult]]] = {
    "text": text_agent.generate,
    "image": image_agent.generate,
    "audio": audio_agent.generate,
    "video": video_agent.generate,
}

# Media types in a stable canonical ordering used for streaming/pipeline layout.
_MEDIA_ORDER: tuple[MediaType, ...] = ("text", "image", "audio", "video")

from shared.config import MODEL_TEXT
_GEMINI_MODEL = MODEL_TEXT

# Human-friendly labels surfaced in the in-progress SSE ``data`` payload.
_NODE_LABELS: dict[MediaType, str] = {
    "text": "Text Copy Agent",
    "image": "Image Creator Agent",
    "audio": "Audio Agent",
    "video": "Video Agent",
}

_CLARIFICATION_MESSAGE = (
    "I couldn't tell which kind of ad you'd like me to generate. "
    "Please name at least one supported media type — text, image, audio, or video — "
    "and I'll get started."
)


def _enrich_brief(user_message: str, context: dict) -> str:
    """Prepend generation context to the user brief so agents are aware of settings.

    Appends product name/category, target audience details, and language
    preference to the brief so every agent prompt receives them. Only non-empty
    fields are included. The user's original message remains the primary brief.

    Args:
        user_message: The raw user message.
        context: The ``gen_context`` dict from run_generation settings.

    Returns:
        An enriched brief string.
    """
    parts: list[str] = [user_message]
    meta: list[str] = []
    if context.get("product_name"):
        meta.append(f"Product/Brand: {context['product_name']}")
    if context.get("product_category"):
        meta.append(f"Category: {context['product_category']}")
    if context.get("target_ethnicity") and context["target_ethnicity"] != "all":
        meta.append(f"Target audience: {context['target_ethnicity'].title()} Malaysian")
    if context.get("age_group") and context["age_group"] != "all_ages":
        label_map = {"gen_z": "Gen Z (18-27)", "millennial": "Millennial (28-43)",
                     "gen_x": "Gen X (44-59)", "baby_boomer": "Baby Boomer (60+)"}
        meta.append(f"Age group: {label_map.get(context['age_group'], context['age_group'])}")
    if context.get("language") and context["language"] != "auto":
        lang_map = {"ms": "Bahasa Melayu", "en": "English", "zh": "Mandarin", "ta": "Tamil"}
        meta.append(f"Copy language: {lang_map.get(context['language'], context['language'])}")
    if context.get("market") and context["market"] != "malaysia":
        meta.append(f"Market: {context['market'].title()}")
    if meta:
        parts.append("[SETTINGS: " + " | ".join(meta) + "]")
    return "\n".join(parts)

_ASSISTANT_SYSTEM_INSTRUCTION = ASSISTANT_CHAT_PROMPT


# --- SSE helpers -------------------------------------------------------------


def _sse(payload: dict) -> str:
    """Serialize ``payload`` as a single SSE ``data:`` line.

    Args:
        payload: The JSON-serializable event body.

    Returns:
        The formatted ``data: {json}\\n\\n`` SSE line.
    """
    return f"data: {json.dumps(payload)}\n\n"


def _status_event(node: str, status: str, data: Optional[dict] = None) -> str:
    """Build a schema-conformant status SSE line (Req 4.5).

    Every status event carries a ``node``, a ``status`` (one of ``in-progress`` /
    ``completed`` / ``failed``), and a ``data`` object.

    Args:
        node: The node/media-type name the event pertains to.
        status: One of ``in-progress`` / ``completed`` / ``failed``.
        data: Optional structured payload for the event.

    Returns:
        The formatted SSE line.
    """
    return _sse({"node": node, "status": status, "data": data or {}})


# --- Step implementations (shared by the graph nodes and run_generation) -----


def _load_history_step(project_id: str, task_id: str) -> list[dict]:
    """Read the last 20 chat turns for conversational memory (Req 6.6, 6.8).

    Returns an empty list when no history exists, without raising.
    """
    try:
        history = list_recent_chat_messages(project_id, task_id)
        logger.info("[Orchestrator] Loaded %d prior chat turn(s)", len(history))
        return history
    except Exception as exc:  # noqa: BLE001 - memory is best-effort (Req 6.8)
        logger.error("[Orchestrator] Failed to load chat history: %s", exc)
        return []


def _detect_intent_step(user_message: str) -> list[MediaType]:
    """Detect requested media types, returning ``[]`` when none (Req 4.1, 4.3)."""
    detected = detect_media_types(user_message)
    logger.info("[Orchestrator] Detected media types: %s", detected)
    return detected


async def _load_reference_parts(reference_urls: list[str]) -> list:
    """Download optional multimodal reference assets as GenAI parts.

    Failures for individual references are swallowed (logged in the helper) so a
    bad reference never blocks generation (Req 3.2).
    """
    parts: list = []
    for ref_url in reference_urls or []:
        part = await load_multimodal_reference(ref_url)
        if part:
            parts.append(part)
    return parts


async def _stream_assistant_reply(
    user_message: str,
    history: list[dict],
    reference_parts: list,
) -> AsyncGenerator[tuple[str, str], None]:
    """Stream a short assistant reply, yielding ``(sse_line, text_chunk)`` pairs.

    The accumulated ``text_chunk`` values form the assistant turn persisted later.
    Any streaming failure degrades to a single fallback chunk so the run
    continues (Req 3.2).
    """
    from google.genai import types as genai_types

    contents = []
    for turn in history:
        role = turn.get("role", "user")
        # Gemini expects 'model' for assistant turns.
        gem_role = "model" if role == "assistant" else "user"
        contents.append(
            genai_types.Content(
                role=gem_role,
                parts=[genai_types.Part.from_text(text=turn.get("content", ""))],
            )
        )

    guides_summary = (
        "Available Guides:\n"
        f"- Poster Guide:\n{load_guide('image')}\n"
        f"- Short Video Guide:\n{load_guide('video')}"
    )
    latest_text = f"USER REQUEST: {user_message}\n---\n{guides_summary}"
    latest_parts = [genai_types.Part.from_text(text=latest_text)] + reference_parts
    contents.append(genai_types.Content(role="user", parts=latest_parts))

    try:
        response_stream = gemini.models.generate_content_stream(
            model=_GEMINI_MODEL,
            contents=contents,
            config=genai_types.GenerateContentConfig(
                system_instruction=_ASSISTANT_SYSTEM_INSTRUCTION
            ),
        )
        for chunk in response_stream:
            if chunk.text:
                yield _sse({"text": chunk.text}), chunk.text
    except Exception as exc:  # noqa: BLE001 - degrade gracefully (Req 3.2)
        logger.error("[Orchestrator] Assistant reply streaming failed: %s", exc)
        fallback = "\n(Generating your requested ad assets now...)\n"
        yield _sse({"text": fallback}), fallback


async def _generate_and_check(
    media_type: MediaType,
    *,
    brief: str,
    project_id: str,
    task_id: str,
    platform: str,
    reference_parts: list,
    skip_compliance: bool = False,
    gen_context: dict = None,
) -> GeneratedAdRef:
    """Resolve rules, invoke the agent, and bridge to compliance for one media type.

    Independence guarantee: this only ever receives the shared ``brief`` and the
    resolved platform ``rules`` — never another agent's output (Req 5.2, 5.3).
    Raises :class:`MissingRuleError` when no sizing rule exists so the caller can
    emit a ``failed`` event for this node only, without invoking the agent
    (Req 7.7). All other failures are captured as a ``failed`` ``GeneratedAdRef``.

    Args:
        media_type: The media type to generate.
        brief: The user's campaign brief.
        project_id: Owning project id.
        task_id: Owning task id.
        platform: The resolved, validated target platform.
        reference_parts: Optional multimodal reference parts.
        skip_compliance: When True, skip compliance and mark as non-final.

    Returns:
        A :class:`GeneratedAdRef` describing the produced ad and its compliance
        status.
    """
    # Resolve backend-authoritative sizing (Req 7.1); missing rule -> reject this
    # media generation only (Req 7.7). Propagated to the caller.
    rules = resolve_rule(platform, media_type)

    agent_generate = _AGENTS[media_type]
    result: AgentResult = await agent_generate(
        brief=brief,
        project_id=project_id,
        task_id=task_id,
        platform=platform,
        rules=rules,
        reference_parts=reference_parts,
    )

    # Compliance is now a SEPARATE step (run from the compliance page).
    # During generation, always mark as non-final to avoid slowing down ad creation.
    compliance = {
        "compliance_status": "non-final",
        "compliance_result": {"skipped": True, "reason": "compliance runs separately after generation"},
        "persisted": False,
    }

    return GeneratedAdRef(
        ad_id=result.get("ad_id") or "",
        media_type=media_type,
        platform=platform,
        s3_media_key=result.get("s3_media_key"),
        public_url=result.get("public_url"),
        caption=result.get("caption"),
        gen_status=result.get("status", "failed"),
        compliance_status=compliance.get("compliance_status", "non-final"),
        compliance_persisted=bool(compliance.get("persisted", False)),
        compliance_reasons=summarize_reasons(compliance.get("compliance_result") or {}),
    )


def _persist_assistant_step(
    project_id: str, task_id: str, content: str
) -> Optional[str]:
    """Persist the assistant turn to the chat store (Req 6.4).

    Returns an error message when persistence fails (the turn is preserved for
    retry inside the store), or ``None`` on success.
    """
    try:
        create_chat_message(project_id, task_id, "assistant", content or "")
        return None
    except ChatPersistenceError as exc:
        logger.error("[Orchestrator] Assistant turn persistence failed: %s", exc)
        return str(exc)
    except Exception as exc:  # noqa: BLE001 - never crash the stream on persistence
        logger.error("[Orchestrator] Unexpected assistant-persist error: %s", exc)
        return str(exc)


def _build_pipeline_state(
    *,
    user_message: str,
    current_state: dict,
    generated_ads: list[GeneratedAdRef],
) -> dict:
    """Assemble the final canvas ``pipeline_state`` for the frontend (Req 10.4).

    Preserves the existing ``nodes``/``edges``/``viewport`` shape the frontend
    canvas already parses, upserting one node per generated media type plus an
    input and output node, and attaches the structured ``generated_ads`` list.

    Args:
        user_message: The originating user request (shown on the input node).
        current_state: The task's prior canvas state.
        generated_ads: The refs produced this run.

    Returns:
        The new ``pipeline_state`` dict.
    """
    nodes: list[dict] = list(current_state.get("nodes") or [])
    edges: list[dict] = list(current_state.get("edges") or [])
    viewport = current_state.get("viewport") or {"panX": 0, "panY": 0, "zoom": 1}

    # Stagger offset based on current run size
    run_offset_x = len([n for n in nodes if n.get("type") == "input"]) * 80
    run_offset_y = len([n for n in nodes if n.get("type") == "input"]) * 100

    def create_new_node(ntype: str, label: str) -> str:
        node_id = f"node-{ntype}-{uuid.uuid4().hex[:6]}"
        base_x, base_y = NODE_COORDS.get(ntype, (200, 200))
        
        # Calculate staggering offset
        count = sum(1 for n in nodes if n.get("type") == ntype)
        x = base_x + (count * 40) + run_offset_x
        y = base_y + (count * 50) + run_offset_y

        nodes.append(
            {
                "id": node_id,
                "type": ntype,
                "x": x,
                "y": y,
                "label": label,
                "props": {},
                "status": "idle",
                "output": None,
                "error": None,
            }
        )
        return node_id

    # We only connect/create input & output nodes if there are multiple ads or if it's video
    is_single_image = len(generated_ads) == 1 and generated_ads[0]["media_type"] == "image"
    should_connect = not is_single_image

    input_id = None
    output_id = None

    if should_connect:
        input_id = create_new_node("input", "User Request")
        for node in nodes:
            if node["id"] == input_id:
                node["output"] = user_message
                node["status"] = "done"
        output_id = create_new_node("output", "Campaign Output")

    ads_by_type = {ad["media_type"]: ad for ad in generated_ads}

    for media_type in _MEDIA_ORDER:
        ad = ads_by_type.get(media_type)
        if ad is None:
            continue
        node_id = create_new_node(media_type, f"{media_type.capitalize()} Agent")
        for node in nodes:
            if node["id"] == node_id:
                node["status"] = "done" if ad["gen_status"] == "completed" else "error"
                node["output"] = (
                    ad.get("caption") if ad["media_type"] == "text"
                    else ad.get("public_url") or ad.get("caption")
                )
                node["error"] = None if ad["gen_status"] == "completed" else "generation failed"
                node["props"] = {
                    "compliance_status": ad["compliance_status"],
                    "prompt_used": user_message,
                }
        
        # Connect nodes only if we should_connect and input/output exist
        if should_connect and input_id and output_id:
            if not any(e.get("from") == input_id and e.get("to") == node_id for e in edges):
                edges.append({"id": str(uuid.uuid4()), "from": input_id, "to": node_id})
            if not any(e.get("from") == node_id and e.get("to") == output_id for e in edges):
                edges.append({"id": str(uuid.uuid4()), "from": node_id, "to": output_id})

    if should_connect and output_id:
        for node in nodes:
            if node["id"] == output_id:
                node["status"] = "done"
                node["output"] = json.dumps(
                    {ad["media_type"]: ad.get("public_url") for ad in generated_ads}
                )

    return {
        "nodes": nodes,
        "edges": edges,
        "viewport": viewport,
        "generated_ads": [dict(ad) for ad in generated_ads],
    }


# --- LangGraph topology (Req 4, 5) -------------------------------------------


def _node_load_history(state: GenerationState) -> dict:
    """Graph node: populate conversational memory (Req 6.6)."""
    return {
        "history": _load_history_step(state["project_id"], state["task_id"])
    }


def _node_resolve_platform(state: GenerationState) -> dict:
    """Graph node: resolve/validate the target platform (Req 7.4–7.6)."""
    return {"target_platform": normalize_platform(state.get("target_platform"))}


def _node_detect_intent(state: GenerationState) -> dict:
    """Graph node: classify requested media types (Req 4.1, 4.3)."""
    detected = _detect_intent_step(state["user_message"])
    return {
        "detected_media_types": detected,
        "needs_clarification": not detected,
    }


def _route_after_intent(state: GenerationState) -> list[str]:
    """Conditional router: fan out to detected media nodes, else clarify (Req 4.2, 4.4).

    Returns the list of media node names to run in parallel — the fan-out is
    connected *only* to the ``collect`` join downstream, never agent→agent, so no
    agent can consume another's output (Req 5.2, 5.3).
    """
    detected = state.get("detected_media_types") or []
    if not detected:
        return ["clarify"]
    return [f"{media_type}_node" for media_type in _MEDIA_ORDER if media_type in detected]


def _make_media_node(media_type: MediaType) -> Callable[[GenerationState], Awaitable[dict]]:
    """Build an async graph node for one media type.

    The node invokes the media agent independently and bridges to compliance,
    appending its result to ``generated_ads``. A failing node records a failure
    and does not affect sibling nodes (Req 4.6, 5.5, 5.6).
    """

    async def _node(state: GenerationState) -> dict:
        try:
            ref = await _generate_and_check(
                media_type,
                brief=state["user_message"],
                project_id=state["project_id"],
                task_id=state["task_id"],
                platform=state["target_platform"],
                reference_parts=[],
                gen_context=state.get("gen_context") or {},
            )
        except MissingRuleError as exc:
            logger.warning("[Orchestrator] %s rejected (missing rule): %s", media_type, exc)
            return {"generated_ads": []}
        except Exception as exc:  # noqa: BLE001 - isolate node failure (Req 5.6)
            logger.error("[Orchestrator] %s node failed: %s", media_type, exc)
            return {"generated_ads": []}
        return {"generated_ads": [ref]}

    return _node


def _node_clarify(state: GenerationState) -> dict:
    """Graph node: mark that clarification is needed (Req 4.3)."""
    return {"needs_clarification": True}


def _node_collect(state: GenerationState) -> dict:
    """Join node: no-op merge point downstream of the media fan-out."""
    return {}


def _node_persist_assistant(state: GenerationState) -> dict:
    """Graph node: persist the assistant turn (Req 6.4)."""
    content = _CLARIFICATION_MESSAGE if state.get("needs_clarification") else "Generation complete."
    _persist_assistant_step(state["project_id"], state["task_id"], content)
    return {}


def _node_emit_pipeline_state(state: GenerationState) -> dict:
    """Graph node: assemble the final canvas pipeline state (Req 10.4)."""
    pipeline_state = _build_pipeline_state(
        user_message=state["user_message"],
        current_state=state.get("pipeline_state") or {},
        generated_ads=state.get("generated_ads") or [],
    )
    return {"pipeline_state": pipeline_state}


def build_graph():
    """Build and compile the generation ``StateGraph(GenerationState)``.

    Encodes the design topology: ``load_history → resolve_platform →
    detect_intent`` then a fan-out to the four media nodes joined *only* through
    ``collect`` (never agent→agent — Req 5.2, 5.3), then ``persist_assistant`` and
    ``emit_pipeline_state``. Returns the compiled graph.
    """
    graph = StateGraph(GenerationState)

    graph.add_node("load_history", _node_load_history)
    graph.add_node("resolve_platform", _node_resolve_platform)
    graph.add_node("detect_intent", _node_detect_intent)
    graph.add_node("clarify", _node_clarify)
    graph.add_node("collect", _node_collect)
    graph.add_node("persist_assistant", _node_persist_assistant)
    graph.add_node("emit_pipeline_state", _node_emit_pipeline_state)
    for media_type in _MEDIA_ORDER:
        graph.add_node(f"{media_type}_node", _make_media_node(media_type))

    graph.add_edge(START, "load_history")
    graph.add_edge("load_history", "resolve_platform")
    graph.add_edge("resolve_platform", "detect_intent")

    # Fan-out: detect_intent -> each detected media node, or -> clarify.
    graph.add_conditional_edges(
        "detect_intent",
        _route_after_intent,
        {
            **{f"{mt}_node": f"{mt}_node" for mt in _MEDIA_ORDER},
            "clarify": "clarify",
        },
    )

    # Media nodes join ONLY at the collect node (never agent->agent).
    for media_type in _MEDIA_ORDER:
        graph.add_edge(f"{media_type}_node", "collect")

    graph.add_edge("clarify", "persist_assistant")
    graph.add_edge("collect", "persist_assistant")
    graph.add_edge("persist_assistant", "emit_pipeline_state")
    graph.add_edge("emit_pipeline_state", END)

    compiled = graph.compile()
    logger.info("[Orchestrator] Generation StateGraph compiled")
    return compiled


# Compile once at import so the topology is validated on module load.
generation_graph = build_graph()


# --- Streaming entrypoint (Req 4.5) ------------------------------------------


async def run_generation(
    project_id: str,
    task_id: str,
    user_message: str,
    reference_urls: list[str],
    target_platform: Optional[str],
    current_state: dict,
    skip_compliance: bool = False,
    video_v3: bool = False,
    target_ethnicity: Optional[str] = None,
    age_group: Optional[str] = None,
    market: Optional[str] = None,
    language: Optional[str] = None,
    product_name: Optional[str] = None,
    product_category: Optional[str] = None,
    gender: Optional[str] = None,
    force_media_types: Optional[list[str]] = None,
) -> AsyncGenerator[str, None]:
    """Run the generation orchestration, streaming SSE lines.

    Entry point used by ``routes/generation.py``. Drives the graph steps while
    yielding SSE ``data:`` lines incrementally:

    * ``{text}`` — streamed assistant reply chunks.
    * ``{node, status, data}`` — per-node status events where ``status`` is one of
      ``in-progress`` / ``completed`` / ``failed`` (Req 4.5).
    * ``{pipeline_state}`` — the final canvas state (Req 10.4).
    * ``{error}`` — a terminal error indication (e.g. an unsupported platform).

    Behavior:

    * Reads the last 20 chat turns for conversational memory (Req 6.6, 6.8).
    * Resolves/validates the platform, defaulting to Instagram and rejecting
      unsupported values (Req 7.4–7.6).
    * Detects requested media types; when none are found it emits a clarification
      and invokes no agent (Req 4.3).
    * Routes only to the detected media agents (Req 4.2, 4.4), each generating
      independently (Req 5.2, 5.3), bridging to compliance before final (Req 8.1).
    * A failing media node emits a ``failed`` event and does not stop siblings
      (Req 4.6, 5.6).
    * Persists the assistant turn (Req 6.4) and emits the final pipeline state.

    Args:
        project_id: Owning project id.
        task_id: Owning task id.
        user_message: The user's chat message / brief.
        reference_urls: Optional reference asset URLs.
        target_platform: The requested platform (defaults to Instagram).
        current_state: The task's prior canvas ``pipeline_state``.
        skip_compliance: When True, skip the compliance check (faster iteration).
        video_v3: When True, video generation uses the V3 Character Grid Pipeline
            (Director → Character Sheet → Scene Grid → Gemini Omni full-clip → Assemble)
            instead of the single-clip V1 path.
        target_ethnicity: Target audience for conditional localization
            (``malay``/``chinese``/``indian``/``all``). Halal rules apply only
            for Malay/Muslim; Indian avoids beef; etc.

    Yields:
        SSE ``data:`` lines as described above.
    """
    logger.info(
        "[Orchestrator] Starting generation run (project=%s, task=%s)",
        project_id,
        task_id,
    )

    # 1. Resolve/validate the platform up front — reject before any agent runs
    #    when the value is unsupported (Req 7.6).
    try:
        platform = normalize_platform(target_platform)
    except UnsupportedPlatformError as exc:
        logger.warning("[Orchestrator] Rejecting run: %s", exc)
        yield _sse({"error": str(exc)})
        return

    # 2. Load conversational memory (Req 6.6, 6.8).
    history = _load_history_step(project_id, task_id)

    # Build the generation context from all settings (threaded to agents/prompts).
    gen_context = {
        "target_ethnicity": target_ethnicity or "all",
        "age_group": age_group or "all_ages",
        "market": market or "malaysia",
        "language": language or "auto",
        "product_name": product_name or "",
        "product_category": product_category or "",
        "gender": gender or "female",
    }

    # 3. Prepare optional multimodal references and stream the assistant reply.
    reference_parts = await _load_reference_parts(reference_urls)
    assistant_reply = ""
    async for sse_line, text_chunk in _stream_assistant_reply(
        user_message, history, reference_parts
    ):
        assistant_reply += text_chunk
        yield sse_line

    # 4. Detect intent (Req 4.1).
    yield _status_event("orchestrator", "in-progress", {"message": "Analyzing campaign channels..."})
    if force_media_types:
        # Guided mode: bypass intent detection — we know exactly what to generate.
        detected = [mt for mt in _MEDIA_ORDER if mt in force_media_types]
        logger.info("[Orchestrator] Using forced media types: %s", detected)
    else:
        detected = _detect_intent_step(user_message)

    generated_ads: list[GeneratedAdRef] = []
    v3_ran = False  # Track if V3 pipeline handled video (it emits its own pipeline_state)

    # 5a. No media type detected -> request clarification, invoke no agent (Req 4.3).
    if not detected:
        logger.info("[Orchestrator] No media type detected; requesting clarification")
        yield _sse({"text": _CLARIFICATION_MESSAGE})
        yield _status_event(
            "orchestrator", "completed", {"needs_clarification": True}
        )
        assistant_reply = (assistant_reply + "\n" + _CLARIFICATION_MESSAGE).strip()
    else:
        # 5b. Fan out to each detected media agent (Req 4.2, 4.4). Each runs
        #     independently; a failure does not stop siblings (Req 4.6, 5.6).
        for media_type in _MEDIA_ORDER:
            if media_type not in detected:
                continue
            label = _NODE_LABELS[media_type]
            yield _status_event(
                media_type, "in-progress", {"message": f"Starting {label}...", "phase": "init", "platform": platform}
            )

            # Phase 1: Resolve platform rules
            try:
                rules = resolve_rule(platform, media_type)
            except MissingRuleError as exc:
                logger.warning("[Orchestrator] %s rejected (missing rule): %s", media_type, exc)
                yield _status_event(
                    media_type, "failed",
                    {"media_type": media_type, "error": str(exc)},
                )
                continue

            yield _status_event(
                media_type, "in-progress", {"message": f"{label}: Generating content...", "phase": "generating"}
            )

            # Special path: Video V2 planning mode. Instead of running the whole
            # V3 Grid Pipeline: Full character-consistent multi-scene video.
            # Director -> Character Sheet -> Scene Grid -> Slice -> Gemini Omni -> Assemble.
            # Each step emits its own canvas nodes via SSE.
            if media_type == "video" and video_v3:
                v3_ran = True
                yield _status_event(
                    "video", "in-progress",
                    {"message": "V3 Grid Pipeline: Director planning...", "phase": "v3_grid"},
                )
                try:
                    async for sse_line in video_v3_agent.run_grid_pipeline(
                        brief=_enrich_brief(user_message, gen_context),
                        project_id=project_id,
                        task_id=task_id,
                        character_description=gen_context.get("product_name", ""),
                        product_description=gen_context.get("product_category", ""),
                        video_duration_sec=30.0,
                        width=1080,
                        height=1920,
                        target_ethnicity=gen_context.get("target_ethnicity", "all"),
                    ):
                        yield sse_line
                except Exception as exc:  # noqa: BLE001
                    logger.error("[Orchestrator] V3 Grid Pipeline failed: %s", exc)
                    yield _status_event(
                        "video", "failed",
                        {"media_type": "video", "error": str(exc), "phase": "v3_failed"},
                    )
                continue

            # Phase 2: Run the agent
            try:
                agent_generate = _AGENTS[media_type]
                result: AgentResult = await agent_generate(
                    brief=_enrich_brief(user_message, gen_context),
                    project_id=project_id,
                    task_id=task_id,
                    platform=platform,
                    rules=rules,
                    reference_parts=reference_parts,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("[Orchestrator] %s agent crashed: %s", media_type, exc)
                yield _status_event(
                    media_type, "failed",
                    {"media_type": media_type, "error": str(exc), "phase": "generation_failed"},
                )
                continue

            if result.get("status") == "completed":
                yield _status_event(
                    media_type, "in-progress", {"message": f"{label}: Uploading to S3...", "phase": "uploaded"}
                )

            # Compliance removed from generation flow — runs separately.
            compliance = {
                "compliance_status": "non-final",
                "compliance_result": {"skipped": True, "reason": "compliance runs separately"},
                "persisted": False,
            }

            # Build the final ref
            ref = GeneratedAdRef(
                ad_id=result.get("ad_id") or "",
                media_type=media_type,
                platform=platform,
                s3_media_key=result.get("s3_media_key"),
                public_url=result.get("public_url"),
                caption=result.get("caption"),
                gen_status=result.get("status", "failed"),
                compliance_status=compliance.get("compliance_status", "non-final"),
                compliance_persisted=bool(compliance.get("persisted", False)),
                compliance_reasons=summarize_reasons(compliance.get("compliance_result") or {}),
            )

            generated_ads.append(ref)
            status = "completed" if ref["gen_status"] == "completed" else "failed"
            yield _status_event(
                media_type,
                status,
                {
                    "ad_id": ref["ad_id"],
                    "media_type": ref["media_type"],
                    "platform": ref["platform"],
                    "public_url": ref["public_url"],
                    "caption": ref["caption"],
                    "compliance_status": ref["compliance_status"],
                    "compliance_persisted": ref["compliance_persisted"],
                    "compliance_reasons": ref["compliance_reasons"],
                },
            )

    # 6. Persist the assistant turn (Req 6.4). Surface an error event on failure
    #    without discarding the turn (the store enqueues it for retry — Req 6.7).
    persist_error = _persist_assistant_step(
        project_id, task_id, assistant_reply or "Generation complete."
    )
    if persist_error:
        yield _sse({"error": f"chat persistence failed: {persist_error}"})

    # 7. Emit the final canvas state (Req 10.4).
    # Skip for V3 — it emits its own pipeline_state with V3-specific nodes.
    if not v3_ran:
        pipeline_state = _build_pipeline_state(
            user_message=user_message,
            current_state=current_state or {},
            generated_ads=generated_ads,
        )
        yield _sse({"pipeline_state": pipeline_state})
    logger.info(
        "[Orchestrator] Generation run complete (%d ad(s) produced, v3=%s)", len(generated_ads), v3_ran
    )


# --- Video V2: execute an approved plan (Continue button) --------------------


async def run_video_plan_execution(
    project_id: str,
    task_id: str,
    plan: dict,
    current_state: dict,
    skip_compliance: bool = False,
) -> AsyncGenerator[str, None]:
    """Execute an approved video plan (V3 Grid or legacy V2).

    Detects the plan version and routes accordingly:
    - V3 (pipeline_version: "v3_grid"): calls video_v3_agent.execute_production()
    - Legacy V2: calls video_v2_agent.execute_video_plan() [if still available]

    Args:
        project_id: Owning project id.
        task_id: Owning task id.
        plan: The approved plan dict (from the ``video_plan`` SSE event).
        current_state: The task's prior canvas ``pipeline_state``.
        skip_compliance: When True, skip the compliance check.

    Yields:
        SSE ``data:`` lines with progress and pipeline_state.
    """
    pipeline_version = plan.get("pipeline_version", "v2")

    if pipeline_version == "v3_grid":
        # V3 Grid Pipeline — Stage 3: Execute Production
        logger.info("[Orchestrator] Executing V3 Grid plan %s", plan.get("plan_id"))

        yield _status_event(
            "video", "in-progress",
            {"message": "V3: Generating full video with Gemini Omni...", "phase": "v3_production"},
        )

        # Build the assets dict from the plan (frame_urls should be persisted on the plan)
        assets = {
            "plan_id": plan.get("plan_id"),
            "frame_urls": plan.get("frame_urls", []),
            "scenes": plan.get("scenes", []),
        }

        # If frame_urls not in plan directly, try to reconstruct from pipeline_state
        if not assets["frame_urls"]:
            # Look for frame_urls in the current state's node props
            for node in (current_state.get("nodes") or []):
                if node.get("props", {}).get("frame_urls"):
                    assets["frame_urls"] = node["props"]["frame_urls"]
                    break

        if not assets["frame_urls"]:
            yield _sse({"error": "No frame URLs found in plan — regenerate assets first"})
            return

        async for event in video_v3_agent.execute_production(
            assets=assets,
            project_id=project_id,
            task_id=task_id,
            brief=plan.get("product_integration", ""),
        ):
            yield event

        return

    # -- Legacy V2 path (fallback) -----------------------------------------
    logger.info(
        "[Orchestrator] Executing Video plan %s (project=%s, task=%s)",
        plan.get("plan_id"), project_id, task_id,
    )
    platform = normalize_platform(plan.get("platform"))

    yield _status_event(
        "video", "in-progress",
        {"message": "Rendering approved scenes with Gemini Omni...", "phase": "generating"},
    )

    # V2 is deprecated — if an old V2 plan somehow arrives, inform the user.
    logger.warning("[Orchestrator] Legacy V2 plan received — V2 is deprecated, use V3")
    yield _sse({"error": "Video V2 is deprecated. Please regenerate using V3 Grid Pipeline."})
    return
