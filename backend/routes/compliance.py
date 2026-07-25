"""
routes/compliance.py
────────────────────
Compliance check endpoints.

Endpoints:
  - POST /api/compliance/check              → Invoke Compliance Pipeline (SSE)
  - GET  /api/compliance/{task_id}          → Single check result
  - POST /api/compliance/{task_id}/clone-voice → Clone brand voice (kept for future remix integration)
  - WS   /ws/{task_id}                     → Legacy WebSocket (retained for compat)
"""

import asyncio
import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from fastapi import APIRouter, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse

from jusads_compliance.utils import detect_media_type_from_filename
from shared.supabase_client import SupabaseComplianceStore
from shared.s3_client import S3MediaClient, build_s3_key
from shared.models import CheckRecord, ComplianceOutput, Compliance_State
from jusads_compliance.pipeline_runner import PipelineRunner
from jusads_compliance.progress_tracker import ProgressTracker

logger = logging.getLogger(__name__)

router = APIRouter(tags=["compliance"])

# -- Shared state (injected from app.py) ---------------------------------------
_supabase_store: SupabaseComplianceStore | None = None
_s3_client: S3MediaClient | None = None
_pending_decisions: Dict[str, asyncio.Event] = {}
_decision_store: Dict[str, str] = {}
_compliance_runner: PipelineRunner | None = None
_remediation_runner: PipelineRunner | None = None
_tracker: ProgressTracker | None = None

# Directories
IS_LAMBDA = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
_BASE_DIR = Path("/tmp") if IS_LAMBDA else Path("assets")
RESULTS_DIR = _BASE_DIR / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def init_compliance(supabase_store, s3_client):
    """Called from app.py to inject shared clients."""
    global _supabase_store, _s3_client, _compliance_runner, _remediation_runner, _tracker

    from jusads_compliance.compliance_pipeline import compliance_pipeline
    from jusads_compliance.remediation_pipeline import remediation_pipeline

    _supabase_store = supabase_store
    _s3_client = s3_client
    _compliance_runner = PipelineRunner(
        tracker=_tracker,
        pipeline=compliance_pipeline,
        pending_decisions=_pending_decisions,
        decision_store=_decision_store,
    )
    _remediation_runner = PipelineRunner(
        tracker=_tracker,
        pipeline=remediation_pipeline,
        pending_decisions=_pending_decisions,
        decision_store=_decision_store,
    )
_tracker = ProgressTracker()


async def _stream_pipeline_events(pipeline, state: Compliance_State, task_id: str):
    """Bridge synchronous LangGraph events into an async SSE generator.

    Gemini and tool calls block the graph's synchronous ``stream`` iterator.
    Running it in a worker thread lets the event loop flush each node status as
    soon as it is produced rather than buffering all events until completion.
    """
    event_loop = asyncio.get_running_loop()
    events: asyncio.Queue[dict] = asyncio.Queue()

    def publish(event: dict) -> None:
        event_loop.call_soon_threadsafe(events.put_nowait, event)

    def run_graph() -> None:
        final_state: dict = {}
        try:
            config = {"configurable": {"thread_id": task_id}}
            for chunk in pipeline.stream(
                state,
                config=config,
                stream_mode=["tasks", "updates"],
                version="v2",
            ):
                chunk_type = chunk.get("type")
                payload = chunk.get("data", {})
                if chunk_type == "tasks":
                    node_name = payload.get("name", "compliance_check")
                    if "input" in payload:
                        publish({
                            "type": "node_status", "node": node_name,
                            "status": "running",
                            "description": f"Checking: {node_name.replace('_', ' ')}",
                        })
                    elif "error" in payload or "result" in payload:
                        publish({
                            "type": "node_status", "node": node_name,
                            "status": "error" if payload.get("error") else "completed",
                            "description": payload.get("error") or f"Completed {node_name.replace('_', ' ')}",
                        })
                elif chunk_type == "updates" and isinstance(payload, dict):
                    for node_output in payload.values():
                        if isinstance(node_output, dict):
                            final_state.update(node_output)
            publish({"type": "pipeline_complete", "final_state": final_state})
        except Exception as exc:
            logger.exception("[Pipeline] Graph failed for %s", task_id)
            publish({"type": "pipeline_error", "message": str(exc)})

    threading.Thread(target=run_graph, name=f"compliance-{task_id[:8]}", daemon=True).start()
    while True:
        event = await events.get()
        yield event
        if event["type"] in {"pipeline_complete", "pipeline_error"}:
            return

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# WEBSOCKET (sends result once pipeline completes)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Store completed results for WebSocket delivery
_completed_results: Dict[str, dict] = {}


