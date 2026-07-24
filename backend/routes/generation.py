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
import tempfile
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from shared.supabase_client import SupabaseComplianceStore
from shared.s3_client import generate_presigned_upload_url, get_public_url, upload_file_public
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
    get_ad_analytics,
    configured_distribution_accounts,
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
    # V3 is the production video path. Legacy single-clip generation remains
    # an explicit opt-out for existing workflows only.
    video_v3: bool = True
    target_ethnicity: Optional[str] = None
    age_group: Optional[str] = None  # gen_z|millennial|gen_x|baby_boomer|all_ages
    market: Optional[str] = None  # malaysia|singapore
    language: Optional[str] = None  # ms|en|zh|ta|auto
    product_name: Optional[str] = None
    product_category: Optional[str] = None
    gender: Optional[str] = None  # male|female|mixed
    # Easy Mode fields (Req 14.1, 14.5)
    revision_instruction: Optional[str] = None
    advanced_overrides: Optional[dict] = None
    parent_ad_id: Optional[str] = None
    parent_asset_url: Optional[str] = None


class UploadUrlRequest(BaseModel):
    filename: str
    content_type: str = "application/octet-stream"


class ExecuteVideoPlanRequest(BaseModel):
    """Body for executing an approved Video V2 storyboard plan (Continue button)."""

    plan: dict  # the plan dict from the `video_plan` SSE event (possibly edited)
    skip_compliance: bool = False


import asyncio

# In-memory store for background generation tasks. Maps run_id -> asyncio.Queue of SSE chunks.
# When the client disconnects and reconnects, they poll the queue by run_id.
_active_runs: dict[str, asyncio.Queue] = {}
_run_complete: dict[str, bool] = {}


@router.post("/projects/{project_id}/tasks/{task_id}/chat")
async def chat_with_generation_agent(project_id: str, task_id: str, body: ChatRequest) -> StreamingResponse:
    """Send a message to the AI generation agent, streaming response text and returning the final state.

    The generation runs as a BACKGROUND TASK — if the client disconnects mid-stream,
    the pipeline continues running and persists results to Supabase. When the user
    comes back, the frontend fetches the persisted generated_ads + pipeline_state.
    """
    if not _store:
        return JSONResponse(status_code=503, content={"error": "Persistence store is unavailable"})

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
            return JSONResponse(status_code=422, content={"error": str(ve)})
    elif body.guided_mode and body.design_type and body.guided_inputs:
        try:
            from jusads_generation.guided_prompts import assemble_guided_message, DESIGN_TYPE_TO_MEDIA

            effective_message = assemble_guided_message(body.design_type, body.guided_inputs)
            forced_media = DESIGN_TYPE_TO_MEDIA.get(body.design_type)
        except ValueError as ve:
            return JSONResponse(status_code=422, content={"error": str(ve)})
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
                video_v3=body.video_v3,
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
                            # Save intermediate state to DB
                            _store.update_task_pipeline(
                                project_id=project_id,
                                task_id=task_id,
                                status="in_progress",
                                pipeline_state=final_state,
                            )
                    except Exception as pe:
                        logger.warning("[BG] Error parsing/persisting state chunk: %s", pe)

        except Exception as err:
            logger.error("[BG] Generation background task error: %s", err)
            await queue.put(f"data: {json.dumps({'error': str(err)})}\n\n")

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
    project_id: str, task_id: str, body: ExecuteVideoPlanRequest
) -> StreamingResponse:
    """Render an approved Video V2 storyboard plan into the final video (SSE).

    Runs as a BACKGROUND TASK — if client disconnects, rendering continues.
    """
    if not _store:
        return JSONResponse(status_code=503, content={"error": "Persistence store is unavailable"})

    task = _store.get_task_detail(project_id=project_id, task_id=task_id)
    if not task:
        return JSONResponse(status_code=404, content={"error": "Task not found"})

    current_pipeline_state = task.get("pipeline_state") or {
        "nodes": [], "edges": [], "viewport": {"panX": 0, "panY": 0, "zoom": 1}
    }
    if (
        body.plan.get("pipeline_version") == "v3_grid"
        and not _is_usable_v3_plan(body.plan)
    ):
        return JSONResponse(
            status_code=422,
            content={
                "error": (
                    "Video storyboard assets are incomplete. Regenerate the scene grid "
                    "and sliced frames before starting paid rendering."
                )
            },
        )

    run_id = f"v2_{project_id}_{task_id}_{uuid.uuid4().hex[:6]}"
    queue: asyncio.Queue = asyncio.Queue()
    _active_runs[run_id] = queue
    _run_complete[run_id] = False

    async def _run_v2_background():
        """Background task for Video V2 execution."""
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
                            _store.update_task_pipeline(
                                project_id=project_id, task_id=task_id,
                                status="in_progress", pipeline_state=final_state,
                            )
                    except Exception as pe:
                        logger.warning("[BG-V2] Error parsing/persisting state: %s", pe)
        except Exception as err:
            logger.error("[BG-V2] Video V2 execution error: %s", err)
            await queue.put(f"data: {json.dumps({'error': str(err)})}\n\n")

        if final_state:
            try:
                _store.update_task_pipeline(
                    project_id=project_id, task_id=task_id,
                    status="completed", pipeline_state=final_state,
                )
                logger.info("[BG-V2] Persisted final V2 pipeline state.")
            except Exception as se:
                logger.error("[BG-V2] Failed to persist final V2 state: %s", se)

        _run_complete[run_id] = True
        await queue.put(None)
        await asyncio.sleep(30)
        _active_runs.pop(run_id, None)
        _run_complete.pop(run_id, None)

    asyncio.create_task(_run_v2_background())

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
            logger.info("[SSE-V2] Client disconnected — background task continues")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "Content-Encoding": "none"},
    )


