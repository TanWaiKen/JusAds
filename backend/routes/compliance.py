"""
routes/compliance.py
────────────────────
Compliance check endpoints: WebSocket streaming, check trigger, history,
results, media URLs, remediation.

Endpoints:
  - POST /api/compliance/check       → Invoke Compliance Pipeline
  - POST /api/compliance/{task_id}/remediate → Invoke Remediation Pipeline
  - GET  /api/compliance/history      → Paginated check history
  - GET  /api/compliance/{task_id}   → Single check result
  - GET  /api/media/{task_id}/{type} → Presigned media URL
  - WS   /ws/{task_id}              → Legacy WebSocket (retained for compat)
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

from fastapi import APIRouter, File, Form, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse

from jusads_compliance.utils import detect_media_type_from_filename
from shared.supabase_client import SupabaseComplianceStore
from shared.s3_client import S3MediaClient, build_s3_key
from shared.models import CheckRecord, ComplianceOutput, Compliance_State, Remediation_State
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
# POST /api/compliance/{task_id}/remediate
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.post("/api/compliance/{task_id}/remediate")
async def remediate_compliance(task_id: str):
    """Invoke the Remediation Pipeline for a completed compliance check.

    The Remediation Pipeline retrieves the compliance result by task_id,
    confirms aspect ratio (for image/video), performs media-specific
    remediation, and uploads the result to S3.

    Progress can be polled via GET /api/compliance/{task_id}/progress.
    """
    if not _remediation_runner:
        return JSONResponse(status_code=503, content={"error": "Remediation pipeline unavailable"})

    # Verify task_id exists in compliance_checks
    if _supabase_store:
        try:
            response = _supabase_store.client.table("compliance_checks").select(
                "task_id, status, media_type"
            ).eq("task_id", task_id).execute()
            rows = response.data or []
            if not rows:
                return JSONResponse(status_code=404, content={"error": f"Check not found: {task_id}"})
        except Exception as e:
            logger.error("[Remediate] DB lookup failed for %s: %s", task_id, e)
            return JSONResponse(status_code=500, content={"error": "Failed to verify task_id"})

    # Build Remediation_State TypedDict
    state: Remediation_State = {
        "task_id": task_id,
        "project_id": "",
        "media_type": "",
        "source_media_url": "",
        "compliance_result": {},
        "remediation_plan": {},
        "platform_target": "",
        "aspect_ratio": "",
        "strategy": "",
        "remediated_paths": [],
        "remix_url": "",
        "status": "pending",
    }

    async def run_remediation():
        try:
            result = await _remediation_runner.run_with_human_loop(task_id, state)
            if result and isinstance(result, dict):
                status = result.get("status", "remix_failed")
                logger.info(
                    "[Remediate] Pipeline complete for task_id=%s, status=%s",
                    task_id, status,
                )
            else:
                logger.warning("[Remediate] Pipeline returned None for task_id=%s", task_id)
        except Exception as e:
            logger.error("[Remediate] Error for %s: %s", task_id, e)

    asyncio.create_task(run_remediation())

    return JSONResponse(content={
        "task_id": task_id,
        "status": "remediating",
        "message": "Remediation pipeline started. Poll progress via GET /api/compliance/{task_id}/progress.",
    })


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# POST /api/compliance/{task_id}/smart-remediate
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.post("/api/compliance/{task_id}/smart-remediate")
async def smart_remediate(task_id: str):
    """Intelligent Remediation — AI decides the tool and severity.

    Unlike /remediate (which runs a fixed pipeline), this endpoint uses
    the AI Tool Router to classify violation severity and pick the
    cheapest/fastest tool(s) that can fix the issues.

    Flow:
      1. Fetch compliance result
      2. AI Tool Router classifies severity + selects tools
      3. Execute selected tools sequentially
      4. Upload result, create new version

    Returns:
      SSE stream with routing decision + execution progress + final result.
    """
    if not _supabase_store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    # Fetch the compliance check record
    try:
        response = _supabase_store.client.table("compliance_checks").select(
            "task_id, media_type, market, ethnicity, age_group, platform, "
            "result_json, s3_upload_key, project_id, status"
        ).eq("task_id", task_id).execute()
        rows = response.data or []
        if not rows:
            return JSONResponse(status_code=404, content={"error": f"Check not found: {task_id}"})
    except Exception as e:
        logger.error("[SmartRemediate] DB lookup failed: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})

    check = rows[0]
    media_type = check["media_type"]
    result_json = check.get("result_json") or {}
    market = check.get("market", "malaysia")
    ethnicity = check.get("ethnicity", "malay")
    project_id = str(check.get("project_id", ""))
    source_url = check.get("s3_upload_key", "")

    violations = result_json.get("high_risk_indicator", [])
    risk_level = result_json.get("risk_level", "Moderate")
    risk_percentage = result_json.get("risk_percentage", 50)
    suggestion = result_json.get("suggestion", "")
    localization_plan = result_json.get("localization_plan", "")
    violations_timeline = result_json.get("violations_timeline")

    async def generate_events():
        """SSE event generator for smart remediation."""
        def emit(event: dict) -> str:
            return f"data: {json.dumps(event)}\n\n"

        try:
            # Step 1: AI Tool Router
            yield emit({
                "type": "status",
                "step": "routing",
                "message": "AI analyzing violations and selecting tools...",
            })

            from jusads_compliance.tool_router import route_remediation

            routing_decision = await route_remediation(
                media_type=media_type,
                violations=violations,
                risk_level=risk_level,
                risk_percentage=risk_percentage,
                suggestion=suggestion,
                localization_plan=localization_plan,
                violations_timeline=violations_timeline,
            )

            yield emit({
                "type": "routing_decision",
                "severity": routing_decision.overall_severity,
                "tools": [t.model_dump() for t in routing_decision.tools],
                "strategy": routing_decision.strategy_summary,
                "confidence": routing_decision.confidence,
            })

            # Step 2: Execute remediation
            yield emit({
                "type": "status",
                "step": "executing",
                "message": f"Executing {len(routing_decision.tools)} tool(s)...",
            })

            from jusads_compliance.remediation_executor import execute_remediation

            exec_result = await execute_remediation(
                routing_decision=routing_decision,
                check_id=task_id,
                source_media_url=source_url,
                project_id=project_id,
                user_email=project_id,
                compliance_result=result_json,
                market=market,
                ethnicity=ethnicity,
                gender="female",  # Default; could be passed from frontend
            )

            # Step 3: Emit final result
            yield emit({
                "type": "result",
                "status": exec_result.get("status"),
                "output_url": exec_result.get("output_url"),
                "tools_applied": exec_result.get("tools_applied", []),
                "tools_failed": exec_result.get("tools_failed", []),
                "strategy_summary": exec_result.get("strategy_summary", ""),
                "overall_severity": exec_result.get("overall_severity", ""),
                "confidence": exec_result.get("confidence", 0),
            })

        except Exception as e:
            logger.error("[SmartRemediate] Error for %s: %s", task_id, e, exc_info=True)
            yield emit({
                "type": "error",
                "message": f"Smart remediation failed: {str(e)[:200]}",
            })

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
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
# GET /api/compliance/{task_id}/routing-preview
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.get("/api/compliance/{task_id}/routing-preview")
async def routing_preview(task_id: str):
    """Preview what the AI Tool Router would decide without executing anything.

    Useful for showing the user what tools will be applied before they
    confirm the remediation.
    """
    if not _supabase_store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        response = _supabase_store.client.table("compliance_checks").select(
            "task_id, media_type, result_json"
        ).eq("task_id", task_id).execute()
        rows = response.data or []
        if not rows:
            return JSONResponse(status_code=404, content={"error": "Check not found"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

    check = rows[0]
    result_json = check.get("result_json") or {}

    from jusads_compliance.tool_router import route_remediation

    routing_decision = await route_remediation(
        media_type=check["media_type"],
        violations=result_json.get("high_risk_indicator", []),
        risk_level=result_json.get("risk_level", "Moderate"),
        risk_percentage=result_json.get("risk_percentage", 50),
        suggestion=result_json.get("suggestion", ""),
        localization_plan=result_json.get("localization_plan", ""),
        violations_timeline=result_json.get("violations_timeline"),
    )

    return JSONResponse(content={
        "task_id": task_id,
        "media_type": check["media_type"],
        "routing": routing_decision.model_dump(),
    })


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET /api/compliance/history
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.get("/api/compliance/history")
async def get_compliance_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Paginated compliance check history."""
    user_id = "demo_user"
    if not _supabase_store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})
    try:
        history = _supabase_store.get_history(user_id=user_id, page=page, page_size=page_size)
        return JSONResponse(content={
            "records": [r.model_dump(mode="json") for r in history.records],
            "total": history.total,
            "page": history.page,
            "page_size": history.page_size,
        })
    except Exception as e:
        logger.error("History fetch failed: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


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
# GET /api/media/{task_id}/{asset_type}
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.get("/api/media/{task_id}/{asset_type}")
async def get_media_url(task_id: str, asset_type: str):
    """Presigned URL for a compliance check media asset (original/segmented/remixed)."""
    if asset_type not in ("original", "remixed", "segmented"):
        return JSONResponse(status_code=400, content={"error": "asset_type must be original, remixed, or segmented"})

    if not _supabase_store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        response = (
            _supabase_store.client.table("compliance_checks")
            .select("s3_upload_key, s3_segmented_key, s3_remix_key")
            .eq("task_id", task_id)
            .execute()
        )
        if not response.data:
            return JSONResponse(status_code=404, content={"error": f"Check not found: {task_id}"})

        record = response.data[0]
        key_map = {"original": "s3_upload_key", "segmented": "s3_segmented_key", "remixed": "s3_remix_key"}
        s3_key = record.get(key_map[asset_type])

        if not s3_key:
            return JSONResponse(status_code=404, content={"error": f"No {asset_type} media for {task_id}"})

        # The DB might store full public URLs instead of just the object key
        if "amazonaws.com/" in s3_key:
            import urllib.parse
            s3_key = s3_key.split("amazonaws.com/")[1]
            s3_key = urllib.parse.unquote(s3_key)

        client = S3MediaClient()
        url = client.generate_presigned_url(s3_key, expiry_seconds=3600)
        return RedirectResponse(url=url)
    except Exception as e:
        logger.error("Media URL failed for %s/%s: %s", task_id, asset_type, e)
        return JSONResponse(status_code=500, content={"error": str(e)})



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
