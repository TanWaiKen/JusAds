"""
routes/compliance.py
────────────────────
Compliance check endpoints: WebSocket streaming, check trigger, history,
results, media URLs, remediation.

Endpoints:
  - POST /api/compliance/check       → Invoke Compliance Pipeline
  - POST /api/compliance/{check_id}/remediate → Invoke Remediation Pipeline
  - GET  /api/compliance/history      → Paginated check history
  - GET  /api/compliance/{check_id}   → Single check result
  - GET  /api/media/{check_id}/{type} → Presigned media URL
  - WS   /ws/{check_id}              → Legacy WebSocket (retained for compat)
"""

import asyncio
import json
import logging
import os
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

# ── Shared state (injected from app.py) ───────────────────────────────────────
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
    _tracker = ProgressTracker()

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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# WEBSOCKET (sends result once pipeline completes)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Store completed results for WebSocket delivery
_completed_results: Dict[str, dict] = {}


@router.websocket("/ws/{check_id}")
async def websocket_endpoint(websocket: WebSocket, check_id: str):
    """WebSocket for compliance check result delivery and human decisions.

    Polls _completed_results until the pipeline finishes, then sends the
    result event and closes. Also handles human-in-the-loop resume.
    """
    await websocket.accept()
    try:
        while True:
            # Check if result is ready (non-blocking poll)
            if check_id in _completed_results:
                result = _completed_results.pop(check_id)
                await websocket.send_json({"type": "result", "data": result})
                await websocket.close()
                return

            # Wait for client messages with a short timeout
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=1.0)
                action = data.get("action")
                if action == "resume":
                    decision = data.get("decision", "ok")
                    _decision_store[check_id] = decision
                    event = _pending_decisions.get(check_id)
                    if event:
                        event.set()
                    logger.info("[WS] Resume for %s: %s", check_id, decision)
                elif action == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                # No message from client — just loop and check for results again
                continue
    except WebSocketDisconnect:
        _pending_decisions.pop(check_id, None)
        _decision_store.pop(check_id, None)
        logger.info("[WS] Disconnected: %s", check_id)


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
    """Trigger a compliance check. Returns check_id + WebSocket URL for streaming."""
    check_id = uuid.uuid4().hex[:8]
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
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix=f"{check_id}_")
        tmp.write(file_content)
        tmp.close()
        file_path = tmp.name

        if _s3_client:
            try:
                s3_key = build_s3_key("upload", username, project_id, check_id, filename)
                _s3_client.upload_file(file_path, s3_key)
                s3_upload_key = _s3_client.get_public_url(s3_key)
                logger.info("[API] S3 upload: %s", s3_upload_key)
            except Exception as e:
                logger.warning("[API] S3 upload failed: %s", e)

        media_type = detect_media_type_from_filename(filename)
    else:
        return JSONResponse(status_code=400, content={"error": "Provide 'text' or 'file'"})

    logger.info("[API] check_id=%s, media_type=%s", check_id, media_type)

    # Build Compliance_State TypedDict for the new pipeline
    state: Compliance_State = {
        "session_id": check_id,
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
        "check_id": check_id,
        "remediated_path": "",
        "remix_iteration": 0,
    }

    async def run_pipeline():
        try:
            result = await _compliance_runner.run_with_human_loop(check_id, state)
            if result and isinstance(result, dict):
                response = result.get("result", {})

                # Upload segmented mask to S3
                s3_segmented_url = None
                seg_data = response.get("segmentation")
                seg_path = seg_data.get("segmented_image_path") if isinstance(seg_data, dict) else None

                if seg_path:
                    # Resolve relative paths against the backend root
                    if not os.path.isabs(seg_path):
                        seg_path = str(Path(__file__).resolve().parent.parent / seg_path)
                    logger.info("[Pipeline] Segmented path: %s, exists=%s", seg_path, os.path.exists(seg_path))

                if seg_path and _s3_client and os.path.exists(seg_path):
                    try:
                        s3_seg_key = build_s3_key("segmented", username, project_id, check_id, os.path.basename(seg_path))
                        s3_segmented_url = _s3_client.upload_file_public(seg_path, s3_seg_key)
                        logger.info("[Pipeline] Segmented uploaded: %s", s3_segmented_url)
                    except Exception as e:
                        logger.warning("[Pipeline] Segmented S3 upload failed: %s", e)

                # Also try mask_path from CLIPSeg segmentation
                if not s3_segmented_url and isinstance(seg_data, dict):
                    mask_path = seg_data.get("mask_path")
                    if mask_path and not os.path.isabs(mask_path):
                        mask_path = str(Path(__file__).resolve().parent.parent / mask_path)
                    if mask_path and _s3_client and os.path.exists(mask_path):
                        try:
                            s3_seg_key = build_s3_key("segmented", username, project_id, check_id, os.path.basename(mask_path))
                            s3_segmented_url = _s3_client.upload_file_public(mask_path, s3_seg_key)
                            logger.info("[Pipeline] Mask uploaded as segmented: %s", s3_segmented_url)
                        except Exception as e:
                            logger.warning("[Pipeline] Mask S3 upload failed: %s", e)

                # Normalize output and inject S3 URLs directly into result
                output = ComplianceOutput.from_pipeline_result(response, media_type)
                output_dict = output.model_dump()
                output_dict["s3_upload_key"] = s3_upload_key
                output_dict["s3_segmented_key"] = s3_segmented_url
                output_dict["market"] = market
                logger.info("[Pipeline] Built output_dict: s3_upload_key=%s, s3_segmented_key=%s", s3_upload_key, s3_segmented_url)

                # Persist to Supabase
                _persist_check_record(
                    check_id=check_id, username=username, project_id=project_id,
                    media_type=media_type, market=market, ethnicity=ethnicity,
                    age_group=age_group, platform=platform,
                    response=output_dict,
                    s3_upload_key=s3_upload_key, s3_segmented_key=s3_segmented_url,
                )

                logger.info("[Pipeline] ═══ RESULT PERSISTED ═══")
                logger.info("[Pipeline] check_id=%s, s3_upload_key=%s", check_id, output_dict.get("s3_upload_key"))
                logger.info("[Pipeline] s3_segmented_key=%s", output_dict.get("s3_segmented_key"))
                logger.info("[Pipeline] risk_percentage=%s, risk_level=%s", output_dict.get("risk_percentage"), output_dict.get("risk_level"))
                logger.info("[Pipeline] ═══ END ═══")

                # Store result for WebSocket delivery
                _completed_results[check_id] = {
                    "status": output_dict.get("status", "checked"),
                    "result": output_dict,
                    "media_type": media_type,
                    "market": market,
                }

        except Exception as e:
            logger.error("[Pipeline] Error for %s: %s", check_id, e)

    asyncio.create_task(run_pipeline())

    return JSONResponse(content={
        "check_id": check_id,
        "media_type": media_type,
        "status": "processing",
        "ws_url": f"/ws/{check_id}",
        "s3_upload_key": s3_upload_key,
    })


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# POST /api/compliance/{check_id}/remediate
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.post("/api/compliance/{check_id}/remediate")
async def remediate_compliance(check_id: str):
    """Invoke the Remediation Pipeline for a completed compliance check.

    The Remediation Pipeline retrieves the compliance result by check_id,
    confirms aspect ratio (for image/video), performs media-specific
    remediation, and uploads the result to S3.

    Progress can be polled via GET /api/compliance/{check_id}/progress.
    """
    if not _remediation_runner:
        return JSONResponse(status_code=503, content={"error": "Remediation pipeline unavailable"})

    # Verify check_id exists in compliance_checks
    if _supabase_store:
        try:
            response = _supabase_store.client.table("compliance_checks").select(
                "check_id, status, media_type"
            ).eq("check_id", check_id).execute()
            rows = response.data or []
            if not rows:
                return JSONResponse(status_code=404, content={"error": f"Check not found: {check_id}"})
        except Exception as e:
            logger.error("[Remediate] DB lookup failed for %s: %s", check_id, e)
            return JSONResponse(status_code=500, content={"error": "Failed to verify check_id"})

    # Build Remediation_State TypedDict
    state: Remediation_State = {
        "check_id": check_id,
        "media_type": "",
        "source_media_url": "",
        "compliance_result": {},
        "remediation_plan": {},
        "platform_target": "",
        "aspect_ratio": "",
        "strategy": "",
        "remediated_paths": [],
        "status": "pending",
    }

    async def run_remediation():
        try:
            result = await _remediation_runner.run_with_human_loop(check_id, state)
            if result and isinstance(result, dict):
                status = result.get("status", "remix_failed")
                logger.info(
                    "[Remediate] Pipeline complete for check_id=%s, status=%s",
                    check_id, status,
                )
            else:
                logger.warning("[Remediate] Pipeline returned None for check_id=%s", check_id)
        except Exception as e:
            logger.error("[Remediate] Error for %s: %s", check_id, e)

    asyncio.create_task(run_remediation())

    return JSONResponse(content={
        "check_id": check_id,
        "status": "remediating",
        "message": "Remediation pipeline started. Poll progress via GET /api/compliance/{check_id}/progress.",
    })


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# POST /api/compliance/{check_id}/smart-remediate
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.post("/api/compliance/{check_id}/smart-remediate")
async def smart_remediate(check_id: str):
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
            "check_id, media_type, market, ethnicity, age_group, platform, "
            "result_json, s3_upload_key, user_email, project_id, status"
        ).eq("check_id", check_id).execute()
        rows = response.data or []
        if not rows:
            return JSONResponse(status_code=404, content={"error": f"Check not found: {check_id}"})
    except Exception as e:
        logger.error("[SmartRemediate] DB lookup failed: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})

    check = rows[0]
    media_type = check["media_type"]
    result_json = check.get("result_json") or {}
    market = check.get("market", "malaysia")
    ethnicity = check.get("ethnicity", "malay")
    project_id = str(check.get("project_id", ""))
    user_email = check.get("user_email", "unknown")
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
                check_id=check_id,
                source_media_url=source_url,
                project_id=project_id,
                user_email=user_email,
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
            logger.error("[SmartRemediate] Error for %s: %s", check_id, e, exc_info=True)
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
# POST /api/compliance/{check_id}/clone-voice
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.post("/api/compliance/{check_id}/clone-voice")
async def clone_voice_endpoint(check_id: str):
    """Clone the brand voice from the original audio of a compliance check.

    The cloned voice is stored persistently and reused for all future
    audio remediation on this project.
    """
    if not _supabase_store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        response = _supabase_store.client.table("compliance_checks").select(
            "check_id, media_type, s3_upload_key, project_id"
        ).eq("check_id", check_id).execute()
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
        voice_name=f"Brand Voice - {check_id}",
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
# GET /api/compliance/{check_id}/routing-preview
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.get("/api/compliance/{check_id}/routing-preview")
async def routing_preview(check_id: str):
    """Preview what the AI Tool Router would decide without executing anything.

    Useful for showing the user what tools will be applied before they
    confirm the remediation.
    """
    if not _supabase_store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        response = _supabase_store.client.table("compliance_checks").select(
            "check_id, media_type, result_json"
        ).eq("check_id", check_id).execute()
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
        "check_id": check_id,
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
# GET /api/compliance/{check_id}
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.get("/api/compliance/{check_id}")
async def get_results(check_id: str):
    """Get results for a previous compliance check.

    Tries the local JSON cache first, then falls back to Supabase.
    Always enriches with S3 URLs from the DB.
    """
    result: dict = {}

    # Try local JSON cache
    result_path = RESULTS_DIR / f"{check_id}.json"
    if result_path.exists():
        with open(result_path, "r", encoding="utf-8") as f:
            result = json.load(f)

    # Enrich with S3 URLs from Supabase (always authoritative for URLs)
    if _supabase_store:
        try:
            response = _supabase_store.client.table("compliance_checks").select(
                "s3_upload_key, s3_segmented_key, s3_remix_key, result_json"
            ).eq("check_id", check_id).execute()
            if response.data:
                record = response.data[0]
                if not result and record.get("result_json"):
                    result = record["result_json"]
                result["s3_upload_key"] = record.get("s3_upload_key")
                result["s3_segmented_key"] = record.get("s3_segmented_key")
                result["s3_remix_key"] = record.get("s3_remix_key")
        except Exception as e:
            logger.warning("[Results] DB fetch failed for %s: %s", check_id, e)

    if not result:
        return JSONResponse(status_code=404, content={"error": "Not found"})

    return JSONResponse(content=result)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET /api/media/{check_id}/{asset_type}
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.get("/api/media/{check_id}/{asset_type}")
async def get_media_url(check_id: str, asset_type: str):
    """Presigned URL for a compliance check media asset (original/segmented/remixed)."""
    if asset_type not in ("original", "remixed", "segmented"):
        return JSONResponse(status_code=400, content={"error": "asset_type must be original, remixed, or segmented"})

    if not _supabase_store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        response = (
            _supabase_store.client.table("compliance_checks")
            .select("s3_upload_key, s3_segmented_key, s3_remix_key")
            .eq("check_id", check_id)
            .execute()
        )
        if not response.data:
            return JSONResponse(status_code=404, content={"error": f"Check not found: {check_id}"})

        record = response.data[0]
        key_map = {"original": "s3_upload_key", "segmented": "s3_segmented_key", "remixed": "s3_remix_key"}
        s3_key = record.get(key_map[asset_type])

        if not s3_key:
            return JSONResponse(status_code=404, content={"error": f"No {asset_type} media for {check_id}"})

        client = S3MediaClient()
        url = client.generate_presigned_url(s3_key, expiry_seconds=3600)
        return RedirectResponse(url=url)
    except Exception as e:
        logger.error("Media URL failed for %s/%s: %s", check_id, asset_type, e)
        return JSONResponse(status_code=500, content={"error": str(e)})



# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PERSISTENCE HELPER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _persist_check_record(
    check_id: str, username: str, project_id: str,
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
        check_id=check_id,
        user_email=username,
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
        logger.warning("[Persist] No store, skipping %s", check_id)
        return

    try:
        success = _supabase_store.insert_check(record)
        if success:
            logger.info("[Persist] Inserted: %s", check_id)
            try:
                _supabase_store.create_task(
                    project_id=project_id, task_type="compliance",
                    status="checked", summary=f"Compliance check - {media_type} ({market})",
                    reference_id=check_id,
                )
            except Exception as e:
                logger.warning("[Persist] Task creation failed for %s: %s", check_id, e)
    except Exception as e:
        logger.warning("[Persist] Failed for %s: %s", check_id, e)