@router.get("/projects/{project_id}/tasks/{task_id}/generated-ads")
async def get_generated_ads(project_id: str, task_id: str) -> JSONResponse:
    """Return all generated ads for a task (newest first) so the UI can repopulate on reload."""
    if not _store:
        return JSONResponse(status_code=503, content={"error": "Persistence store is unavailable"})

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
            ads.append({
                "ad_id": str(row.get("id", "")),
                "media_type": row.get("media_type", ""),
                "platform": row.get("platform", ""),
                "s3_media_key": row.get("s3_media_key"),
                "public_url": metadata.get("s3_url"),
                "aspect_ratio": metadata.get("aspect_ratio"),
                "caption": row.get("caption") or (row.get("prompt_used") if row.get("media_type") == "text" else None),
                "gen_status": row.get("status", "completed"),
                "compliance_status": row.get("compliance_status", "non-final"),
                "compliance_reasons": row.get("compliance_result") or {},
                "revision_edit": metadata.get("revision_edit"),
            })
        return JSONResponse(content={"ads": ads})
    except Exception as e:
        logger.error("Failed to fetch generated ads for task %s: %s", task_id, e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/projects/{project_id}/easy-results")
async def get_easy_results(project_id: str) -> JSONResponse:
    """Return recent output-bearing tasks so Easy Mode can resume a specific run."""
    if not _store:
        return JSONResponse(status_code=503, content={"error": "Persistence store is unavailable"})

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
    except Exception as e:
        logger.error("Failed to fetch Easy Mode results for project %s: %s", project_id, e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/projects/{project_id}/tasks/{task_id}/chat-history")
async def get_chat_history(project_id: str, task_id: str) -> JSONResponse:
    """Return the full ordered Chat_History for a task (Req 11.5).

    Responds with 200 ``{messages: [...]}`` (oldest → newest) on success, 404 when the
    task does not exist for the project (Req 2.7), and 503 when the persistence store is
    unavailable (Req 2.6).
    """
    if not _store:
        return JSONResponse(status_code=503, content={"error": "Persistence store is unavailable"})

    task = _store.get_task_detail(project_id=project_id, task_id=task_id)
    if not task:
        return JSONResponse(status_code=404, content={"error": "Task not found"})

    messages = list_chat_history(project_id, task_id)
    return JSONResponse(content={"messages": messages})


@router.post("/projects/{project_id}/tasks/{task_id}/ads/{ad_id}/publish")
async def publish_generated_ad(project_id: str, task_id: str, ad_id: str) -> JSONResponse:
    """Approve and publish a Generated_Ad — the human-in-the-loop gate (§ 4).

    Flips ``generated_ads.status`` to ``published`` once the owner has reviewed
    the output. Returns 200 with the post-publish state, 404 when the ad does
    not exist for the project, 409 when the ad failed compliance (blocked), and
    503 when the persistence store is unavailable.
    """
    if not _store:
        return JSONResponse(status_code=503, content={"error": "Persistence store is unavailable"})

    try:
        result = publish_ad(project_id, ad_id)
    except AdNotFoundError as e:
        logger.info("[Publish] %s", e)
        return JSONResponse(status_code=404, content={"error": str(e)})
    except CompliancePublishBlockedError as e:
        logger.warning("[Publish] Blocked: %s", e)
        return JSONResponse(status_code=409, content={"error": str(e)})
    except PublishError as e:
        logger.error("[Publish] Store error: %s", e)
        return JSONResponse(status_code=503, content={"error": str(e)})

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


@router.get("/distribution/accounts")
async def list_distribution_accounts() -> JSONResponse:
    """Return normalized connected Zernio accounts for multi-account posting."""
    try:
        from shared.zernio_client import get_connected_accounts

        payload = await get_connected_accounts()
        raw_accounts = payload.get("accounts") or payload.get("data") or []
        if isinstance(raw_accounts, dict):
            raw_accounts = raw_accounts.get("accounts") or raw_accounts.get("data") or []
        accounts: list[dict] = []
        for raw in raw_accounts if isinstance(raw_accounts, list) else []:
            if not isinstance(raw, dict):
                continue
            raw_platform = raw.get("platform")
            platform = raw_platform.get("value") if isinstance(raw_platform, dict) else raw_platform
            account_id = raw.get("id") or raw.get("_id") or raw.get("accountId")
            if not isinstance(platform, str) or not account_id:
                continue
            username = raw.get("username") or raw.get("handle") or raw.get("name")
            accounts.append({
                "id": str(account_id),
                "platform": platform.lower(),
                "label": f"@{username}" if username else f"{platform.title()} account",
            })
        if not accounts:
            accounts = configured_distribution_accounts()
        return JSONResponse(content={"accounts": accounts})
    except Exception as exc:
        logger.warning("[Distribution] Account discovery failed: %s", exc)
        return JSONResponse(content={"accounts": configured_distribution_accounts()})


class DistributeRequest(BaseModel):
    """Body for distributing a published ad to a social platform."""

    platform: Optional[str] = None  # legacy single-target request
    account_id: Optional[str] = None
    caption: Optional[str] = None
    destinations: List[DistributionTarget] = Field(default_factory=list)


@router.post("/projects/{project_id}/tasks/{task_id}/ads/{ad_id}/distribute")
async def distribute_generated_ad(
    project_id: str, task_id: str, ad_id: str, body: DistributeRequest
) -> JSONResponse:
    """Distribute a published ad to a social platform via Zernio.

    Only ads with ``status = published`` can be distributed. Returns 200 with the
    distribution result, 404 when the ad does not exist, 409 when the ad isn't
    published yet, and 503 when the distribution service is unavailable.
    """
    if not _store:
        return JSONResponse(status_code=503, content={"error": "Persistence store is unavailable"})

    # Verify the ad exists and is published.
    try:
        from shared.clients import supabase as sb

        resp = sb.table("generated_ads").select("id, status, platform, metadata, media_type, prompt_used, caption").eq("id", ad_id).eq("project_id", project_id).limit(1).execute()
        rows = resp.data or []
        if not rows:
            return JSONResponse(status_code=404, content={"error": f"Ad {ad_id} not found"})
        ad_row = rows[0]
        if ad_row.get("status") != "published":
            return JSONResponse(status_code=409, content={"error": "Ad must be published before distributing"})
    except Exception as e:
        return JSONResponse(status_code=503, content={"error": f"Failed to verify ad: {e}"})

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
            results.append({"platform": platform, "account_id": target.account_id, "status": "failed", "error": str(exc)})

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


@router.get("/projects/{project_id}/tasks/{task_id}/ads/{ad_id}/analytics")
async def get_ad_performance_analytics(
    project_id: str, task_id: str, ad_id: str
) -> JSONResponse:
    """Retrieve live social post analytics for a distributed ad."""
    if not _store:
        return JSONResponse(status_code=503, content={"error": "Persistence store is unavailable"})

    try:
        analytics = await asyncio.to_thread(get_ad_analytics, ad_id, project_id)
        return JSONResponse(content=analytics)
    except ValueError:
        return JSONResponse(status_code=404, content={"error": "Ad not found"})
    except DistributionError as exc:
        logger.warning("[Routes] Ad analytics unavailable: %s", exc)
        return JSONResponse(status_code=503, content={"error": str(exc)})
    except Exception:
        logger.exception("[Routes] Failed to get ad analytics")
        return JSONResponse(status_code=500, content={"error": "Failed to load analytics"})


@router.post("/projects/{project_id}/tasks/{task_id}/upload-url")
async def get_upload_url(project_id: str, task_id: str, body: UploadUrlRequest) -> JSONResponse:
    """Generate a pre-signed PUT URL for direct-to-S3 upload."""
    unique_id = uuid.uuid4().hex[:8]
    s3_key = f"generated_ads/{project_id}/{task_id}/references/{unique_id}_{body.filename}"

    try:
        upload_url = generate_presigned_upload_url(s3_key, body.content_type)
        public_url = get_public_url(s3_key)
        logger.info("[UploadURL] Generated presigned PUT for %s", s3_key)
        return JSONResponse(content={
            "upload_url": upload_url,
            "s3_key": s3_key,
            "public_url": public_url,
        })
    except Exception as e:
        logger.error("[UploadURL] Failed to generate presigned URL: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/projects/{project_id}/tasks/{task_id}/upload")
async def upload_reference_asset(project_id: str, task_id: str, file: UploadFile = File(...)) -> JSONResponse:
    """Server-side upload fallback for when S3 CORS is not configured.

    Accepts multipart file upload, writes to temp disk, uploads to S3.
    Frontend should prefer the presigned URL path when S3 CORS is enabled.
    """
    suffix = Path(file.filename or "file").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    s3_key = f"generated_ads/{project_id}/{task_id}/references/{uuid.uuid4().hex[:6]}_{file.filename}"
    try:
        s3_url = upload_file_public(tmp_path, s3_key)
        logger.info("[Upload] Uploaded reference: %s -> S3 key: %s", file.filename, s3_key)

        try:
            from shared.supabase_client import supabase as sb
            media_type = "image"
            if file.content_type and "video" in file.content_type:
                media_type = "video"
            elif file.content_type and "audio" in file.content_type:
                media_type = "audio"

            sb.table("generated_ads").insert({
                "project_id": project_id,
                "task_id": task_id,
                "media_type": media_type,
                "platform": "general",
                "s3_media_key": s3_key,
                "status": "completed",
                "asset_role": "reference",
                "prompt_used": f"Uploaded reference: {file.filename}",
                "metadata": {
                    "is_reference": True,
                    "filename": file.filename,
                    "s3_url": s3_url
                }
            }).execute()
            logger.info("[Upload] Recorded chatbot reference asset %s in generated_ads", file.filename)
        except Exception as dberr:
            logger.error("[Upload] Failed to record reference asset in DB: %s", dberr)

        return JSONResponse(content={
            "s3_url": s3_url,
            "s3_key": s3_key,
            "public_url": s3_url,
            "filename": file.filename,
        })
    except Exception as e:
        logger.error("[Upload] Failed reference upload: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


# --- Guided Form Schema -------------------------------------------------------


@router.get("/guided-form-schema")
async def get_guided_form_schema() -> JSONResponse:
    """Return form field definitions for guided generation mode."""
    from jusads_generation.guided_prompts import get_form_schema

    return JSONResponse(content=get_form_schema())


# --- Prompt Search (Phase F) --------------------------------------------------


@router.get("/prompt-suggestions")
async def get_prompt_suggestions(query: str = "", top_k: int = 8) -> JSONResponse:
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

    try:
        from jusads_generation.prompt_search.qdrant_store import search_prompts

        results = search_prompts(query.strip(), top_k=top_k)
        return JSONResponse(content={"suggestions": results})
    except Exception as e:
        logger.error("[PromptSearch] Search failed: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e), "suggestions": []})


@router.get("/prompt-recommendations")
async def get_prompt_recommendations(
    product_name: str = "",
    product_category: str = "",
    target_ethnicity: str = "all",
    platform: str = "tiktok",
    age_group: str = "all_ages",
    top_k: int = 6,
    user_email: str = "",
) -> JSONResponse:
    """Get personalized prompt recommendations based on the user's profile settings.

    Builds a query from the user's configured product/category/audience and
    searches the prompt vector DB for the most relevant templates — shown as a
    "Recommended for you" feed without the user needing to type anything.
    """
    product_description = ""
    target_platforms = [platform] if platform else []
    target_markets = [target_ethnicity] if target_ethnicity else []

    # Fetch real user business profile details from database if email is provided
    if user_email:
        try:
            from shared.clients import supabase as sb
            resp = sb.table("business_profiles").select("*").eq("owner_email", user_email).execute()
            if resp.data:
                profile = resp.data[0]
                product_name = profile.get("company_name") or product_name
                product_category = profile.get("product_category") or product_category
                product_description = profile.get("product_description") or ""
                target_platforms = profile.get("target_platforms") or target_platforms
                target_markets = profile.get("target_markets") or target_markets
        except Exception as e:
            logger.warning("[PromptRecommendations] Failed to fetch profile: %s", e)

    # Build a contextual query from the user's profile.
    parts = []
    if product_name:
        parts.append(f"advertisement for {product_name}")
    if product_category:
        category_labels = {
            "food_beverage": "food and beverage",
            "fashion": "fashion and apparel",
            "beauty": "beauty and personal care",
            "tech": "technology and gadgets",
            "health": "health and wellness",
            "finance": "finance and banking",
            "travel": "travel and tourism",
            "education": "education",
            "real_estate": "real estate",
            "automotive": "automotive",
            "entertainment": "entertainment",
            "ecommerce": "e-commerce retail",
        }
        parts.append(category_labels.get(product_category, product_category))
    if platform:
        parts.append(f"{platform} ad creative")
    if target_ethnicity and target_ethnicity != "all":
        parts.append(f"for {target_ethnicity} audience")
    if age_group and age_group != "all_ages":
        age_labels = {
            "gen_z": "young trendy Gen Z",
            "millennial": "millennial lifestyle",
            "gen_x": "mature Gen X family",
            "baby_boomer": "senior traditional",
        }
        parts.append(age_labels.get(age_group, age_group))

    if not parts:
        parts.append("creative advertisement poster social media")

    query = " ".join(parts)

    # Enhance query via Gemini using full user background
    if gemini:
        try:
            enhancement_prompt = f"""
            You are an expert marketing strategist and prompt engineer.
            Given the following user business profile:
            - Company/Product Name: {product_name}
            - Product Category: {product_category}
            - Product Description: {product_description}
            - Target Platforms: {', '.join(target_platforms) if isinstance(target_platforms, list) else platform}
            - Target Markets/Ethnicities: {', '.join(target_markets) if isinstance(target_markets, list) else target_ethnicity}
            - Audience Age Group: {age_group}
            
            Synthesize this user background and write a concise, highly effective 1-2 sentence search query for finding relevant ad prompt templates in a vector database. Focus on target style, core theme, and advertising visual concept. Return ONLY the enhanced query. Do not add quotes, explanation, or markdown.
            """
            
            response = gemini.models.generate_content(
                model=MODEL_TEXT,
                contents=enhancement_prompt,
            )
            enhanced_query = (response.text or "").strip()
            if enhanced_query:
                query = enhanced_query
                logger.info("[PromptRecommendations] Enhanced query: %s", query)
        except Exception as e:
            logger.error("[PromptRecommendations] Gemini enhancement failed, falling back to rule-based: %s", e)

    top_k = max(1, min(12, top_k))

    try:
        from jusads_generation.prompt_search.qdrant_store import search_prompts

        results = search_prompts(query, top_k=top_k)
        return JSONResponse(content={"query_used": query, "recommendations": results})
    except Exception as e:
        logger.error("[PromptRecommendations] Failed: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e), "recommendations": []})


@router.get("/user-assets")
async def get_user_assets(user_email: str = "", limit: int = 50) -> JSONResponse:
    """Fetch all generated ads across the user's projects for the Assets page.

    Returns completed ads with their media URLs, sorted newest first.
    """
    if not _store:
        return JSONResponse(status_code=503, content={"error": "Persistence store is unavailable"})

    try:
        from shared.clients import supabase as sb

        # Get user's projects first.
        projects_resp = sb.table("projects").select("id").eq("owner_email", user_email).execute()
        project_ids = [str(r["id"]) for r in (projects_resp.data or [])]

        if not project_ids:
            return JSONResponse(content={"assets": []})

        # Fetch generated ads across all user projects.
        ads_resp = (
            sb.table("generated_ads")
            .select("id, media_type, platform, s3_media_key, status, metadata, prompt_used, created_at, project_id, task_id")
            .in_("project_id", project_ids)
            .eq("status", "completed")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

        assets = []
        for row in (ads_resp.data or []):
            metadata = row.get("metadata") or {}
            # Public URL: prefer metadata.s3_url, fall back to constructing from s3_media_key.
            public_url = metadata.get("s3_url") or ""
            if not public_url and row.get("s3_media_key"):
                from shared.s3_client import get_public_url
                public_url = get_public_url(row["s3_media_key"])
            assets.append({
                "id": str(row.get("id", "")),
                "media_type": row.get("media_type", ""),
                "platform": row.get("platform", ""),
                "public_url": public_url,
                "prompt_used": row.get("prompt_used", ""),
                "status": row.get("status", ""),
                "created_at": row.get("created_at", ""),
                "project_id": str(row.get("project_id", "")),
                "task_id": str(row.get("task_id", "")),
                "is_reference": bool(metadata.get("is_reference", False)),
            })

        return JSONResponse(content={"assets": assets})
    except Exception as e:
        logger.error("[UserAssets] Failed: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


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
async def autofill_easy_form(body: AutofillRequest) -> JSONResponse:
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
