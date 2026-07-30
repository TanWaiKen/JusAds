"""
routes/generation.py
────────────────────
FastAPI routes for ad generation chat with streaming SSE and S3 presigned URL uploads.

This module is the HTTP-surface concern only (Req 1.1). It preserves every existing
endpoint contract (Req 2) and delegates generation to the LangGraph orchestrator in
``jusads_generation`` (Req 1.5, 1.6). Chat turns are persisted through
``jusads_generation.chat_store`` (Req 6.3, 6.7); one additive endpoint exposes the
stored Chat_History (Req 11.5).
"""

import asyncio
import uuid
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from shared.supabase_client import SupabaseComplianceStore
from shared.s3_client import delete_object, get_public_url, normalize_s3_key
from shared.auth import Principal, get_current_principal
from shared.authorization import require_project_access
from jusads_generation import run_generation, run_video_plan_execution
from jusads_generation.video_plan_validation import is_usable_v3_plan
from jusads_generation.chat_store import (
    ChatPersistenceError,
    create_chat_message,
    list_chat_history,
)
from jusads_generation.publish import (
    AdNotFoundError,
    CompliancePublishBlockedError,
    PublishError,
    publish_ad,
)
from jusads_generation.distribution import (
    distribute_ad,
    DistributionError,
    AccountNotConfiguredError,
)
from jusads_generation.caption_agent import (
    generate_platform_caption,
    normalize_platform_caption,
)

logger = logging.getLogger(__name__)

from shared.clients import gemini
from shared.config import MODEL_TEXT


# ─── Video-plan continuation detection ────────────────────────────────────────

import re as _re

def _sync_pipeline_nodes_to_generated_ads(pipeline_state: dict):
    """Synchronize pipeline node outputs into generated_ads relational table."""
    if not pipeline_state:
        return
    nodes = pipeline_state.get("nodes")
    if not isinstance(nodes, list):
        return
    
    from shared.clients import supabase as sb
    
    for node in nodes:
        if not isinstance(node, dict):
            continue
        output_url = node.get("output")
        ad_id = node.get("props", {}).get("ad_id")
        if isinstance(output_url, str) and ad_id:
            try:
                row_resp = sb.table("generated_ads").select("metadata").eq("id", ad_id).limit(1).execute()
                rows = row_resp.data or []
                if rows:
                    metadata = rows[0].get("metadata") or {}
                    if metadata.get("s3_url") != output_url:
                        metadata["s3_url"] = output_url
                        sb.table("generated_ads").update({"metadata": metadata}).eq("id", ad_id).execute()
                        logger.info("[Generation] Synced output URL to generated_ads for ad_id=%s", ad_id)
            except Exception as e:
                logger.error("[Generation] Sync to generated_ads failed for ad_id=%s: %s", ad_id, e)

_CONTINUATION_PHRASES: set[str] = {
    "continue",
    "proceed",
    "go ahead",
    "render it",
    "render video",
    "render the video",
    "generate the video",
    "generate video",
    "create the video",
    "create video",
    "continue video",
    "start rendering",
    "yes generate it",
    "yes, generate it",
    "yes generate",
    "yes",
    "ok",
    "okay",
    "do it",
    "lets go",
    "let's go",
}


def _is_video_plan_continuation(message: str) -> bool:
    """Return True when the message is a narrow, deterministic continuation command.

    Only matches messages whose entire meaningful content is one of a fixed set
    of confirmation/continuation phrases.  General chat that merely contains the
    word *continue* is NOT matched.
    """
    normalised = _re.sub(r"[^\w\s']", "", message.lower()).strip()
    return normalised in _CONTINUATION_PHRASES


def _is_usable_v3_plan(plan: object) -> bool:
    """Return True when ``plan`` is a dict representing a ready V3 storyboard."""
    return is_usable_v3_plan(plan)

router = APIRouter(prefix="/api", tags=["generation"])

_store: SupabaseComplianceStore | None = None


def init_generation(store: SupabaseComplianceStore | None):
    """Injects the Supabase client store at app startup."""
    global _store
    _store = store


class ChatRequest(BaseModel):
    message: str
    guided_mode: bool = False
    design_type: Optional[str] = None
    guided_inputs: Optional[dict] = None
    reference_urls: List[str] = []
    target_platform: Optional[str] = None
    skip_compliance: bool = False
    target_ethnicity: Optional[str] = None
    age_group: Optional[str] = None  # gen_z|millennial|gen_x|baby_boomer|all_ages
    market: Optional[str] = None  # malaysia|singapore
    language: Optional[str] = None  # ms|en|zh|ta|auto
    product_name: Optional[str] = None
    product_category: Optional[str] = None
    gender: Optional[str] = None  # male|female|mixed
    # Creative strategy for the localize plan (Director hook/pacing style).
    # meme_shock | culture_anchor | problem_punchline | testimonial_burst | speaker_led | product_hero
    creative_style: Optional[str] = None
    # Easy Mode fields (Req 14.1, 14.5)
    revision_instruction: Optional[str] = None
    advanced_overrides: Optional[dict] = None
    parent_ad_id: Optional[str] = None
    parent_asset_url: Optional[str] = None




class ExecuteVideoPlanRequest(BaseModel):
    """Body for executing an approved V3 storyboard plan (Continue button)."""

    plan: dict  # the plan dict from the `video_plan` SSE event (possibly edited)
    skip_compliance: bool = False


import asyncio

# In-memory store for background generation tasks. Maps run_id -> asyncio.Queue of SSE chunks.
# When the client disconnects and reconnects, they poll the queue by run_id.
_active_runs: dict[str, asyncio.Queue] = {}
_run_complete: dict[str, bool] = {}


