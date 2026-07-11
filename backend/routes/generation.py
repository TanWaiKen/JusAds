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

import uuid
import json
import logging
import tempfile
import os
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from shared.supabase_client import SupabaseComplianceStore
from shared.s3_client import generate_presigned_upload_url, get_public_url, upload_file_public
from jusads_generation import run_generation, run_video_plan_execution
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
)

logger = logging.getLogger(__name__)

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
    video_v3: bool = False
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


class UploadUrlRequest(BaseModel):
    filename: str
    content_type: str = "application/octet-stream"


class ExecuteVideoPlanRequest(BaseModel):
    """Body for executing an approved Video V2 storyboard plan (Continue button)."""

    plan: dict  # the plan dict from the `video_plan` SSE event (possibly edited)
    skip_compliance: bool = False


import asyncio

# In-memory store for background generation tasks. Maps run_id → asyncio.Queue of SSE chunks.
# When the client disconnects and reconnects, they poll the queue by run_id.
_active_runs: dict[str, asyncio.Queue] = {}
_run_complete: dict[str, bool] = {}


@router.post("/projects/{project_id}/tasks/{task_id}/chat")
async def chat_with_generation_agent(project_id: str, task_id: str, body: ChatRequest) -> StreamingResponse:
    """Send a message to the AI generation agent, streaming response text and returning the final state.

    The generation runs as a BACKGROUND TASK — if the client disconnects mid-stream,
    the pipeline continues running and persists results to Supabase. When the user
    comes back, the frontend fetches the persisted generated_ads + pipeline_state.

    Delegates to the ``jusads_generation`` orchestrator (Req 1.5, 1.6), which emits the
    same SSE event shapes the frontend already parses (`{text}`, `{node,status,data}`,
    `{pipeline_state}`, `{error}`). The user turn is persisted before generation begins
    (Req 6.3); a persistence failure surfaces an error event without discarding the turn
    (Req 6.7).
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

    # ── Guided mode: assemble the effective message from form inputs ──
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
                _store.update_task_pipeline(
                    project_id=project_id,
                    task_id=task_id,
                    status="completed",
                    pipeline_state=final_state,
                )
                logger.info("[BG] Persisted final generation pipeline state to Supabase.")
            except Exception as se:
                logger.error("[BG] Failed to persist final state: %s", se)

        # ── Easy Mode provenance persistence (Req 17.1, 17.2) ──
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
            .select("id, media_type, platform, s3_media_key, status, metadata, compliance_status, compliance_result, prompt_used")
            .eq("project_id", project_id)
            .eq("task_id", task_id)
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
                "caption": row.get("prompt_used") if row.get("media_type") == "text" else None,
                "gen_status": row.get("status", "completed"),
                "compliance_status": row.get("compliance_status", "non-final"),
                "compliance_reasons": row.get("compliance_result") or {},
            })
        return JSONResponse(content={"ads": ads})
    except Exception as e:
        logger.error("Failed to fetch generated ads for task %s: %s", task_id, e)
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

    return JSONResponse(content=dict(result))


class DistributeRequest(BaseModel):
    """Body for distributing a published ad to a social platform."""

    platform: str  # tiktok|instagram|youtube
    caption: Optional[str] = None


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

        resp = sb.table("generated_ads").select("id, status, metadata, media_type, prompt_used").eq("id", ad_id).eq("project_id", project_id).limit(1).execute()
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

    try:
        result = distribute_ad(
            ad_id=ad_id,
            platform=body.platform,
            media_url=media_url,
            media_type=ad_row.get("media_type", "image"),
            caption=body.caption or ad_row.get("prompt_used") or "",
        )
        return JSONResponse(content=result)
    except AccountNotConfiguredError as e:
        return JSONResponse(status_code=409, content={"error": str(e)})
    except DistributionError as e:
        return JSONResponse(status_code=503, content={"error": str(e)})


@router.get("/projects/{project_id}/tasks/{task_id}/ads/{ad_id}/analytics")
async def get_ad_performance_analytics(
    project_id: str, task_id: str, ad_id: str
) -> JSONResponse:
    """Retrieve social post analytics from Zernio for a distributed ad.

    If Zernio is not configured or the post is not distributed, returns fallback
    mock engagement data so the UI can render analytics graphs beautifully.
    """
    if not _store:
        return JSONResponse(status_code=503, content={"error": "Persistence store is unavailable"})

    try:
        analytics = get_ad_analytics(ad_id, project_id)
        return JSONResponse(content=analytics)
    except Exception as e:
        logger.error("[Routes] Failed to get ad analytics: %s", e)
        return JSONResponse(status_code=500, content={"error": f"Failed to load analytics: {e}"})


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


# ─── Guided Form Schema ───────────────────────────────────────────────────────


@router.get("/guided-form-schema")
async def get_guided_form_schema() -> JSONResponse:
    """Return form field definitions for guided generation mode."""
    from jusads_generation.guided_prompts import get_form_schema

    return JSONResponse(content=get_form_schema())


# ─── Prompt Search (Phase F) ──────────────────────────────────────────────────


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
) -> JSONResponse:
    """Get personalized prompt recommendations based on the user's profile settings.

    Builds a query from the user's configured product/category/audience and
    searches the prompt vector DB for the most relevant templates — shown as a
    "Recommended for you" feed without the user needing to type anything.

    Query params are the user's settings (from the Settings panel).
    """
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
            })

        return JSONResponse(content={"assets": assets})
    except Exception as e:
        logger.error("[UserAssets] Failed: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})
