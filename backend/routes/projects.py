"""
routes/projects.py
──────────────────
Project and Task CRUD endpoints.

All endpoints require Supabase availability — returns 503 if not.
"""

import logging

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from agent.supabase_client import SupabaseComplianceStore
from agent.models import CreateTaskRequest, UpdatePipelineRequest, UpdateProjectRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["projects"])

# Shared Supabase store — set during app startup
_store: SupabaseComplianceStore | None = None


def init_store(store: SupabaseComplianceStore | None):
    """Called from app startup to inject the shared Supabase store."""
    global _store
    _store = store


def _get_store():
    if not _store:
        return None
    return _store


# ── Request Models ────────────────────────────────────────────────────────────


class CreateProjectRequest(BaseModel):
    """Request body for POST /api/projects."""

    name: str
    username: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Project name cannot be empty")
        if len(stripped) > 255:
            raise ValueError("Project name cannot exceed 255 characters")
        return stripped


# ── Project Endpoints ─────────────────────────────────────────────────────────


@router.post("/projects")
async def create_project(body: CreateProjectRequest) -> JSONResponse:
    """Create a new project."""
    store = _get_store()
    if not store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        result = store.create_project(
            user_id=body.username,
            name=body.name,
        )
        return JSONResponse(status_code=201, content=result)
    except Exception as e:
        logger.error("Failed to create project: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/projects")
async def list_projects(username: str = Query(...)) -> JSONResponse:
    """List all projects for a user."""
    store = _get_store()
    if not store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        projects = store.get_projects(user_id=username)
        return JSONResponse(content=projects)
    except Exception as e:
        logger.error("Failed to list projects: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.patch("/projects/{project_id}")
async def update_project(project_id: str, body: UpdateProjectRequest) -> JSONResponse:
    """Update project name."""
    store = _get_store()
    if not store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        result = store.update_project_name(project_id=project_id, name=body.name)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error("Failed to update project %s: %s", project_id, e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str) -> JSONResponse:
    """Delete a project and all associated data (cascade)."""
    store = _get_store()
    if not store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        success = store.delete_project(project_id=project_id)
        if not success:
            return JSONResponse(status_code=500, content={"error": "Failed to delete project"})
        return JSONResponse(content={"status": "deleted", "project_id": project_id})
    except Exception as e:
        logger.error("Failed to delete project %s: %s", project_id, e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/projects/{project_id}/checks")
async def get_project_checks(project_id: str) -> JSONResponse:
    """Fetch compliance checks for a project."""
    store = _get_store()
    if not store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        checks = store.get_project_checks(project_id=project_id)
        return JSONResponse(content=checks)
    except Exception as e:
        logger.error("Failed to get project checks: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


# ── Task Endpoints ────────────────────────────────────────────────────────────


@router.get("/projects/{project_id}/tasks")
async def list_tasks(project_id: str, username: str = "") -> JSONResponse:
    """List all tasks for a project."""
    store = _get_store()
    if not store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        if username:
            projects = store.get_projects(user_id=username)
            project_ids = {p["id"] for p in projects}
            if project_id not in project_ids:
                all_res = store.client.table("projects").select("id, owner_email").eq("id", project_id).execute()
                if not all_res.data:
                    return JSONResponse(status_code=404, content={"error": "Project not found"})
                return JSONResponse(status_code=403, content={"error": "Access denied"})

        tasks = store.list_tasks(project_id=project_id)
        return JSONResponse(content=tasks)
    except Exception as e:
        logger.error("Failed to list tasks: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/projects/{project_id}/tasks/{task_id}")
async def get_task_detail(project_id: str, task_id: str) -> JSONResponse:
    """Get full task detail with type-specific data."""
    store = _get_store()
    if not store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        task = store.get_task_detail(project_id=project_id, task_id=task_id)
        if task is None:
            return JSONResponse(status_code=404, content={"error": "Task not found"})
        return JSONResponse(content=task)
    except Exception as e:
        logger.error("Failed to get task %s: %s", task_id, e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/projects/{project_id}/tasks")
async def create_task(project_id: str, body: CreateTaskRequest) -> JSONResponse:
    """Create a new task."""
    store = _get_store()
    if not store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        task = store.create_task(
            project_id=project_id,
            task_type=body.type,
            status="created",
            summary=f"New {body.type} task",
            pipeline_state=(
                {"nodes": [], "edges": [], "viewport": {"panX": 0, "panY": 0, "zoom": 1}}
                if body.type == "generation" else None
            ),
        )
        return JSONResponse(status_code=201, content=task)
    except Exception as e:
        logger.error("Failed to create task: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.put("/projects/{project_id}/tasks/{task_id}/pipeline")
async def update_task_pipeline(project_id: str, task_id: str, body: UpdatePipelineRequest) -> JSONResponse:
    """Persist pipeline graph state and status."""
    store = _get_store()
    if not store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        success = store.update_task_pipeline(
            project_id=project_id,
            task_id=task_id,
            status=body.status,
            pipeline_state=body.pipeline_state,
        )
        if not success:
            return JSONResponse(status_code=404, content={"error": "Task not found"})
        return JSONResponse(content={"status": "updated"})
    except Exception as e:
        logger.error("Failed to update pipeline: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.delete("/projects/{project_id}/tasks/{task_id}")
async def delete_task(project_id: str, task_id: str) -> JSONResponse:
    """Delete a single task."""
    store = _get_store()
    if not store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        success = store.delete_task(project_id=project_id, task_id=task_id)
        if not success:
            return JSONResponse(status_code=500, content={"error": "Failed to delete task"})
        return JSONResponse(content={"status": "deleted", "task_id": task_id})
    except Exception as e:
        logger.error("Failed to delete task %s: %s", task_id, e)
        return JSONResponse(status_code=500, content={"error": str(e)})


# ── Health ────────────────────────────────────────────────────────────────────


@router.get("/health")
async def health() -> JSONResponse:
    """Health check."""
    store = _get_store()
    return JSONResponse(content={
        "status": "ok",
        "services": {
            "supabase": store is not None,
        },
    })