@router.post("/projects/{project_id}/tasks/{task_id}/chat")
async def chat_with_generation_agent(project_id: str, task_id: str, body: ChatRequest, principal: Principal = Depends(get_current_principal)) -> StreamingResponse:
    """Send a message to the AI generation agent, streaming response text and returning the final state.

    The generation runs as a BACKGROUND TASK — if the client disconnects mid-stream,
    the pipeline continues running and persists results to Supabase. When the user
    comes back, the frontend fetches the persisted generated_ads + pipeline_state.
    """
    if not _store:
        return JSONResponse(status_code=503, content={"error": "Persistence store is unavailable"})
    require_project_access(_store, project_id, principal, write=True)

    task = _store.get_task_detail(project_id=project_id, task_id=task_id)
    if not task:
        return JSONResponse(status_code=404, content={"error": "Task not found"})

    current_pipeline_state = task.get("pipeline_state") or {
        "nodes": [],
        "edges": [],
        "viewport": {"panX": 0, "panY": 0, "zoom": 1}
    }

    # ── Video-plan continuation shortcut ──────────────────────────────────
    # When the user sends a short confirmation/continuation phrase AND the
    # persisted pipeline_state already contains a usable V3 storyboard, skip
    # normal generation and execute the existing plan directly.
    saved_plan = current_pipeline_state.get("video_plan")
    if _is_video_plan_continuation(body.message) and _is_usable_v3_plan(saved_plan):
        logger.info(
            "[Generation] Continuation command detected — executing saved V3 plan (task=%s)",
            task_id,
        )

        # Persist the user continuation turn.
        try:
            create_chat_message(project_id, task_id, "user", body.message)
        except ChatPersistenceError as pe:
            logger.error("[SSE] User continuation turn persistence failed: %s", pe)

        # Persist an assistant acknowledgement turn.
        ack_message = (
            "Got it — I'm using the approved storyboard and starting video rendering now. "
            "This may take a minute while Gemini Omni generates each scene."
        )
        try:
            create_chat_message(project_id, task_id, "assistant", ack_message)
        except ChatPersistenceError as pe:
            logger.error("[SSE] Assistant acknowledgement persistence failed: %s", pe)

        # Run the plan execution in a background task (same pattern as /execute-video-plan).
        run_id = f"cont_{project_id}_{task_id}_{uuid.uuid4().hex[:6]}"
        queue: asyncio.Queue = asyncio.Queue()
        _active_runs[run_id] = queue
        _run_complete[run_id] = False

        async def _run_continuation_background():
            """Execute the saved V3 plan triggered by a chat continuation command."""
            final_state = None
            try:
                # Emit the assistant acknowledgement as a text event first
                await queue.put(f"data: {json.dumps({'text': ack_message})}\n\n")

                async for chunk in run_video_plan_execution(
                    project_id=project_id,
                    task_id=task_id,
                    plan=saved_plan,
                    current_state=current_pipeline_state,
                    skip_compliance=body.skip_compliance,
                ):
                    await queue.put(chunk)

                    if "pipeline_state" in chunk:
                        try:
                            data = json.loads(chunk.replace("data: ", "").strip())
                            if "pipeline_state" in data:
                                final_state = data["pipeline_state"]
                                _sync_pipeline_nodes_to_generated_ads(final_state)
                                _store.update_task_pipeline(
                                    project_id=project_id,
                                    task_id=task_id,
                                    status="in_progress",
                                    pipeline_state=final_state,
                                )
                        except Exception as pe:
                            logger.warning("[BG-Cont] Error parsing/persisting state: %s", pe)
            except Exception as err:
                logger.error("[BG-Cont] Video plan continuation error: %s", err)
                await queue.put(f"data: {json.dumps({'error': 'Video rendering failed. Please try again.'})}\n\n")

            if final_state:
                try:
                    _store.update_task_pipeline(
                        project_id=project_id,
                        task_id=task_id,
                        status="completed",
                        pipeline_state=final_state,
                    )
                    logger.info("[BG-Cont] Persisted final continuation pipeline state.")
                except Exception as se:
                    logger.error("[BG-Cont] Failed to persist final state: %s", se)

            _run_complete[run_id] = True
            await queue.put(None)
            await asyncio.sleep(30)
            _active_runs.pop(run_id, None)
            _run_complete.pop(run_id, None)

        asyncio.create_task(_run_continuation_background())

        async def _continuation_event_generator():
            try:
                while True:
                    try:
                        chunk = await asyncio.wait_for(queue.get(), timeout=120)
                    except asyncio.TimeoutError:
                        yield f"data: {json.dumps({'type': 'ping'})}\n\n"
                        continue
                    if chunk is None:
                        break
                    yield chunk
            except asyncio.CancelledError:
                logger.info("[SSE-Cont] Client disconnected — background task continues")

        return StreamingResponse(
            _continuation_event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Encoding": "none",
            },
        )

    # When the message looks like a continuation but NO usable plan exists,
    # give a helpful response instead of silently generating something new.
    if _is_video_plan_continuation(body.message) and not _is_usable_v3_plan(saved_plan):
        logger.info("[Generation] Continuation command received but no saved plan (task=%s)", task_id)
        no_plan_message = (
            "I'd love to continue, but there's no approved storyboard waiting to be rendered. "
            "Please describe what you'd like to create, and I'll plan a new video for you!"
        )
        try:
            create_chat_message(project_id, task_id, "user", body.message)
        except ChatPersistenceError:
            pass
        try:
            create_chat_message(project_id, task_id, "assistant", no_plan_message)
        except ChatPersistenceError:
            pass

        async def _no_plan_generator():
            yield f"data: {json.dumps({'text': no_plan_message})}\n\n"

        return StreamingResponse(
            _no_plan_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Encoding": "none",
            },
        )

    # A revision must be tied to a persisted asset in this task. The server
    # owns this lookup so a client cannot create cross-project parent links.
    revision_parent: dict | None = None
    if body.parent_ad_id or body.parent_asset_url:
        try:
            from shared.clients import supabase as sb

            query = (
                sb.table("generated_ads")
                .select("id, media_type, prompt_used, caption, s3_media_key, metadata")
                .eq("project_id", project_id)
                .eq("task_id", task_id)
                .eq("asset_role", "output")
            )
            if body.parent_ad_id:
                query = query.eq("id", body.parent_ad_id)
            elif body.parent_asset_url:
                query = query.contains("metadata", {"s3_url": body.parent_asset_url})
            rows = query.limit(1).execute().data or []
            revision_parent = rows[0] if rows else None
            if not revision_parent:
                return JSONResponse(status_code=404, content={"error": "Selected source version was not found in this task"})
            parent_url = (revision_parent.get("metadata") or {}).get("s3_url")
            if parent_url and parent_url not in body.reference_urls:
                body.reference_urls.append(parent_url)
        except Exception as exc:
            logger.error("[Generation] Failed to load revision source: %s", exc)
            return JSONResponse(status_code=500, content={"error": "Could not load the selected source version"})

    # -- Guided mode: assemble the effective message from form inputs --
    # Easy Mode detection: if revision_instruction or advanced_overrides are present,
    # use the Easy Mode prompt assembly path (Req 13.3, 14.1, 14.5).
    easy_mode_provenance: dict | None = None

    is_easy_mode = body.guided_mode and body.design_type and body.guided_inputs and (
        body.revision_instruction is not None or body.advanced_overrides is not None
    )

    if is_easy_mode:
        try:
            from jusads_generation.easy_mode_prompts import assemble_easy_mode_prompt
            from jusads_generation.guided_prompts import DESIGN_TYPE_TO_MEDIA

            effective_message, easy_mode_provenance = assemble_easy_mode_prompt(
                design_type=body.design_type,
                form_inputs=body.guided_inputs,
                revision_instruction=body.revision_instruction,
                advanced_overrides=body.advanced_overrides,
            )
            forced_media = DESIGN_TYPE_TO_MEDIA.get(body.design_type)
            logger.info(
                "[Generation] Easy Mode detected (design_type=%s, has_revision=%s)",
                body.design_type,
                body.revision_instruction is not None,
            )
        except ValueError as ve:
            logger.warning("[Generation] Invalid Easy Mode request: %s", ve)
            return JSONResponse(
                status_code=422,
                content={"error": "The guided campaign inputs are invalid. Please review the form and try again."},
            )
    elif body.guided_mode and body.design_type and body.guided_inputs:
        try:
            from jusads_generation.guided_prompts import assemble_guided_message, DESIGN_TYPE_TO_MEDIA

            effective_message = assemble_guided_message(body.design_type, body.guided_inputs)
            forced_media = DESIGN_TYPE_TO_MEDIA.get(body.design_type)
        except ValueError as ve:
            logger.warning("[Generation] Invalid guided request: %s", ve)
            return JSONResponse(
                status_code=422,
                content={"error": "The guided campaign inputs are invalid. Please review the form and try again."},
            )
    else:
        effective_message = body.message
        forced_media = None

    if revision_parent:
        effective_message = (
            f"{effective_message}\n\n[VERSION REVISION]\n"
            f"Edit the supplied source version; preserve its product, layout, visual identity and useful details unless the feedback explicitly changes them. "
            f"This output is a new version of asset {revision_parent['id']}."
        )

    # Create a unique run_id for this generation
    run_id = f"{project_id}_{task_id}_{uuid.uuid4().hex[:6]}"
    queue: asyncio.Queue = asyncio.Queue()
    _active_runs[run_id] = queue
    _run_complete[run_id] = False

    # Persist user turn BEFORE spawning background task
    # For guided mode, persist a human-readable summary instead of the full assembled prompt
    if body.guided_mode and body.design_type and body.guided_inputs:
        chat_display_message = (
            f"[Guided: {body.design_type}] "
            f"{body.guided_inputs.get('product_name', '')} — "
            f"{body.guided_inputs.get('key_message', '')}"
        )
    else:
        chat_display_message = body.message

    try:
        create_chat_message(project_id, task_id, "user", chat_display_message)
    except ChatPersistenceError as pe:
        logger.error("[SSE] User turn persistence failed: %s", pe)

    # Background task: runs the full generation pipeline independently of the HTTP connection.
    async def _run_generation_background():
        """Execute generation in the background, pushing SSE chunks to the queue.

        Persists pipeline_state incrementally after each media agent completes,
        so even if the client disconnects, partial results are saved.
        """
        final_state = None
        try:
            async for chunk in run_generation(
                project_id=project_id,
                task_id=task_id,
                user_message=effective_message,
                reference_urls=body.reference_urls,
                target_platform=body.target_platform,
                current_state=current_pipeline_state,
                skip_compliance=body.skip_compliance,
                target_ethnicity=body.target_ethnicity,
                age_group=body.age_group,
                market=body.market,
                language=body.language,
                product_name=body.product_name,
                product_category=body.product_category,
                gender=body.gender,
                generation_mode="easy" if body.guided_mode else "advanced",
                guided_inputs=body.guided_inputs,
                parent_ad_id=str(revision_parent["id"]) if revision_parent else None,
                parent_asset_url=parent_url if revision_parent else None,
                revision_feedback=(body.revision_instruction or body.message) if revision_parent else None,
                force_media_types=forced_media,
                creative_style=body.creative_style,
            ):
                # Push chunk to queue for any listening SSE client
                await queue.put(chunk)

                # Persist pipeline_state incrementally (not just at end)
                if "pipeline_state" in chunk:
                    try:
                        clean_json = chunk.replace("data: ", "").strip()
                        data = json.loads(clean_json)
                        if "pipeline_state" in data:
                            final_state = data["pipeline_state"]
                            _sync_pipeline_nodes_to_generated_ads(final_state)
                            # Save intermediate state to DB
                            _store.update_task_pipeline(
                                project_id=project_id,
                                task_id=task_id,
                                status="in_progress",
                                pipeline_state=final_state,
                            )
                    except Exception as pe:
                        logger.warning("[BG] Error parsing/persisting state chunk: %s", pe)

        except Exception:
            logger.exception("[BG] Generation background task failed task=%s", task_id)
            await queue.put(
                f"data: {json.dumps({'error': 'Generation failed. Please try again.'})}\n\n"
            )

        # Final persistence — mark as completed
        if final_state:
            try:
                # Task-level provenance makes the correct surface recoverable
                # after a refresh: Easy tasks return to the Easy Results gallery.
                final_state = {
                    **final_state,
                    "generation": {
                        "mode": "easy" if body.guided_mode else "advanced",
                        "design_type": body.design_type if body.guided_mode else None,
                    },
                }
                _store.update_task_pipeline(
                    project_id=project_id,
                    task_id=task_id,
                    status="completed",
                    pipeline_state=final_state,
                )
                logger.info("[BG] Persisted final generation pipeline state to Supabase.")
            except Exception as se:
                logger.error("[BG] Failed to persist final state: %s", se)

        # -- Easy Mode provenance persistence (Req 17.1, 17.2) --
        # Store the provenance record in generated_ads.metadata.easy_mode namespace
        if easy_mode_provenance and final_state:
            try:
                from shared.clients import supabase as sb

                # Extract ad IDs from the pipeline_state generated_ads list
                generated_ads_list = final_state.get("generated_ads") or []
                ad_ids = [
                    ad.get("ad_id") for ad in generated_ads_list
                    if ad.get("ad_id") and ad.get("gen_status") == "completed"
                ]

                for ad_id in ad_ids:
                    # Fetch current metadata to merge (don't overwrite existing metadata)
                    row_resp = (
                        sb.table("generated_ads")
                        .select("metadata")
                        .eq("id", ad_id)
                        .limit(1)
                        .execute()
                    )
                    rows = row_resp.data or []
                    current_metadata = (rows[0].get("metadata") or {}) if rows else {}

                    # Merge easy_mode provenance into the metadata namespace
                    current_metadata["easy_mode"] = {
                        "template_type": body.design_type,
                        "revision_instruction": body.revision_instruction,
                        "provenance": easy_mode_provenance,
                    }

                    sb.table("generated_ads").update(
                        {"metadata": current_metadata}
                    ).eq("id", ad_id).execute()

                logger.info(
                    "[Generation] Easy Mode provenance stored for %d ad(s)",
                    len(ad_ids),
                )
            except Exception as prov_err:
                logger.error(
                    "[Generation] Failed to persist Easy Mode provenance: %s",
                    prov_err,
                )

        # Signal completion
        _run_complete[run_id] = True
        await queue.put(None)  # Sentinel: generation done

        # Cleanup after a delay (give client time to finish reading)
        await asyncio.sleep(30)
        _active_runs.pop(run_id, None)
        _run_complete.pop(run_id, None)

    # Spawn the background task — runs independently of this HTTP request
    asyncio.create_task(_run_generation_background())

    # SSE stream: reads from the queue and yields to the client.
    # If client disconnects, the background task keeps running.
    async def event_generator():
        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(queue.get(), timeout=120)
                except asyncio.TimeoutError:
                    # Keep-alive ping so the connection isn't dropped by proxies
                    yield f"data: {json.dumps({'type': 'ping'})}\n\n"
                    continue

                if chunk is None:
                    # Background task finished
                    break
                yield chunk
        except asyncio.CancelledError:
            # Client disconnected — background task continues running
            logger.info("[SSE] Client disconnected for run %s — background task continues", run_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Encoding": "none",
        }
    )


