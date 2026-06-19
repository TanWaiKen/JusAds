"""
JusAds Compliance API
======================
Uses the agent/ pipeline for compliance checks with WebSocket streaming,
S3 storage, Supabase persistence, and human-in-the-loop decision flow.

Usage:
  uvicorn langgraph_api:app --reload --port 8000
"""

import asyncio
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from dotenv import load_dotenv

# Load .env from backend/ directory
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

from fastapi import FastAPI, File, Form, Query, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError, field_validator

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent.utils import detect_media_type_from_filename
from agent.ws_manager import ConnectionManager
from agent.supabase_client import SupabaseComplianceStore
from agent.s3_client import S3MediaClient, build_s3_key
from agent.validators import validate_file_size, validate_user_quota
from agent.fallback_queue import FallbackQueue
from agent.models import CheckRecord, CreateTaskRequest, UpdatePipelineRequest, UpdateProjectRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="JusAds Compliance API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ValidationError)
async def pydantic_validation_exception_handler(request, exc: ValidationError) -> JSONResponse:
    """Return 400 for Pydantic validation errors."""
    errors = exc.errors()
    messages = [e.get("msg", "Validation error") for e in errors]
    return JSONResponse(status_code=400, content={"error": "; ".join(messages)})


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return 400 for request validation errors (FastAPI body/query param validation)."""
    errors = exc.errors()
    messages = [e.get("msg", "Validation error") for e in errors]
    return JSONResponse(status_code=400, content={"error": "; ".join(messages)})

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# S3 / SUPABASE / FALLBACK CLIENTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Initialize S3 client (graceful — logs warning if credentials missing)
try:
    s3_client = S3MediaClient()
    logger.info("[Init] S3MediaClient initialized successfully.")
except Exception as _s3_init_err:
    logger.warning("S3MediaClient initialization failed: %s — S3 uploads will be skipped.", _s3_init_err)
    s3_client = None  # type: ignore[assignment]

# Initialize Supabase client (graceful — logs warning if credentials missing)
try:
    supabase_store = SupabaseComplianceStore()
    logger.info("[Init] SupabaseComplianceStore initialized successfully.")
except Exception as _supa_init_err:
    logger.warning("SupabaseComplianceStore initialization failed: %s — persistence will fallback to local.", _supa_init_err)
    supabase_store = None  # type: ignore[assignment]

# Fallback queue for retrying failed S3/Supabase operations
fallback_queue = FallbackQueue(
    supabase_client=supabase_store,
    s3_client=s3_client,
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# WEBSOCKET CONNECTION MANAGER & DECISION COORDINATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

manager = ConnectionManager()

# Decision coordination for human-in-the-loop
pending_decisions: Dict[str, asyncio.Event] = {}
decision_store: Dict[str, str] = {}

# Pipeline runner instance
from agent.pipeline_runner import PipelineRunner  # noqa: E402

pipeline_runner = PipelineRunner(
    manager=manager,
    pending_decisions=pending_decisions,
    decision_store=decision_store,
)


async def handle_resume(check_id: str, decision: str) -> None:
    """Store a human decision and signal the pipeline to continue."""
    decision_store[check_id] = decision
    event = pending_decisions.get(check_id)
    if event:
        event.set()
    logger.info(f"[WS] Resume received for {check_id}: decision={decision}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# WEBSOCKET ENDPOINT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@app.websocket("/ws/{check_id}")
async def websocket_endpoint(websocket: WebSocket, check_id: str):
    """Bidirectional WebSocket for compliance check events and human decisions."""
    await manager.connect(check_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")
            if action == "resume":
                await handle_resume(check_id, data.get("decision", "ok"))
            elif action == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(check_id)
        pending_decisions.pop(check_id, None)
        decision_store.pop(check_id, None)
        logger.info(f"[WS] Client disconnected: {check_id}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DIRECTORIES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

UPLOAD_DIR = Path("assets/uploads")
CLIPS_DIR = Path("assets/clips")
RESULTS_DIR = Path("assets/results")

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
CLIPS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/clips", StaticFiles(directory=str(CLIPS_DIR)), name="clips")
app.mount("/results", StaticFiles(directory=str(RESULTS_DIR)), name="results")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMPLIANCE CHECK ENDPOINT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@app.post("/api/compliance/check")
async def check_compliance(
    file: UploadFile = File(None),
    text: str = Form(None),
    market: str = Form("malaysia"),
    ethnicity: str = Form("malay"),
    age_group: str = Form("all_ages"),
    username: str = Form("anonymous"),
    project_id: str = Form(None),
):
    """
    Single entry point for all compliance checks.
    Routes through the agent pipeline based on media type.

    Returns:
        JSON with check_id, media_type, and instructions to connect via WebSocket
        for real-time streaming updates.
    """
    check_id = uuid.uuid4().hex[:8]
    s3_upload_key: str | None = None

    if not project_id:
        # No project_id provided — create an ad-hoc project for this check
        if supabase_store:
            try:
                proj = supabase_store.create_project(
                    user_id=username,
                    name="Untitled",
                    media_type="compliance",
                )
                project_id = proj["id"]
            except Exception:
                project_id = str(uuid.uuid4())
        else:
            project_id = str(uuid.uuid4())

    # ── Input validation ──────────────────────────────────────────────────────
    if text and not file:
        media_type = "text"
        file_path = ""
        filename = ""
    elif file:
        filename = file.filename or "upload"

        # Read file content
        file_content = await file.read()
        file_size = len(file_content)

        # Validate file size (raises HTTPException 400 if > 100 MB)
        validate_file_size(file_size)

        # Validate user quota
        if s3_client:
            try:
                validate_user_quota(username, file_size, s3_client)
            except Exception as quota_err:
                from fastapi import HTTPException
                if isinstance(quota_err, HTTPException):
                    raise
                logger.warning("Quota check failed (non-blocking): %s", quota_err)

        # Save file locally
        upload_filename = f"{check_id}_{filename}"
        file_path = str(UPLOAD_DIR / upload_filename)
        with open(file_path, "wb") as f:
            f.write(file_content)

        # ── S3 upload (with fallback to local) ────────────────────────────────
        if s3_client:
            try:
                s3_key = build_s3_key(
                    asset_type="upload",
                    username=username,
                    project_id=project_id,
                    check_id=check_id,
                    filename=filename,
                )
                s3_client.upload_file(file_path, s3_key)
                s3_upload_key = s3_client.get_public_url(s3_key)
                logger.info("[API] S3 upload succeeded: %s", s3_upload_key)
            except Exception as s3_err:
                logger.warning("[API] S3 upload failed — falling back to local: %s", s3_err)
                fallback_queue.queue_s3_upload(file_path, build_s3_key(
                    asset_type="upload", username=username,
                    project_id=project_id, check_id=check_id, filename=filename,
                ))

        # Detect media type from filename
        media_type = detect_media_type_from_filename(filename)
    else:
        return JSONResponse(status_code=400, content={"error": "Provide either 'text' or 'file'"})

    logger.info(f"[API] check_id={check_id}, media_type={media_type}, file={filename}")

    # Return immediately with check_id — client connects via WebSocket for streaming
    # Also start the pipeline in the background
    from agent.data_model import ComplianceState

    state = ComplianceState(
        session_id=check_id,
        media_type=media_type,
        input_path=file_path,
        text_input=text or "",
        market=market,
        platform="general",
        ethnicity=ethnicity,
        age_group=age_group,
    )

    # Run pipeline in background task
    async def run_pipeline():
        try:
            # Wait for the client to connect via WebSocket before starting the pipeline.
            # The client receives the check_id from this response, then opens a WebSocket.
            # Without this delay, pipeline events are emitted before anyone is listening.
            max_wait = 10.0  # seconds
            interval = 0.2
            elapsed = 0.0
            while elapsed < max_wait:
                if manager.get_connection(check_id):
                    logger.info(f"[Pipeline] Client connected for {check_id} after {elapsed:.1f}s")
                    break
                await asyncio.sleep(interval)
                elapsed += interval
            else:
                logger.warning(f"[Pipeline] No client connected for {check_id} after {max_wait}s — running anyway")

            result = await pipeline_runner.run_with_human_loop(check_id, state)
            if result:
                response = result.result if hasattr(result, 'result') else {}

                # Upload segmented image to S3
                s3_segmented_url = None
                segmented_path = response.get("segmentation", {}).get("segmented_image_path") if isinstance(response.get("segmentation"), dict) else None
                if segmented_path and s3_client and os.path.exists(segmented_path):
                    try:
                        s3_seg_key = build_s3_key(
                            asset_type="segmented",
                            username=username,
                            project_id=project_id,
                            check_id=check_id,
                            filename=os.path.basename(segmented_path),
                        )
                        s3_segmented_url = s3_client.upload_file_public(segmented_path, s3_seg_key)
                        logger.info("[Pipeline] Segmented uploaded to S3: %s", s3_segmented_url)
                    except Exception as seg_err:
                        logger.warning("[Pipeline] Segmented S3 upload failed: %s", seg_err)

                # Send enriched result with image URLs via WS
                # (pipeline_runner already sent a basic result, but we send media_urls if still connected)
                await manager.send_message(check_id, {
                    "type": "media_urls",
                    "s3_upload_key": s3_upload_key,
                    "s3_segmented_key": s3_segmented_url,
                })

                # Persist to Supabase
                _persist_check_record(
                    check_id=check_id,
                    username=username,
                    project_id=project_id,
                    media_type=media_type,
                    market=market,
                    ethnicity=ethnicity,
                    age_group=age_group,
                    response=response,
                    s3_upload_key=s3_upload_key,
                    s3_segmented_key=s3_segmented_url,
                    violations=[],
                )
        except Exception as e:
            logger.error(f"[Pipeline] Error for {check_id}: {e}")
            await manager.send_error(check_id, "pipeline", str(e)[:200], can_continue=False)

    asyncio.create_task(run_pipeline())

    return JSONResponse(content={
        "check_id": check_id,
        "media_type": media_type,
        "status": "processing",
        "message": "Connect to WebSocket for real-time updates",
        "ws_url": f"/ws/{check_id}",
        "s3_upload_key": s3_upload_key,
    })


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PROJECT MODELS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class CreateProjectRequest(BaseModel):
    """Request body for POST /api/projects."""

    name: str
    media_type: str
    username: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate project name is non-empty and ≤255 characters."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Project name cannot be empty")
        if len(stripped) > 255:
            raise ValueError("Project name cannot exceed 255 characters")
        return stripped

    @field_validator("media_type")
    @classmethod
    def validate_media_type(cls, v: str) -> str:
        """Validate media_type is one of the allowed values."""
        valid = {"compliance", "generation"}
        if v not in valid:
            raise ValueError(f"media_type must be one of: {', '.join(sorted(valid))}")
        return v


class ProjectResponse(BaseModel):
    """Response body for project endpoints."""

    id: str
    user_id: str
    name: str
    media_type: str
    created_at: str
    updated_at: str


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PROJECT ENDPOINTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@app.post("/api/projects")
async def create_project(body: CreateProjectRequest) -> JSONResponse:
    """Create a new project. Persists to Supabase projects table.

    Returns 201 with the created project including generated UUID.
    Returns 400 if validation fails (empty name, invalid media_type).
    Returns 503 if Supabase is unavailable.
    """
    if not supabase_store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        result = supabase_store.create_project(
            user_id=body.username,
            name=body.name,
            media_type=body.media_type,
        )
        return JSONResponse(status_code=201, content=result)
    except Exception as e:
        logger.error("Failed to create project: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/projects")
async def list_projects(username: str = Query(...)) -> JSONResponse:
    """List all projects for a user, sorted by created_at descending.

    Returns 503 if Supabase is unavailable.
    """
    if not supabase_store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        projects = supabase_store.get_projects(user_id=username)
        return JSONResponse(content=projects)
    except Exception as e:
        logger.error("Failed to list projects: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/projects/{project_id}/checks")
async def get_project_checks(project_id: str) -> JSONResponse:
    """Fetch compliance checks for a specific project, ordered by created_at descending.

    Returns 503 if Supabase is unavailable.
    """
    if not supabase_store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        checks = supabase_store.get_project_checks(project_id=project_id)
        return JSONResponse(content=checks)
    except Exception as e:
        logger.error("Failed to get project checks: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TASK ENDPOINTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@app.get("/api/projects/{project_id}/tasks")
async def list_tasks(project_id: str) -> JSONResponse:
    """List all tasks for a project, ordered by created_at descending.

    Returns unified task summaries (id, type, status, summary, created_at).
    Returns 503 if Supabase is unavailable.
    """
    if not supabase_store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        tasks = supabase_store.list_tasks(project_id=project_id)
        return JSONResponse(content=tasks)
    except Exception as e:
        logger.error("Failed to list tasks for project %s: %s", project_id, e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/projects/{project_id}/tasks/{task_id}")
async def get_task_detail(project_id: str, task_id: str) -> JSONResponse:
    """Get full task detail with type-specific data.

    For compliance tasks, includes compliance check results and violations.
    For generation tasks, includes pipeline_state.
    Returns 404 if not found, 503 if Supabase is unavailable.
    """
    if not supabase_store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        task = supabase_store.get_task_detail(project_id=project_id, task_id=task_id)
        if task is None:
            return JSONResponse(status_code=404, content={"error": "Task not found"})
        return JSONResponse(content=task)
    except Exception as e:
        logger.error("Failed to get task %s: %s", task_id, e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/projects/{project_id}/tasks")
async def create_task(project_id: str, body: CreateTaskRequest) -> JSONResponse:
    """Create a new generation task with an empty pipeline.

    Returns 201 with the created task.
    Returns 503 if Supabase is unavailable.
    """
    if not supabase_store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        task = supabase_store.create_task(
            project_id=project_id,
            task_type=body.type,
            status="created",
            summary=f"New {body.type} task",
            pipeline_state={"nodes": [], "edges": [], "viewport": {"panX": 0, "panY": 0, "zoom": 1}} if body.type == "generation" else None,
        )
        return JSONResponse(status_code=201, content=task)
    except Exception as e:
        logger.error("Failed to create task for project %s: %s", project_id, e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.put("/api/projects/{project_id}/tasks/{task_id}/pipeline")
async def update_task_pipeline(project_id: str, task_id: str, body: UpdatePipelineRequest) -> JSONResponse:
    """Persist generation pipeline graph state and status.

    Returns 200 on success, 404 if task not found, 503 if Supabase unavailable.
    """
    if not supabase_store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        success = supabase_store.update_task_pipeline(
            project_id=project_id,
            task_id=task_id,
            status=body.status,
            pipeline_state=body.pipeline_state,
        )
        if not success:
            return JSONResponse(status_code=404, content={"error": "Task not found"})
        return JSONResponse(content={"status": "updated"})
    except Exception as e:
        logger.error("Failed to update pipeline for task %s: %s", task_id, e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.patch("/api/projects/{project_id}")
async def update_project(project_id: str, body: UpdateProjectRequest) -> JSONResponse:
    """Update project name.

    Returns 200 with the updated project row.
    Returns 503 if Supabase is unavailable.
    """
    if not supabase_store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        result = supabase_store.update_project_name(
            project_id=project_id,
            name=body.name,
        )
        return JSONResponse(content=result)
    except Exception as e:
        logger.error("Failed to update project %s: %s", project_id, e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str) -> JSONResponse:
    """Delete a project and all its associated data (cascade).

    Returns 200 on success, 503 if Supabase is unavailable.
    """
    if not supabase_store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        success = supabase_store.delete_project(project_id=project_id)
        if not success:
            return JSONResponse(status_code=500, content={"error": "Failed to delete project"})
        return JSONResponse(content={"status": "deleted", "project_id": project_id})
    except Exception as e:
        logger.error("Failed to delete project %s: %s", project_id, e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.delete("/api/projects/{project_id}/tasks/{task_id}")
async def delete_task(project_id: str, task_id: str) -> JSONResponse:
    """Delete a single task from a project.

    Returns 200 on success, 503 if Supabase is unavailable.
    """
    if not supabase_store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        success = supabase_store.delete_task(project_id=project_id, task_id=task_id)
        if not success:
            return JSONResponse(status_code=500, content={"error": "Failed to delete task"})
        return JSONResponse(content={"status": "deleted", "task_id": task_id})
    except Exception as e:
        logger.error("Failed to delete task %s: %s", task_id, e)
        return JSONResponse(status_code=500, content={"error": str(e)})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# OTHER ENDPOINTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@app.get("/api/compliance/history")
async def get_compliance_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Fetch paginated compliance check history."""
    user_id = "demo_user"

    try:
        store = SupabaseComplianceStore()
        history = store.get_history(user_id=user_id, page=page, page_size=page_size)
        return JSONResponse(content={
            "records": [record.model_dump(mode="json") for record in history.records],
            "total": history.total,
            "page": history.page,
            "page_size": history.page_size,
        })
    except Exception as e:
        logger.error("Failed to fetch compliance history: %s", e)
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to fetch compliance history", "detail": str(e)},
        )


