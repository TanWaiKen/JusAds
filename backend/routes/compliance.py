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

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import JSONResponse, StreamingResponse

from jusads_compliance.utils import detect_media_type_from_filename
from shared.supabase_client import SupabaseComplianceStore
from shared.s3_client import S3MediaClient, build_s3_key
from shared.s3_client import generate_presigned_url, upload_file
from shared.auth import Principal, get_current_principal
from shared.authorization import (
    get_authorized_compliance_check,
    require_project_access,
)
from shared.media_security import (
    MediaSecurityError,
    SlidingWindowRateLimiter,
    remove_temp_file,
    stream_validated_upload,
)
from shared.models import CheckRecord, ComplianceOutput, Compliance_State
from jusads_compliance.pipeline_runner import PipelineRunner
from jusads_compliance.progress_tracker import ProgressTracker
from shared.config import ML_TRIAGE_ADVISORY_ENABLED

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
_upload_limiter = SlidingWindowRateLimiter(limit=10, window_seconds=60)
_MAX_COMPLIANCE_UPLOAD_BYTES = 100 * 1024 * 1024
_PRESIGNED_VIEW_SECONDS = 300

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
            publish({
                "type": "pipeline_error",
                "message": "Compliance evaluation could not be completed. Please try again.",
            })

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
    # Browser WebSockets cannot safely attach the bearer dependency used by the
    # REST endpoints. Until a short-lived, server-issued websocket ticket is
    # introduced, fail closed instead of exposing task-scoped results or resume
    # controls to an unauthenticated socket.
    await websocket.close(code=4401)
    return
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
    username: str = Form(None),
    project_id: str = Form(None),
    principal: Principal = Depends(get_current_principal),
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
    if not _supabase_store:
        return JSONResponse(
            status_code=503,
            content={"error": {"code": "DATASTORE_UNAVAILABLE", "message": "Service temporarily unavailable"}},
        )
    if not await _upload_limiter.allow(principal.subject):
        return JSONResponse(
            status_code=429,
            content={"error": {"code": "RATE_LIMITED", "message": "Too many compliance requests"}},
        )

    task_id: str | None = None
    s3_upload_key: str | None = None
    validated_upload = None
    file_path = ""

    try:
        if file is not None:
            validated_upload = await stream_validated_upload(
                file,
                max_bytes=_MAX_COMPLIANCE_UPLOAD_BYTES,
                allowed_media_types=("image", "audio", "video"),
            )
            file_path = validated_upload.path
        elif text is None or not text.strip():
            return JSONResponse(
                status_code=400,
                content={"error": {"code": "INPUT_REQUIRED", "message": "Provide text or a media file"}},
            )
        elif len(text.encode("utf-8")) > 100_000:
            return JSONResponse(
                status_code=413,
                content={"error": {"code": "TEXT_TOO_LARGE", "message": "Text input is too large"}},
            )
    except MediaSecurityError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code.upper(), "message": exc.public_message}},
        )

    try:
        if project_id:
            require_project_access(_supabase_store, project_id, principal, write=True)
        else:
            proj = _supabase_store.create_project(user_id=principal.email, name="Untitled")
            project_id = proj["id"]
    except HTTPException:
        remove_temp_file(file_path)
        raise
    except Exception:
        logger.exception("[ComplianceAPI] Project preparation failed subject=%s", principal.subject)
        remove_temp_file(file_path)
        return JSONResponse(
            status_code=503,
            content={"error": {"code": "DATASTORE_UNAVAILABLE", "message": "Service temporarily unavailable"}},
        )

    # Input routing
    if text and not file:
        media_type = "text"
        file_path = ""
        filename = ""
        summary_text = "Compliance check: Text Content"
    elif validated_upload:
        filename = validated_upload.filename
        media_type = validated_upload.media_type
        summary_text = f"Compliance check: {filename}"
    else:
        media_type = "unknown"
        filename = ""
        file_path = ""
        summary_text = "Compliance check: Unknown"

    # Create the task first to get task_id
    try:
        task_row = _supabase_store.create_task(
            project_id=project_id, task_type="compliance",
            status="pending", summary=summary_text,
        )
        task_id = task_row["id"]
    except Exception:
        logger.exception("[ComplianceAPI] Task creation failed project_id=%s", project_id)
        remove_temp_file(file_path)
        return JSONResponse(
            status_code=503,
            content={"error": {"code": "DATASTORE_UNAVAILABLE", "message": "Service temporarily unavailable"}},
        )

    if validated_upload:
        if not _s3_client:
            remove_temp_file(file_path)
            return JSONResponse(
                status_code=503,
                content={"error": {"code": "STORAGE_UNAVAILABLE", "message": "Media storage is temporarily unavailable"}},
            )
        try:
            s3_upload_key = build_s3_key(
                "upload", principal.subject, project_id, task_id, filename
            )
            _s3_client.upload_file(file_path, s3_upload_key)
            logger.info(
                "[ComplianceAPI] Private source uploaded task_id=%s subject=%s",
                task_id,
                principal.subject,
            )
        except Exception:
            logger.exception("[ComplianceAPI] Source upload failed task_id=%s", task_id)
            remove_temp_file(file_path)
            return JSONResponse(
                status_code=503,
                content={"error": {"code": "STORAGE_UNAVAILABLE", "message": "Media storage is temporarily unavailable"}},
            )
    else:
        remove_temp_file(file_path)
        return JSONResponse(status_code=400, content={"error": {"code": "INPUT_REQUIRED", "message": "Provide text or a media file"}})

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

        source_view_url = (
            generate_presigned_url(s3_upload_key, _PRESIGNED_VIEW_SECONDS)
            if s3_upload_key
            else None
        )
        # Emit initiated event immediately
        yield emit({
            "type": "initiated",
            "task_id": task_id,
            "media_type": media_type,
            "s3_upload_key": source_view_url,
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
                    # NOTE: Do NOT call _tracker here: each pipeline node already
                    # emits its own compatibility log. The SSE stream is the sole
                    # client-facing progress channel.
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
                    "code": "COMPLIANCE_ANALYSIS_FAILED",
                    "message": "Compliance analysis could not be completed.",
                })
                return

            # Upload segmented mask to S3
            s3_segmented_key = None
            seg_data = response.get("segmentation")
            seg_path = seg_data.get("segmented_image_path") if isinstance(seg_data, dict) else None

            if seg_path:
                if not os.path.isabs(seg_path):
                    seg_path = str(Path(__file__).resolve().parent.parent / seg_path)

            if seg_path and _s3_client and os.path.exists(seg_path):
                try:
                    s3_segmented_key = build_s3_key(
                        "segmented", principal.subject, project_id, task_id, os.path.basename(seg_path)
                    )
                    _s3_client.upload_file(seg_path, s3_segmented_key)
                except Exception:
                    logger.exception("[Pipeline] Segmented S3 upload failed task_id=%s", task_id)

            if not s3_segmented_key and isinstance(seg_data, dict):
                mask_path = seg_data.get("mask_path")
                if mask_path and not os.path.isabs(mask_path):
                    mask_path = str(Path(__file__).resolve().parent.parent / mask_path)
                if mask_path and _s3_client and os.path.exists(mask_path):
                    try:
                        s3_segmented_key = build_s3_key(
                            "segmented", principal.subject, project_id, task_id, os.path.basename(mask_path)
                        )
                        _s3_client.upload_file(mask_path, s3_segmented_key)
                    except Exception:
                        logger.exception("[Pipeline] Mask S3 upload failed task_id=%s", task_id)

            # Normalize output
            output = ComplianceOutput.from_pipeline_result(response, media_type)
            output_dict = output.model_dump()
            output_dict["s3_upload_key"] = source_view_url
            output_dict["s3_segmented_key"] = (
                generate_presigned_url(s3_segmented_key, _PRESIGNED_VIEW_SECONDS)
                if s3_segmented_key
                else None
            )
            output_dict["market"] = market
            output_dict["task_id"] = task_id

            # Optional synthetic-data demonstration only. It is deliberately
            # absent by default and cannot influence the authoritative rules,
            # LLM assessment, remediation, or recheck path.
            if ML_TRIAGE_ADVISORY_ENABLED and media_type == "text" and text:
                from jusads_compliance.ml_triage_advisory import classify_text
                output_dict["ml_triage_advisory"] = classify_text(text).to_dict()

            # Persist to Supabase
            _persist_check_record(
                task_id=task_id, project_id=project_id,
                media_type=media_type, market=market, ethnicity=ethnicity,
                age_group=age_group, platform=platform,
                response=output_dict,
                s3_upload_key=s3_upload_key, s3_segmented_key=s3_segmented_key,
            )

            logger.info("[Pipeline] ═══ RESULT PERSISTED ═══ task_id=%s", task_id)

            # Emit final result
            yield emit({
                "type": "result",
                "data": output_dict,
            })

        except Exception:
            logger.exception("[Pipeline] Error for task_id=%s", task_id)
            _tracker.fail_step(task_id, "pipeline", "COMPLIANCE_PIPELINE_FAILED")
            yield emit({
                "type": "error",
                "code": "COMPLIANCE_PIPELINE_FAILED",
                "message": "Compliance analysis could not be completed.",
            })
        finally:
            remove_temp_file(file_path)

    return StreamingResponse(
        generate_sse_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )








# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# POST /api/compliance/{task_id}/clone-voice
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.post("/api/compliance/{task_id}/clone-voice")
async def clone_voice_endpoint(
    task_id: str,
    principal: Principal = Depends(get_current_principal),
):
    """Clone the brand voice from the original audio of a compliance check.

    The cloned voice is stored persistently and reused for all future
    audio remediation on this project.
    """
    if not _supabase_store:
        return JSONResponse(status_code=503, content={"error": {"code": "DATASTORE_UNAVAILABLE", "message": "Service temporarily unavailable"}})

    try:
        check = get_authorized_compliance_check(
            _supabase_store, task_id, principal, write=True,
            fields="task_id, media_type, s3_upload_key, project_id",
        ).record
    except HTTPException:
        raise
    if check["media_type"] not in ("audio", "video"):
        return JSONResponse(status_code=400, content={"error": {"code": "VOICE_SOURCE_UNSUPPORTED", "message": "Voice cloning requires audio or video media"}})

    source_url = check.get("s3_upload_key", "")
    if not source_url:
        return JSONResponse(status_code=400, content={"error": {"code": "VOICE_SOURCE_MISSING", "message": "No source audio available"}})

    from jusads_compliance.voice_clone_manager import clone_brand_voice

    result = await clone_brand_voice(
        project_id=str(check["project_id"]),
        voice_name=f"Brand Voice - {task_id[:8]}",
        sample_audio_url=generate_presigned_url(source_url, _PRESIGNED_VIEW_SECONDS),
        sample_s3_key=source_url,
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
        return JSONResponse(status_code=502, content={"error": {"code": "VOICE_CLONE_FAILED", "message": "Voice cloning could not be completed"}})








# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET /api/compliance/{task_id}
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.get("/api/compliance/{task_id}")
async def get_results(
    task_id: str,
    principal: Principal = Depends(get_current_principal),
):
    """Get results for a previous compliance check.

    Tries the local JSON cache first, then falls back to Supabase.
    Always enriches with S3 URLs from the DB.
    """
    if not _supabase_store:
        return JSONResponse(status_code=503, content={"error": {"code": "DATASTORE_UNAVAILABLE", "message": "Service temporarily unavailable"}})
    authorized = get_authorized_compliance_check(
        _supabase_store, task_id, principal, write=False,
        fields="s3_upload_key, s3_segmented_key, s3_remix_key, result_json",
    )
    record = authorized.record
    result = dict(record.get("result_json") or {})
    if not result:
        return JSONResponse(status_code=404, content={"error": {"code": "RESOURCE_NOT_FOUND", "message": "Resource not found"}})
    for field in ("s3_upload_key", "s3_segmented_key", "s3_remix_key"):
        private_key = record.get(field)
        result[field] = generate_presigned_url(private_key, _PRESIGNED_VIEW_SECONDS) if private_key else None
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
    # Storage keys live in dedicated private-key columns.  Never persist a
    # short-lived presentation URL inside the durable compliance result.
    persist_response.pop("s3_upload_key", None)
    persist_response.pop("s3_segmented_key", None)
    persist_response.pop("s3_remix_key", None)
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
            # Keep a small, queryable evidence index alongside the immutable
            # raw result JSON.  This powers timelines and audit summaries
            # without asking the UI to parse model output again.
            violations = _normalize_violations(persist_response)
            try:
                _supabase_store.client.table("violations").delete().eq("task_id", task_id).execute()
                if violations:
                    _supabase_store.insert_violations(task_id, violations)
                logger.info("[Persist] Stored %d normalized violations for task=%s", len(violations), task_id)
            except Exception:
                # The compliance result remains authoritative even if the
                # optional query index is temporarily unavailable.
                logger.exception("[Persist] Failed to index violations for task=%s", task_id)
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


def _normalize_violations(result: dict) -> list[dict]:
    """Create stable audit rows from model indicators and timeline evidence."""

    indicators = [str(item).strip() for item in result.get("high_risk_indicator") or [] if str(item).strip()]
    timeline = result.get("violations_timeline") or []
    by_description: dict[str, dict] = {}
    for item in timeline:
        if not isinstance(item, dict):
            continue
        description = str(item.get("description") or item.get("type") or "").strip()
        if not description:
            continue
        by_description.setdefault(description.casefold(), item)

    risk_level = str(result.get("risk_level") or "moderate").strip().lower()
    severity = risk_level if risk_level in {"low", "moderate", "high", "critical"} else "moderate"
    rows: list[dict] = []
    for index, indicator in enumerate(indicators):
        evidence = by_description.get(indicator.casefold(), {})
        rows.append({
            "violation_index": index,
            "type": str(evidence.get("type") or "compliance_indicator")[:120],
            "severity": severity,
            "description": indicator[:2000],
            "start_time": evidence.get("start_seconds", evidence.get("start_time")),
            "end_time": evidence.get("end_seconds", evidence.get("end_time")),
        })
    return rows