@router.post("/projects/{project_id}/tasks/{task_id}/execute-video-plan")
async def execute_video_plan_endpoint(
    project_id: str,
    task_id: str,
    body: ExecuteVideoPlanRequest,
    principal: Principal = Depends(get_current_principal),
) -> StreamingResponse:
    """Render an approved, complete V3 storyboard plan into a final video (SSE).

    Runs as a background task, so rendering continues if the client disconnects.
    """
    if not _store:
        return JSONResponse(status_code=503, content={"error": "Persistence store is unavailable"})
    require_project_access(_store, project_id, principal, write=True)

    task = _store.get_task_detail(project_id=project_id, task_id=task_id)
    if not task:
        return JSONResponse(status_code=404, content={"error": "Task not found"})

    current_pipeline_state = task.get("pipeline_state") or {
        "nodes": [], "edges": [], "viewport": {"panX": 0, "panY": 0, "zoom": 1}
    }
    if not _is_usable_v3_plan(body.plan):
        return JSONResponse(
            status_code=422,
            content={
                "error": (
                    "A complete V3 storyboard is required. Regenerate the scene grid and "
                    "sliced frames before starting paid rendering."
                )
            },
        )

    run_id = f"v3_{project_id}_{task_id}_{uuid.uuid4().hex[:6]}"
    queue: asyncio.Queue = asyncio.Queue()
    _active_runs[run_id] = queue
    _run_complete[run_id] = False

    async def _run_v3_background():
        """Background task for V3 storyboard production."""
        final_state = None
        try:
            async for chunk in run_video_plan_execution(
                project_id=project_id,
                task_id=task_id,
                plan=body.plan,
                current_state=current_pipeline_state,
                skip_compliance=body.skip_compliance,
            ):
                await queue.put(chunk)

                if "pipeline_state" in chunk:
                    try:
                        data = json.loads(chunk.replace("data: ", "").strip())
                        if "pipeline_state" in data:
                            final_state = data["pipeline_state"]
                            _sync_pipeline_nodes_to_generated_ads(final_state)
                            _store.update_task_pipeline(
                                project_id=project_id, task_id=task_id,
                                status="in_progress", pipeline_state=final_state,
                            )
                    except Exception as pe:
                        logger.warning("[BG-V3] Error parsing/persisting state: %s", pe)
        except Exception:
            logger.exception("[BG-V3] Video production failed task=%s", task_id)
            await queue.put(
                f"data: {json.dumps({'error': 'Video production failed. Please try again.'})}\n\n"
            )

        if final_state:
            try:
                _store.update_task_pipeline(
                    project_id=project_id, task_id=task_id,
                    status="completed", pipeline_state=final_state,
                )
                logger.info("[BG-V3] Persisted final V3 pipeline state.")
            except Exception as se:
                logger.error("[BG-V3] Failed to persist final V3 state: %s", se)

        _run_complete[run_id] = True
        await queue.put(None)
        await asyncio.sleep(30)
        _active_runs.pop(run_id, None)
        _run_complete.pop(run_id, None)

    asyncio.create_task(_run_v3_background())

    async def event_generator():
        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(queue.get(), timeout=120)
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'ping'})}\n\n"
                    continue
                if chunk is None:
                    break
                yield chunk
        except asyncio.CancelledError:
            logger.info("[SSE-V3] Client disconnected — background task continues")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "Content-Encoding": "none"},
    )