@app.get("/api/compliance/{check_id}")
async def get_results(check_id: str):
    """Get results for a previous compliance check."""
    result_path = RESULTS_DIR / f"{check_id}.json"
    if not result_path.exists():
        return JSONResponse(status_code=404, content={"error": "Not found"})
    with open(result_path, "r", encoding="utf-8") as f:
        return JSONResponse(content=json.load(f))


@app.get("/api/media/{check_id}/{asset_type}")
async def get_media_url(check_id: str, asset_type: str):
    """Generate a presigned URL for a compliance check media asset.

    Returns a redirect to the presigned S3 URL so it can be used directly in <img src>.
    """
    from fastapi.responses import RedirectResponse

    if asset_type not in ("original", "remixed", "segmented"):
        return JSONResponse(status_code=400, content={"error": "asset_type must be 'original', 'remixed', or 'segmented'"})

    try:
        store = SupabaseComplianceStore()
        response = (
            store.client.table("compliance_checks")
            .select("s3_upload_key, s3_segmented_key, s3_remix_key")
            .eq("check_id", check_id)
            .execute()
        )

        if not response.data:
            return JSONResponse(status_code=404, content={"error": f"Check record not found: {check_id}"})

        record = response.data[0]
        if asset_type == "original":
            s3_key = record.get("s3_upload_key")
        elif asset_type == "segmented":
            s3_key = record.get("s3_segmented_key")
        else:
            s3_key = record.get("s3_remix_key")

        if not s3_key:
            return JSONResponse(status_code=404, content={"error": f"No {asset_type} media found for {check_id}"})

        client = S3MediaClient()
        url = client.generate_presigned_url(s3_key, expiry_seconds=3600)
        return RedirectResponse(url=url)

    except Exception as e:
        logger.error("Failed to generate media URL for %s/%s: %s", check_id, asset_type, e)
        return JSONResponse(status_code=500, content={"error": "Failed to generate media URL", "detail": str(e)})


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "services": {
        "s3": s3_client is not None,
        "supabase": supabase_store is not None,
    }}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _persist_check_record(
    check_id: str,
    username: str,
    project_id: str,
    media_type: str,
    market: str,
    ethnicity: str,
    age_group: str,
    response: dict,
    s3_upload_key: str | None,
    s3_segmented_key: str | None = None,
    violations: list[dict] | None = None,
) -> None:
    """Persist compliance check result to Supabase with local fallback."""
    now = datetime.now(timezone.utc)
    violations = violations or []

    record = CheckRecord(
        check_id=check_id,
        user_id=username,
        project_id=uuid.UUID(project_id) if project_id else uuid.uuid4(),
        media_type=media_type,
        market=market,
        ethnicity=ethnicity,
        age_group=age_group,
        risk_percentage=response.get("risk_percentage"),
        risk_band=response.get("risk_band"),
        confidence=response.get("confidence") if isinstance(response.get("confidence"), (int, float)) else None,
        status="checked",
        result_json=response,
        s3_upload_key=s3_upload_key,
        s3_segmented_key=s3_segmented_key,
        s3_remix_key=None,
        created_at=now,
        updated_at=now,
    )

    if supabase_store:
        try:
            success = supabase_store.insert_check(record)
            if success:
                logger.info("[Persist] CheckRecord inserted: %s", check_id)
                # Wire compliance task creation (Requirement 10.3, 4.3, 11.2)
                try:
                    supabase_store.create_task(
                        project_id=project_id,
                        task_type="compliance",
                        status="checked",
                        summary=f"Compliance check — {media_type} ({market})",
                        reference_id=check_id,
                    )
                    logger.info("[Persist] Compliance task created for check: %s", check_id)
                except Exception as task_err:
                    # Task creation failure must never break compliance persistence
                    logger.warning("[Persist] Failed to create compliance task for %s: %s", check_id, task_err)
            else:
                raise RuntimeError("insert_check returned False")
        except Exception as e:
            logger.warning("[Persist] Supabase failed for %s — queuing: %s", check_id, e)
            fallback_queue.queue_supabase_write(check_id, record.model_dump(mode="json"))
    else:
        fallback_queue.queue_supabase_write(check_id, record.model_dump(mode="json"))

    # Insert violations
    if violations and supabase_store:
        try:
            violation_rows = [
                {
                    "violation_index": v.get("index", i),
                    "type": v.get("type", "unknown"),
                    "severity": v.get("severity", "warning"),
                    "description": v.get("description", ""),
                    "start_time": v.get("start_time", v.get("start")),
                    "end_time": v.get("end_time", v.get("end")),
                }
                for i, v in enumerate(violations)
            ]
            supabase_store.insert_violations(check_id, violation_rows)
        except Exception as e:
            logger.warning("[Persist] Violations insert failed for %s: %s", check_id, e)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STATIC MOUNTS (must be LAST)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