@router.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    """WebSocket for compliance check result delivery and human decisions.

    Polls _completed_results until the pipeline finishes, then sends the
    result event and closes. Also handles human-in-the-loop resume.
    """
    await websocket.accept()
    try:
        while True:
            # Check if result is ready (non-blocking poll)
            if task_id in _completed_results:
                result = _completed_results.pop(task_id)
                await websocket.send_json({"type": "result", "data": result})
                await websocket.close()
                return

            # Wait for client messages with a short timeout
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=1.0)
                action = data.get("action")
                if action == "resume":
                    decision = data.get("decision", "ok")
                    _decision_store[task_id] = decision
                    event = _pending_decisions.get(task_id)
                    if event:
                        event.set()
                    logger.info("[WS] Resume for %s: %s", task_id, decision)
                elif action == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                # No message from client — just loop and check for results again
                continue
    except WebSocketDisconnect:
        _pending_decisions.pop(task_id, None)
        _decision_store.pop(task_id, None)
        logger.info("[WS] Disconnected: %s", task_id)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# POST /api/compliance/check
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.post("/api/compliance/check")
async def check_compliance(
    file: UploadFile = File(None),
    text: str = Form(None),
    market: str = Form("malaysia"),
    ethnicity: str = Form("malay"),
    age_group: str = Form("all_ages"),
    platform: str = Form("general"),
    username: str = Form("anonymous"),
    project_id: str = Form(None),
):
    """Trigger a compliance check. Returns SSE stream with real-time progress.

    SSE events emitted:
      - {"type": "initiated", "task_id": "...", "media_type": "...", "s3_upload_key": "..."}
      - {"type": "node_status", "node": "...", "status": "running"|"completed"|"error", "description": "..."}
      - {"type": "result", "data": {...full compliance result...}}
      - {"type": "error", "message": "..."}
    """
    logger.info(
        "[ComplianceAPI] ═══ NEW CHECK REQUEST ═══ market=%s, ethnicity=%s, "
        "has_file=%s, has_text=%s, project_id=%s",
        market, ethnicity, file is not None, text is not None, project_id
    )
    task_id: str | None = None
    s3_upload_key: str | None = None

    if not project_id:
        if _supabase_store:
            try:
                proj = _supabase_store.create_project(user_id=username, name="Untitled")
                project_id = proj["id"]
            except Exception:
                project_id = str(uuid.uuid4())
        else:
            project_id = str(uuid.uuid4())

    # Create the task first to get task_id
    if _supabase_store:
        try:
            task_row = _supabase_store.create_task(
                project_id=project_id, task_type="compliance",
                status="pending", summary="Compliance check",
            )
            task_id = task_row["id"]
        except Exception as e:
            logger.warning("[API] Task creation failed: %s", e)

    # Fallback task_id if Supabase unavailable
    if not task_id:
        task_id = str(uuid.uuid4())

    # Input routing
    if text and not file:
        media_type = "text"
        file_path = ""
        filename = ""
    elif file:
        filename = file.filename or "upload"
        file_content = await file.read()

        # Write to a temp file (avoids local dir management, works on Lambda)
        import tempfile
        suffix = Path(filename).suffix
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix=f"{task_id[:8]}_")
        tmp.write(file_content)
        tmp.close()
        file_path = tmp.name

        if _s3_client:
            try:
                s3_key = build_s3_key("upload", username, project_id, task_id, filename)
                _s3_client.upload_file(file_path, s3_key)
                s3_upload_key = _s3_client.get_public_url(s3_key)
                logger.info("[API] S3 upload: %s", s3_upload_key)
            except Exception as e:
                logger.warning("[API] S3 upload failed: %s", e)

        media_type = detect_media_type_from_filename(filename)
    else:
        return JSONResponse(status_code=400, content={"error": "Provide 'text' or 'file'"})

    logger.info("[API] task_id=%s, media_type=%s", task_id, media_type)

    # Build Compliance_State TypedDict for the new pipeline
    state: Compliance_State = {
        "session_id": task_id,
        "media_type": media_type,
        "input_path": file_path,
        "text_input": text or "",
        "market": market,
        "platform": platform,
        "ethnicity": ethnicity,
        "age_group": age_group,
        "iteration": 0,
        "result": {},
        "status": "pending",
        "user_prompt_context": "",
        "task_id": task_id,
        "remediated_path": "",
        "remix_iteration": 0,
    }

    def generate_sse_events():
        """SSE event generator — runs pipeline and emits progress events."""
        def emit(event: dict) -> str:
            return f"data: {json.dumps(event)}\n\n"

        # Emit initiated event immediately
        yield emit({
            "type": "initiated",
            "task_id": task_id,
            "media_type": media_type,
            "s3_upload_key": s3_upload_key,
        })

        try:
            # Run pipeline with progress streaming
            from langgraph.errors import GraphInterrupt

            config = {"configurable": {"thread_id": task_id}}
            final_state: dict = {}

            for chunk in _compliance_runner.pipeline.stream(
                state,
                config=config,
                stream_mode=["tasks", "updates"],
                version="v2",
            ):
                chunk_type = chunk.get("type")
                payload = chunk.get("data", {})
                if chunk_type == "tasks":
                    node_name = payload.get("name", "compliance_check")
                    if "input" in payload:
                        yield emit({
                            "type": "node_status",
                            "node": node_name,
                            "status": "running",
                            "description": f"Checking: {node_name.replace('_', ' ')}",
                        })
                    elif "error" in payload or "result" in payload:
                        status = "error" if payload.get("error") else "completed"
                        yield emit({
                            "type": "node_status",
                            "node": node_name,
                            "status": status,
                            "description": payload.get("error") or f"Completed {node_name.replace('_', ' ')}",
                        })
                elif chunk_type == "updates" and isinstance(payload, dict):
                    for node_output in payload.values():
                        if isinstance(node_output, dict):
                            final_state.update(node_output)

            if False:  # Legacy update-only stream retained temporarily for reference.
              for event in _compliance_runner.pipeline.stream(state, config=config, stream_mode="updates"):
                for node_name, node_output in event.items():
                    # Emit node status events for the frontend SSE stream.
                    # NOTE: Do NOT call _tracker here — each pipeline node already
                    # calls _tracker.start_step() and _tracker.complete_step()
                    # internally. Calling it again here causes every step to be
                    # recorded twice in pipeline_progress.
                    yield emit({
                        "type": "node_status",
                        "node": node_name,
                        "status": "running",
                        "description": f"Running {node_name}...",
                    })

                    # Merge state
                    if isinstance(node_output, dict):
                        final_state.update(node_output)

                    yield emit({
                        "type": "node_status",
                        "node": node_name,
                        "status": "completed",
                        "description": f"Completed {node_name}",
                    })

            # Pipeline done — process result
            response = final_state.get("result", {})

            # A graph node has already recorded the internal failure. Do not
            # manufacture or persist a partial compliance result: surface a
            # terminal SSE error so the frontend can show a failed state.
            if response.get("error"):
                yield emit({
                    "type": "error",
                    "message": f"Compliance analysis failed: {response['error']}",
                })
                return

            # Upload segmented mask to S3
            s3_segmented_url = None
            seg_data = response.get("segmentation")
            seg_path = seg_data.get("segmented_image_path") if isinstance(seg_data, dict) else None

            if seg_path:
                if not os.path.isabs(seg_path):
                    seg_path = str(Path(__file__).resolve().parent.parent / seg_path)

            if seg_path and _s3_client and os.path.exists(seg_path):
                try:
                    s3_seg_key = build_s3_key("segmented", username, project_id, task_id, os.path.basename(seg_path))
                    s3_segmented_url = _s3_client.upload_file_public(seg_path, s3_seg_key)
                except Exception as e:
                    logger.warning("[Pipeline] Segmented S3 upload failed: %s", e)

            if not s3_segmented_url and isinstance(seg_data, dict):
                mask_path = seg_data.get("mask_path")
                if mask_path and not os.path.isabs(mask_path):
                    mask_path = str(Path(__file__).resolve().parent.parent / mask_path)
                if mask_path and _s3_client and os.path.exists(mask_path):
                    try:
                        s3_seg_key = build_s3_key("segmented", username, project_id, task_id, os.path.basename(mask_path))
                        s3_segmented_url = _s3_client.upload_file_public(mask_path, s3_seg_key)
                    except Exception as e:
                        logger.warning("[Pipeline] Mask S3 upload failed: %s", e)

            # Normalize output
            output = ComplianceOutput.from_pipeline_result(response, media_type)
            output_dict = output.model_dump()
            output_dict["s3_upload_key"] = s3_upload_key
            output_dict["s3_segmented_key"] = s3_segmented_url
            output_dict["market"] = market
            output_dict["task_id"] = task_id

            # Persist to Supabase
            _persist_check_record(
                task_id=task_id, project_id=project_id,
                media_type=media_type, market=market, ethnicity=ethnicity,
                age_group=age_group, platform=platform,
                response=output_dict,
                s3_upload_key=s3_upload_key, s3_segmented_key=s3_segmented_url,
            )

            logger.info("[Pipeline] ═══ RESULT PERSISTED ═══ task_id=%s", task_id)

            # Emit final result
            yield emit({
                "type": "result",
                "data": output_dict,
            })

        except Exception as e:
            logger.error("[Pipeline] Error for %s: %s", task_id, e, exc_info=True)
            _tracker.fail_step(task_id, "pipeline", str(e)[:200])
            yield emit({
                "type": "error",
                "message": f"Pipeline failed: {str(e)[:200]}",
            })

    return StreamingResponse(
        generate_sse_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )








# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# POST /api/compliance/{task_id}/clone-voice
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.post("/api/compliance/{task_id}/clone-voice")
async def clone_voice_endpoint(task_id: str):
    """Clone the brand voice from the original audio of a compliance check.

    The cloned voice is stored persistently and reused for all future
    audio remediation on this project.
    """
    if not _supabase_store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        response = _supabase_store.client.table("compliance_checks").select(
            "task_id, media_type, s3_upload_key, project_id"
        ).eq("task_id", task_id).execute()
        rows = response.data or []
        if not rows:
            return JSONResponse(status_code=404, content={"error": "Check not found"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

    check = rows[0]
    if check["media_type"] not in ("audio", "video"):
        return JSONResponse(status_code=400, content={"error": "Voice cloning requires audio or video media"})

    source_url = check.get("s3_upload_key", "")
    if not source_url:
        return JSONResponse(status_code=400, content={"error": "No source audio available"})

    from jusads_compliance.voice_clone_manager import clone_brand_voice

    result = await clone_brand_voice(
        project_id=str(check["project_id"]),
        voice_name=f"Brand Voice - {task_id[:8]}",
        sample_audio_url=source_url,
        description="Cloned from compliance check audio",
    )

    if result:
        return JSONResponse(content={
            "status": "cloned",
            "voice_id": result["voice_id"],
            "name": result["name"],
            "project_id": result["project_id"],
        })
    else:
        return JSONResponse(status_code=500, content={"error": "Voice cloning failed"})








# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET /api/compliance/{task_id}
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.get("/api/compliance/{task_id}")
async def get_results(task_id: str):
    """Get results for a previous compliance check.

    Tries the local JSON cache first, then falls back to Supabase.
    Always enriches with S3 URLs from the DB.
    """
    result: dict = {}

    # Try local JSON cache
    result_path = RESULTS_DIR / f"{task_id}.json"
    if result_path.exists():
        with open(result_path, "r", encoding="utf-8") as f:
            result = json.load(f)

    # Enrich with S3 URLs from Supabase (always authoritative for URLs)
    if _supabase_store:
        try:
            response = _supabase_store.client.table("compliance_checks").select(
                "s3_upload_key, s3_segmented_key, s3_remix_key, result_json"
            ).eq("task_id", task_id).execute()
            if response.data:
                record = response.data[0]
                if not result and record.get("result_json"):
                    result = record["result_json"]
                result["s3_upload_key"] = record.get("s3_upload_key")
                result["s3_segmented_key"] = record.get("s3_segmented_key")
                result["s3_remix_key"] = record.get("s3_remix_key")
        except Exception as e:
            logger.warning("[Results] DB fetch failed for %s: %s", task_id, e)

    if not result:
        return JSONResponse(status_code=404, content={"error": "Not found"})

    return JSONResponse(content=result)






# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PERSISTENCE HELPER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _persist_check_record(
    task_id: str, project_id: str,
    media_type: str, market: str, ethnicity: str, age_group: str, platform: str,
    response: dict, s3_upload_key: str | None, s3_segmented_key: str | None = None,
) -> None:
    """Persist compliance check result to Supabase."""
    now = datetime.now(timezone.utc)

    # Strip heavy/duplicate fields from result_json to reduce storage bloat.
    # Bounding boxes are already rendered on the segmented image — no need to store them.
    persist_response = {**response}
    seg = persist_response.get("segmentation")
    if isinstance(seg, dict):
        persist_response["segmentation"] = {
            "num_masks": seg.get("num_masks"),
            "segmented_image_path": seg.get("segmented_image_path"),
        }

    record = CheckRecord(
        task_id=uuid.UUID(task_id) if task_id else uuid.uuid4(),
        project_id=uuid.UUID(project_id) if project_id else uuid.uuid4(),
        media_type=media_type,
        market=market,
        ethnicity=ethnicity,
        age_group=age_group,
        platform=platform,
        risk_percentage=persist_response.get("risk_percentage"),
        status="checked",
        result_json=persist_response,
        s3_upload_key=s3_upload_key,
        s3_segmented_key=s3_segmented_key,
        s3_remix_key=None,
        created_at=now,
        updated_at=now,
    )

    if not _supabase_store:
        logger.warning("[Persist] No store, skipping %s", task_id)
        return

    try:
        success = _supabase_store.insert_check(record)
        if success:
            logger.info("[Persist] Inserted compliance_checks for task: %s", task_id)
            # Also update task status to "checked"
            try:
                _supabase_store.client.table("tasks").update({
                    "status": "checked",
                    "summary": f"Compliance check - {media_type} ({market})",
                }).eq("id", task_id).execute()
            except Exception as e:
                logger.warning("[Persist] Task status update failed for %s: %s", task_id, e)
    except Exception as e:
        logger.warning("[Persist] Failed for %s: %s", task_id, e)