@router.get("/projects/{project_id}/tasks/{task_id}/generated-ads")
async def get_generated_ads(project_id: str, task_id: str, principal: Principal = Depends(get_current_principal)) -> JSONResponse:
    """Return all generated ads for a task (newest first) so the UI can repopulate on reload."""
    if not _store:
        return JSONResponse(status_code=503, content={"error": "Persistence store is unavailable"})
    require_project_access(_store, project_id, principal)
    if not _store.get_task_detail(project_id=project_id, task_id=task_id):
        return JSONResponse(status_code=404, content={"error": "Task not found"})

    try:
        from shared.clients import supabase as sb

        response = (
            sb.table("generated_ads")
            .select("id, media_type, platform, s3_media_key, status, metadata, compliance_status, compliance_result, prompt_used, caption")
            .eq("project_id", project_id)
            .eq("task_id", task_id)
            .eq("asset_role", "output")
            .order("created_at", desc=True)
            .execute()
        )
        rows = response.data or []
        # Map to the shape the frontend expects (matches pipeline_state.generated_ads).
        ads = []
        for row in rows:
            metadata = row.get("metadata") or {}
            s3_media_key = row.get("s3_media_key")
            public_url = metadata.get("s3_url")

            # Fallback if s3_url is missing in metadata but we have a media key
            if not public_url and s3_media_key:
                try:
                    from config import S3_BUCKET_NAME, AWS_REGION
                    if S3_BUCKET_NAME and AWS_REGION:
                        public_url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{s3_media_key}"
                except ImportError:
                    pass

            ads.append({
                "ad_id": str(row.get("id", "")),
                "media_type": row.get("media_type", ""),
                "platform": row.get("platform", ""),
                "s3_media_key": s3_media_key,
                "public_url": public_url,
                "aspect_ratio": metadata.get("aspect_ratio"),
                "caption": row.get("caption") or (row.get("prompt_used") if row.get("media_type") == "text" else None),
                "gen_status": row.get("status", "completed"),
                "compliance_status": row.get("compliance_status", "non-final"),
                "compliance_reasons": row.get("compliance_result") or {},
                "revision_edit": metadata.get("revision_edit"),
            })
        return JSONResponse(content={"ads": ads})
    except Exception:
        logger.exception("Failed to fetch generated ads for task %s", task_id)
        return JSONResponse(status_code=503, content={"error": "Generated ads are temporarily unavailable"})


@router.get("/projects/{project_id}/easy-results")
async def get_easy_results(project_id: str, principal: Principal = Depends(get_current_principal)) -> JSONResponse:
    """Return recent output-bearing tasks so Easy Mode can resume a specific run."""
    if not _store:
        return JSONResponse(status_code=503, content={"error": "Persistence store is unavailable"})
    require_project_access(_store, project_id, principal)

    try:
        from shared.clients import supabase as sb

        response = (
            sb.table("generated_ads")
            .select("task_id, media_type, platform, generation_mode, created_at")
            .eq("project_id", project_id)
            .eq("asset_role", "output")
            .not_.is_("task_id", "null")
            .order("created_at", desc=True)
            .limit(24)
            .execute()
        )
        latest_by_task: dict[str, dict] = {}
        for row in response.data or []:
            task_id = row.get("task_id")
            if task_id and task_id not in latest_by_task:
                latest_by_task[str(task_id)] = row
        return JSONResponse(content={"results": list(latest_by_task.values())[:6]})
    except Exception:
        logger.exception("Failed to fetch Easy Mode results for project %s", project_id)
        return JSONResponse(status_code=503, content={"error": "Easy Mode results are temporarily unavailable"})


@router.get("/projects/{project_id}/tasks/{task_id}/chat-history")
async def get_chat_history(project_id: str, task_id: str, principal: Principal = Depends(get_current_principal)) -> JSONResponse:
    """Return the full ordered Chat_History for a task (Req 11.5).

    Responds with 200 ``{messages: [...]}`` (oldest → newest) on success, 404 when the
    task does not exist for the project (Req 2.7), and 503 when the persistence store is
    unavailable (Req 2.6).
    """
    if not _store:
        return JSONResponse(status_code=503, content={"error": "Persistence store is unavailable"})
    require_project_access(_store, project_id, principal)

    task = _store.get_task_detail(project_id=project_id, task_id=task_id)
    if not task:
        return JSONResponse(status_code=404, content={"error": "Task not found"})

    messages = list_chat_history(project_id, task_id)
    return JSONResponse(content={"messages": messages})


@router.post("/projects/{project_id}/tasks/{task_id}/ads/{ad_id}/publish")
async def publish_generated_ad(project_id: str, task_id: str, ad_id: str, principal: Principal = Depends(get_current_principal)) -> JSONResponse:
    """Approve and publish a Generated_Ad — the human-in-the-loop gate (§ 4).

    Flips ``generated_ads.status`` to ``published`` once the owner has reviewed
    the output. Returns 200 with the post-publish state, 404 when the ad does
    not exist for the project, 409 when the ad failed compliance (blocked), and
    503 when the persistence store is unavailable.
    """
    if not _store:
        return JSONResponse(status_code=503, content={"error": "Persistence store is unavailable"})
    require_project_access(_store, project_id, principal, write=True)

    if not _store.get_task_detail(project_id=project_id, task_id=task_id):
        return JSONResponse(status_code=404, content={"error": "Task not found"})

    try:
        from shared.clients import supabase as sb

        ad_response = (
            sb.table("generated_ads")
            .select("id")
            .eq("id", ad_id)
            .eq("project_id", project_id)
            .eq("task_id", task_id)
            .limit(1)
            .execute()
        )
        if not ad_response.data:
            return JSONResponse(status_code=404, content={"error": "Generated ad not found"})
    except Exception:
        logger.exception("[Publish] Could not verify ad scope project=%s task=%s", project_id, task_id)
        return JSONResponse(status_code=503, content={"error": "Publishing is temporarily unavailable"})

    try:
        result = publish_ad(project_id, ad_id)
    except AdNotFoundError as e:
        logger.info("[Publish] %s", e)
        return JSONResponse(status_code=404, content={"error": "Generated ad not found"})
    except CompliancePublishBlockedError as e:
        logger.warning("[Publish] Blocked: %s", e)
        return JSONResponse(status_code=409, content={"error": "Ad failed compliance review and cannot be published"})
    except PublishError as e:
        logger.error("[Publish] Store error: %s", e)
        return JSONResponse(status_code=503, content={"error": "Publishing is temporarily unavailable"})

    # Publishing is also where a shareable caption is created. This avoids ever
    # treating the internal image-generation prompt as platform post content.
    caption = ""
    try:
        from shared.clients import supabase as sb

        response = (
            sb.table("generated_ads")
            .select("platform, media_type, prompt_used, metadata")
            .eq("id", ad_id)
            .eq("project_id", project_id)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if rows:
            ad = rows[0]
            caption = generate_platform_caption(
                platform=ad.get("platform") or "instagram",
                media_type=ad.get("media_type") or "image",
                prompt_used=ad.get("prompt_used"),
                metadata=ad.get("metadata") or {},
            )
            sb.table("generated_ads").update(
                {"caption": caption, "updated_at": datetime.now(timezone.utc).isoformat()}
            ).eq("id", ad_id).execute()
    except Exception as exc:  # Approval succeeded; caption generation must not undo it.
        logger.warning("[Publish] Caption generation failed for %s: %s", ad_id, exc)

    payload = dict(result)
    payload["caption"] = caption
    return JSONResponse(content=payload)


class DistributionTarget(BaseModel):
    """One selected connected account for a distribution request."""

    platform: str
    account_id: Optional[str] = None


def _normalize_distribution_accounts(payload: dict) -> list[dict]:
    """Map Zernio's documented account response to the picker contract."""
    raw_accounts = payload.get("accounts") or payload.get("data") or []
    if isinstance(raw_accounts, dict):
        raw_accounts = raw_accounts.get("accounts") or raw_accounts.get("data") or []

    accounts: list[dict] = []
    for raw in raw_accounts if isinstance(raw_accounts, list) else []:
        if not isinstance(raw, dict):
            continue
        platform = raw.get("platform")
        account_id = raw.get("_id")
        if not isinstance(platform, str) or not isinstance(account_id, str) or not account_id:
            logger.warning(
                "[Distribution] Skipping a Zernio account with a missing documented _id or platform."
            )
            continue
        username = raw.get("username")
        accounts.append({
            "id": account_id,
            "platform": platform.lower(),
            "label": f"@{username}" if isinstance(username, str) and username else f"{platform.title()} account",
        })
    return accounts


@router.get("/distribution/accounts")
async def list_distribution_accounts(
    principal: Principal = Depends(get_current_principal),
) -> JSONResponse:
    """Return normalized connected Zernio accounts for multi-account posting."""
    try:
        from shared.zernio_client import get_connected_accounts
        from routes.profile import _get_stored_user_zernio_key

        # A connected social account is private to the authenticated person.
        # Never accept an email query parameter here: it allowed account discovery
        # against another user's stored Zernio key.
        api_key = _get_stored_user_zernio_key(principal.email)
        if not api_key:
            return JSONResponse(content={"accounts": [], "message": "Connect your Zernio account in Profile before distributing."})
        payload = await get_connected_accounts(api_key=api_key)
        accounts = _normalize_distribution_accounts(payload)
        return JSONResponse(content={
            "accounts": accounts,
            "message": None if accounts else "No active social accounts were returned by Zernio. Check the connection in Profile.",
        })
    except Exception as exc:
        logger.warning("[Distribution] Account discovery failed subject=%s: %s", principal.subject, exc)
        return JSONResponse(status_code=503, content={"error": "Connected accounts are temporarily unavailable."})


class DistributeRequest(BaseModel):
    """Body for distributing a published ad to a social platform."""

    platform: Optional[str] = None  # legacy single-target request
    account_id: Optional[str] = None
    caption: Optional[str] = None
    destinations: List[DistributionTarget] = Field(default_factory=list)


@router.post("/projects/{project_id}/tasks/{task_id}/ads/{ad_id}/distribute")
async def distribute_generated_ad(
    project_id: str,
    task_id: str,
    ad_id: str,
    body: DistributeRequest,
    principal: Principal = Depends(get_current_principal),
) -> JSONResponse:
    """Distribute a published ad to a social platform via Zernio.

    Only ads with ``status = published`` can be distributed. Returns 200 with the
    distribution result, 404 when the ad does not exist, 409 when the ad isn't
    published yet, and 503 when the distribution service is unavailable.
    """
    if not _store:
        return JSONResponse(status_code=503, content={"error": "Persistence store is unavailable"})
    require_project_access(_store, project_id, principal, write=True)

    # Verify the ad belongs to the requested task and is ready to post.  The
    # authenticated user's own Zernio connection is used, including for a
    # shared project; a collaborator must not inherit the owner's social key.
    try:
        from shared.clients import supabase as sb
        from routes.profile import _get_stored_user_zernio_key

        api_key = _get_stored_user_zernio_key(principal.email)
        if not api_key:
            return JSONResponse(
                status_code=409,
                content={"error": "Connect your Zernio account in Profile before distributing."},
            )

        resp = sb.table("generated_ads").select("id, status, platform, metadata, media_type, prompt_used, caption").eq("id", ad_id).eq("project_id", project_id).eq("task_id", task_id).limit(1).execute()
        rows = resp.data or []
        if not rows:
            return JSONResponse(status_code=404, content={"error": f"Ad {ad_id} not found"})
        ad_row = rows[0]
        if ad_row.get("status") != "published":
            return JSONResponse(status_code=409, content={"error": "Ad must be published before distributing"})
    except Exception:
        logger.exception("[Distribution] Failed to verify ad project_id=%s task_id=%s subject=%s", project_id, task_id, principal.subject)
        return JSONResponse(status_code=503, content={"error": "Could not verify the selected ad. Please try again."})

    metadata = ad_row.get("metadata") or {}
    media_url = metadata.get("s3_url") or ""
    if not media_url:
        return JSONResponse(status_code=409, content={"error": "Ad has no public media URL to distribute"})

    destinations = body.destinations or (
        [DistributionTarget(platform=body.platform, account_id=body.account_id)] if body.platform else []
    )
    if not destinations:
        return JSONResponse(status_code=422, content={"error": "Select at least one connected account"})

    results: list[dict] = []
    history = list(metadata.get("distribution_history") or [])
    for target in destinations:
        platform = target.platform.lower().strip()
        caption = (
            normalize_platform_caption(
                body.caption,
                platform=platform,
                media_type=ad_row.get("media_type", "image"),
            )
            if body.caption
            else generate_platform_caption(
                platform=platform,
                media_type=ad_row.get("media_type", "image"),
                prompt_used=ad_row.get("prompt_used"),
                metadata=metadata,
            )
        )
        try:
            result = distribute_ad(
                ad_id=ad_id,
                platform=platform,
                account_id=target.account_id,
                media_url=media_url,
                media_type=ad_row.get("media_type", "image"),
                api_key=api_key,
                caption=caption,
                metadata=metadata,
            )
            results.append(result)
            history.append({
                "platform": platform,
                "account_id": result.get("account_id"),
                "post_id": result.get("post_id"),
                "caption": caption,
                "status": "distributed",
                "distributed_at": datetime.now(timezone.utc).isoformat(),
            })
        except (AccountNotConfiguredError, DistributionError) as exc:
            logger.warning("[Distribution] %s delivery failed: %s", platform, exc)
            results.append({
                "platform": platform,
                "account_id": target.account_id,
                "status": "failed",
                "error": "Distribution failed for this selected account",
            })

    # The legacy columns retain the latest successful distribution, while the
    # JSON history preserves every selected platform/account in a batch.
    successes = [item for item in results if item.get("status") == "distributed"]
    try:
        update: dict = {"metadata": {**metadata, "distribution_history": history}}
        if successes:
            latest = successes[-1]
            update.update({
                "distributed_at": datetime.now(timezone.utc).isoformat(),
                "distribution_platform": latest.get("platform"),
                "distribution_post_id": latest.get("post_id"),
            })
        sb.table("generated_ads").update(update).eq("id", ad_id).execute()
    except Exception as exc:
        logger.warning("[Distribution] Could not persist distribution history for %s: %s", ad_id, exc)

    if not successes:
        return JSONResponse(status_code=503, content={"error": results[0].get("error", "Distribution failed"), "results": results})
    return JSONResponse(content={"status": "distributed", "results": results, "caption": successes[-1].get("caption", "")})





# --- Prompt Search (Phase F) --------------------------------------------------


@router.get("/search-prompt")
async def get_prompt_suggestions(query: str = "", top_k: int = 8, principal: Principal = Depends(get_current_principal)) -> JSONResponse:
    """Search the prompt vector database for templates matching the query.

    Returns top-K similar prompt templates from the Qdrant prompt_templates
    collection, ranked by cosine similarity. Used by the Prompt Library UI.

    Query params:
        query: The user's search text (what they want to generate).
        top_k: Number of results (default 8, max 20).
    """
    if not query.strip():
        return JSONResponse(content={"suggestions": []})

    top_k = max(1, min(20, top_k))
    
    # Fast Query Rewriting
    search_query = query.strip()
    try:
        from shared.clients import gemini
        from config import MODEL_TEXT
        if gemini:
            rewriting_prompt = f"""
            You are an expert search query optimizer. 
            The user typed this brief search query for an advertisement prompt template: "{search_query}"
            Rewrite this into a single, highly descriptive search phrase optimized for a vector database.
            Do not add quotes, markdown, or explanations. Just the rewritten query.
            """
            response = await asyncio.to_thread(
                gemini.models.generate_content,
                model=MODEL_TEXT,
                contents=rewriting_prompt
            )
            rewritten = (response.text or "").strip()
            if rewritten:
                search_query = rewritten
                logger.info("[PromptSearch] Query rewritten: '%s' -> '%s'", query.strip(), search_query)
    except Exception as e:
        logger.warning("[PromptSearch] Query rewriting failed, using original: %s", e)

    try:
        from jusads_generation.prompt_search.qdrant_store import search_prompts

        results = await asyncio.to_thread(search_prompts, search_query, top_k)
        return JSONResponse(content={"suggestions": results})
    except Exception:
        logger.exception("[PromptSearch] Search failed subject=%s", principal.subject)
        return JSONResponse(status_code=503, content={"error": "Prompt search is temporarily unavailable.", "suggestions": []})


@router.get("/prompt-recommendations")
async def get_prompt_recommendations(
    product_name: str = "",
    product_category: str = "",
    target_ethnicity: str = "all",
    platform: str = "tiktok",
    age_group: str = "all_ages",
    top_k: int = 6,
    principal: Principal = Depends(get_current_principal),
) -> JSONResponse:
    """Get personalized prompt recommendations based on the user's profile settings.

    Builds a query from the user's configured product/category/audience and
    searches the prompt vector DB for the most relevant templates — shown as a
    "Recommended for you" feed without the user needing to type anything.
    """
    product_description = ""
    target_platforms = [platform] if platform else []
    target_markets = [target_ethnicity] if target_ethnicity else []

    # Profile data is always scoped to the authenticated user.
    try:
        from shared.clients import supabase as sb
        resp = sb.table("business_profiles").select("*").eq("owner_email", principal.email).execute()
        if resp.data:
            profile = resp.data[0]
            product_name = profile.get("company_name") or product_name
            product_category = profile.get("product_category") or product_category
            product_description = profile.get("product_description") or ""
            target_platforms = profile.get("target_platforms") or target_platforms
            target_markets = profile.get("target_markets") or target_markets
    except Exception:
        logger.warning("[PromptRecommendations] Failed to fetch profile subject=%s", principal.subject)

    # Multi-Query HyDE Generation
    hyde_queries = []
    try:
        from shared.clients import gemini
        from config import MODEL_TEXT
        if gemini:
            hyde_prompt = f"""
            You are an expert marketing strategist and prompt engineer.
            Given the following user business profile:
            - Company/Product Name: {product_name}
            - Product Category: {product_category}
            - Product Description: {product_description}
            - Target Platforms: {', '.join(target_platforms) if isinstance(target_platforms, list) else platform}
            - Target Markets/Ethnicities: {', '.join(target_markets) if isinstance(target_markets, list) else target_ethnicity}
            - Audience Age Group: {age_group}
            
            Synthesize this user background and generate exactly 3 different hypothetical advertisement prompt templates.
            These templates should cover different visual styles (e.g. minimalist, vibrant, lifestyle).
            Return ONLY a valid JSON array of 3 strings. Do not include markdown blocks like ```json.
            Example: ["A vibrant lifestyle shot of...", "A minimalist studio flatlay...", "A dynamic fast-paced TikTok video ad..."]
            """
            response = await asyncio.to_thread(
                gemini.models.generate_content,
                model=MODEL_TEXT,
                contents=hyde_prompt
            )
            raw_text = (response.text or "").strip()
            if raw_text.startswith("```"):
                lines = raw_text.splitlines()
                if lines[0].startswith("```"): lines = lines[1:]
                if lines and lines[-1].startswith("```"): lines = lines[:-1]
                raw_text = "\n".join(lines).strip()
            hyde_queries = json.loads(raw_text)
            if not isinstance(hyde_queries, list):
                hyde_queries = []
    except Exception as e:
        logger.warning("[PromptRecommendations] Multi-Query HyDE failed: %s", e)
    
    # Fallback to standard rule-based string if LLM failed
    if not hyde_queries:
        parts = []
        if product_name: parts.append(f"advertisement for {product_name}")
        if platform: parts.append(f"{platform} ad creative")
        query = " ".join(parts) or "creative advertisement poster social media"
        hyde_queries = [query]

    top_k = max(1, min(12, top_k))

    try:
        from jusads_generation.prompt_search.qdrant_store import search_prompts
        
        # Parallel Vector Search using ThreadPool
        tasks = [asyncio.to_thread(search_prompts, q, top_k * 2) for q in hyde_queries]
        search_results_list = await asyncio.gather(*tasks)
        
        # Reciprocal Rank Fusion (RRF)
        fused_scores = {}
        prompt_data = {}
        for results in search_results_list:
            for rank, result in enumerate(results):
                title = result.get("title", "")
                if not title: continue
                # RRF Formula: 1 / (rank + k) where k is traditionally 60
                score = 1.0 / (rank + 60)
                fused_scores[title] = fused_scores.get(title, 0.0) + score
                prompt_data[title] = result
        
        # Sort by fused score
        sorted_titles = sorted(fused_scores.keys(), key=lambda t: fused_scores[t], reverse=True)
        final_results = [prompt_data[t] for t in sorted_titles[:top_k]]

        return JSONResponse(content={"query_used": hyde_queries, "recommendations": final_results})
    except Exception:
        logger.exception("[PromptRecommendations] Failed subject=%s", principal.subject)
        return JSONResponse(status_code=503, content={"error": "Prompt recommendations are temporarily unavailable.", "recommendations": []})


@router.get("/user-assets")
async def get_user_assets(limit: int = 50, principal: Principal = Depends(get_current_principal)) -> JSONResponse:
    """Fetch all generated ads across the user's projects for the Assets page.

    Returns completed ads with their media URLs, sorted newest first.
    """
    if not _store:
        return JSONResponse(status_code=503, content={"error": "Persistence store is unavailable"})

    try:
        from shared.clients import supabase as sb

        # Get user's projects first.
        projects_resp = sb.table("projects").select("id").eq("owner_email", principal.email).execute()
        project_ids = [str(r["id"]) for r in (projects_resp.data or [])]

        if not project_ids:
            return JSONResponse(content={"assets": []})

        # Fetch generated ads across all user projects.
        ads_resp = (
            sb.table("generated_ads")
            .select("id, media_type, platform, s3_media_key, status, asset_role, metadata, prompt_used, caption, created_at, project_id, task_id")
            .in_("project_id", project_ids)
            .eq("status", "completed")
            .in_("asset_role", ["output", "reference"])
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

        assets = []
        for row in (ads_resp.data or []):
            metadata = row.get("metadata") or {}
            s3_key = normalize_s3_key(str(row.get("s3_media_key") or ""))
            public_url = metadata.get("s3_url") or ""
            if not public_url and s3_key:
                public_url = get_public_url(s3_key)
            asset_role = str(row.get("asset_role") or "output")
            is_reference = asset_role == "reference" or bool(metadata.get("is_reference", False))
            filename = str(metadata.get("filename") or (s3_key.rsplit("/", 1)[-1] if s3_key else ""))
            assets.append({
                "id": str(row.get("id", "")),
                "media_type": row.get("media_type", ""),
                "platform": row.get("platform", ""),
                "public_url": public_url,
                "s3_key": s3_key,
                "filename": filename,
                "asset_role": asset_role,
                "prompt_used": row.get("prompt_used", "") or row.get("caption", ""),
                "status": row.get("status", ""),
                "created_at": row.get("created_at", ""),
                "project_id": str(row.get("project_id", "")),
                "task_id": str(row.get("task_id", "")),
                "is_reference": is_reference,
            })

        return JSONResponse(content={"assets": assets})
    except Exception:
        logger.exception("[UserAssets] Failed subject=%s", principal.subject)
        return JSONResponse(status_code=503, content={"error": "Assets are temporarily unavailable"})


@router.delete("/user-assets/{asset_id}")
async def delete_user_asset(asset_id: str, principal: Principal = Depends(get_current_principal)) -> JSONResponse:
    """Permanently remove one owner-authorized asset and its S3 object."""
    if not _store:
        return JSONResponse(status_code=503, content={"error": "Persistence store is unavailable"})
    try:
        from shared.clients import supabase as sb
        response = sb.table("generated_ads").select("id, project_id, s3_media_key").eq("id", asset_id).limit(1).execute()
        rows = response.data or []
        if not rows:
            return JSONResponse(status_code=404, content={"error": "Asset not found"})
        asset = rows[0]
        require_project_access(_store, str(asset.get("project_id") or ""), principal, write=True)
        s3_key = normalize_s3_key(str(asset.get("s3_media_key") or ""))
        sb.table("generated_ads").delete().eq("id", asset_id).execute()
        if s3_key:
            try:
                delete_object(s3_key)
            except Exception:
                logger.exception("[UserAssets] Database asset removed but S3 cleanup failed asset=%s", asset_id)
                return JSONResponse(status_code=202, content={"status": "deleted", "cleanup": "pending"})
        return JSONResponse(content={"status": "deleted"})
    except HTTPException:
        raise
    except Exception:
        logger.exception("[UserAssets] Delete failed subject=%s", principal.subject)
        return JSONResponse(status_code=503, content={"error": "Asset could not be deleted"})


class AutofillRequest(BaseModel):
    user_prompt: str
    current_design_type: Optional[str] = None
    current_values: dict[str, str] = Field(default_factory=dict)


_AUTOFILL_DESIGN_TYPES = {
    "image_poster",
    "carousel",
    "video_ad",
    "text_copy",
    "audio_ad",
}
_AUTOFILL_FIELDS = {
    "product_name",
    "key_message",
    "target_audience",
    "platform",
    "brand_tone",
    "visual_style",
    "color_palette",
    "slide_count",
    "copy_length",
    "call_to_action",
    "language",
    "video_duration",
    "creative_mode",
    "opening_hook",
    "code_switching",
    "audio_duration",
    "voice_tone",
    "background_music_style",
    "forbidden_claims",
    "brand_rules",
    "compliance_constraints",
}


def _fallback_autofill(body: AutofillRequest) -> dict:
    """Keep Easy Mode usable when the language model is rate-limited."""
    text = body.user_prompt.strip()
    lowered = text.lower()
    selected = body.current_design_type if body.current_design_type in _AUTOFILL_DESIGN_TYPES else ""
    if any(token in lowered for token in ("video", "tiktok", "reel", "shorts")):
        selected = "video_ad"
    elif any(token in lowered for token in ("audio ad", "radio", "podcast", "voice spot")):
        selected = "audio_ad"
    elif any(token in lowered for token in ("carousel", "slides", "swipe")):
        selected = "carousel"
    elif any(token in lowered for token in ("caption", "ad copy", "text only", "copywriting")):
        selected = "text_copy"
    elif not selected:
        selected = "image_poster"

    values = {
        key: str(value)
        for key, value in body.current_values.items()
        if key in _AUTOFILL_FIELDS and value is not None
    }
    if text:
        values["key_message"] = text
    if "tiktok" in lowered:
        values["platform"] = "tiktok"
    elif "instagram" in lowered or "reel" in lowered:
        values["platform"] = "instagram"
    elif "shopee" in lowered:
        values["platform"] = "shopee"
    if _re.search(r"[\u3400-\u9fff]", text) or any(
        token in lowered for token in ("chinese", "mandarin", "中文", "华语")
    ):
        values["language"] = "Chinese"
    elif any(token in lowered for token in ("bahasa", "malay", "melayu")):
        values["language"] = "Bahasa Melayu"
    if selected == "video_ad":
        values.setdefault("creative_mode", "voiceover")
        values.setdefault("opening_hook", "Sudden action → product reveal")
        values.setdefault("video_duration", "15s")
        values.setdefault("call_to_action", "Learn More")

    return {
        "selected_design_type": selected,
        "selectedTemplate": selected,
        "form_values": values,
        "formValues": values,
        "assistant_message": (
            "I selected the closest format and filled what I could from your request. "
            "Please review the highlighted form, especially the product name, claims, CTA, and safety rules."
        ),
        "missing_fields": [
            field for field in ("product_name", "key_message")
            if not values.get(field, "").strip()
        ],
        "reference_recommendations": (
            ["Product photo", "Character or logo", "Shop / location"]
            if selected == "video_ad"
            else ["Product photo", "Brand logo"]
        ),
        "used_fallback": True,
    }


def _normalize_autofill_payload(data: dict, body: AutofillRequest) -> dict:
    raw_type = str(
        data.get("selected_design_type")
        or data.get("selectedTemplate")
        or body.current_design_type
        or "image_poster"
    )
    aliases = {
        "poster": "image_poster",
        "story": "image_poster",
        "video": "video_ad",
        "audio": "audio_ad",
    }
    selected = aliases.get(raw_type, raw_type)
    if selected not in _AUTOFILL_DESIGN_TYPES:
        selected = "image_poster"

    raw_values = data.get("form_values") or data.get("formValues") or {}
    values = {
        key: str(value).strip()
        for key, value in raw_values.items()
        if key in _AUTOFILL_FIELDS and value is not None and str(value).strip()
    }
    merged_values = {
        key: str(value)
        for key, value in body.current_values.items()
        if key in _AUTOFILL_FIELDS and value is not None
    }
    merged_values.update(values)
    # The user's own request is an approved brief source. Using it as the key
    # message is safer than inventing a slogan and keeps the required field
    # editable when the model extracts only the product name.
    if not merged_values.get("key_message", "").strip():
        merged_values["key_message"] = body.user_prompt.strip()
    required_fields = {"product_name", "key_message"}
    if selected == "video_ad":
        required_fields.update({"call_to_action", "language", "creative_mode", "opening_hook"})
    missing_fields = [
        str(field) for field in data.get("missing_fields", [])
        if isinstance(field, str)
        and field in required_fields
        and not merged_values.get(field, "").strip()
    ]
    assistant_message = str(data.get("assistant_message") or "")
    if not assistant_message or (
        not missing_fields
        and _re.search(r"\b(missing|still needed|provide|required)\b", assistant_message, _re.I)
    ):
        assistant_message = (
            f"I selected {selected.replace('_', ' ')} and prefilled the campaign details. "
            "Review the form and confirm the brief when it is accurate."
        )
    return {
        "selected_design_type": selected,
        "selectedTemplate": selected,
        "form_values": merged_values,
        "formValues": merged_values,
        "assistant_message": assistant_message,
        "missing_fields": missing_fields,
        "reference_recommendations": [
            str(item) for item in data.get("reference_recommendations", [])
            if isinstance(item, str)
        ][:4],
        "used_fallback": False,
    }


@router.post("/generation/autofill")
async def autofill_easy_form(
    body: AutofillRequest,
    principal: Principal = Depends(get_current_principal),
) -> JSONResponse:
    """Turn conversational instructions into a reviewable Easy Mode draft."""
    if not body.user_prompt.strip():
        return JSONResponse(status_code=400, content={"error": "Please describe the ad you want to create."})
    if not gemini:
        return JSONResponse(content=_fallback_autofill(body))

    prompt = f"""
    You are the Easy Mode campaign setup assistant for an advertising application.
    Convert the user's latest message into a draft form. If current values are supplied,
    treat the message as a revision and preserve values the user did not ask to change.
    Never invent prices, awards, certifications, addresses, opening hours, health claims,
    discounts, or product facts. Leave unsupported fields absent.
    Return ONLY a valid JSON object without markdown.
    
    The JSON schema is:
    {{
      "selected_design_type": "image_poster" | "carousel" | "video_ad" | "text_copy" | "audio_ad",
      "form_values": {{
        "product_name": "...", "key_message": "...", "target_audience": "...",
        "platform": "instagram | tiktok | shopee", "brand_tone": "...",
        "visual_style": "...", "color_palette": "...", "slide_count": "...",
        "copy_length": "...", "call_to_action": "...", "language": "...",
        "video_duration": "15s | 30s | 60s",
        "creative_mode": "speaker_led | voiceover | music_first",
        "opening_hook": "Sudden action → product reveal | Shock impact → instant product snap | Unexpected visual transformation | Problem first → product solution | Immediate product demonstration",
        "code_switching": "Yes | No", "audio_duration": "15s | 30s | 60s",
        "voice_tone": "...", "background_music_style": "...",
        "forbidden_claims": "...", "brand_rules": "...", "compliance_constraints": "..."
      }},
      "assistant_message": "One short sentence explaining what was selected and what needs review.",
      "missing_fields": ["field_name"],
      "reference_recommendations": ["Product photo", "Shop / location"]
    }}

    Current design type: {json.dumps(body.current_design_type)}
    Current form values: {json.dumps(body.current_values, ensure_ascii=False)}
    Latest user message: {json.dumps(body.user_prompt, ensure_ascii=False)}
    """

    try:
        response = gemini.models.generate_content(
            model=MODEL_TEXT,
            contents=prompt,
        )
        raw_text = response.text or ""
        raw_text = raw_text.strip()
        if raw_text.startswith("```"):
            lines = raw_text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            raw_text = "\n".join(lines).strip()

        data = json.loads(raw_text)
        return JSONResponse(content=_normalize_autofill_payload(data, body))
    except Exception as e:
        logger.warning("[Autofill] AI extraction failed; using deterministic fallback: %s", e)
        return JSONResponse(content=_fallback_autofill(body))


# ─── Hook Video Search ────────────────────────────────────────────────────────


class HookSearchRequest(BaseModel):
    """Request body for searching YouTube hook/transition videos."""
    query: str = Field(default="", max_length=300)
    creative_style: str = Field(default="meme_shock", max_length=80)
    market: str = Field(default="malaysia", max_length=80)
    ethnicity: str = Field(default="all", max_length=80)
    product_category: str = Field(default="", max_length=120)
    max_results: int = Field(default=8, ge=1, le=20)


class HookPreferenceRequest(BaseModel):
    """Record a user's hook video preference for learning."""
    video_id: str = Field(min_length=1, max_length=128)
    tags: List[str] = Field(default_factory=list, max_length=20)
    creative_style: str = Field(default="meme_shock", max_length=80)
    product_category: str = Field(default="", max_length=120)


@router.post("/hook-search")
async def search_hook_videos_endpoint(
    body: HookSearchRequest,
    principal: Principal = Depends(get_current_principal),
) -> JSONResponse:
    """Search YouTube for hook/transition videos for ad creative references.

    Uses the YouTube Data API v3 to find short, viral clips suitable as
    hook references for the meme_shock creative style.

    Returns a list of video results with thumbnails, titles, and URLs.
    """
    from jusads_generation.hook_search import search_hook_videos

    try:
        results = await search_hook_videos(
            query=body.query,
            creative_style=body.creative_style,
            market=body.market,
            ethnicity=body.ethnicity,
            product_category=body.product_category,
            max_results=body.max_results,
        )
        return JSONResponse(content={
            "results": [r.to_dict() for r in results],
            "count": len(results),
            "query_used": body.query or f"(auto: {body.creative_style})",
        })
    except Exception:
        logger.exception("[HookSearch] Endpoint error for verified user")
        return JSONResponse(
            status_code=500,
            content={"error": "Hook video search failed"},
        )


@router.post("/hook-search/preference")
async def record_hook_preference(
    body: HookPreferenceRequest,
    principal: Principal = Depends(get_current_principal),
) -> JSONResponse:
    """Record a user's hook video selection for preference learning.

    The system learns which hook styles the user prefers via simple
    association rules. Future searches are reranked by this profile.
    """
    from jusads_generation.hook_search import learn_preference

    user_id = principal.email
    try:
        learn_preference(
            user_id=user_id,
            selected_video_id=body.video_id,
            tags=body.tags,
            creative_style=body.creative_style,
            product_category=body.product_category,
        )
        return JSONResponse(content={"status": "ok", "message": "Preference recorded"})
    except Exception:
        logger.exception("[HookSearch] Preference recording failed for verified user")
        return JSONResponse(
            status_code=503,
            content={"error": "Preference service is temporarily unavailable"},
        )


@router.get("/hook-search/tags")
async def suggest_hook_tags(
    brief: str = Query(""),
    creative_style: str = Query("meme_shock"),
    principal: Principal = Depends(get_current_principal),
) -> JSONResponse:
    """Suggest hook style tags for a given brief and creative strategy.

    Returns a list of recommended HOOK_TAGS to guide the user's hook
    video selection or auto-search refinement.
    """
    from jusads_generation.hook_search import suggest_hook_tags_for_brief, HOOK_TAGS

    suggestions = suggest_hook_tags_for_brief(brief, creative_style)
    return JSONResponse(content={
        "suggestions": suggestions,
        "all_tags": HOOK_TAGS,
    })
