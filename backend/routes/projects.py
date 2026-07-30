"""
routes/projects.py
──────────────────
Project and Task CRUD endpoints.

All endpoints require Supabase availability — returns 503 if not.
"""

import logging
from copy import deepcopy

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from shared.supabase_client import SupabaseComplianceStore
from shared.models import CreateTaskRequest, UpdatePipelineRequest, UpdateProjectRequest
from shared.auth import Principal, get_current_principal
from shared.authorization import require_project_access
from shared.s3_client import generate_presigned_url, normalize_s3_key

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


_COMPLIANCE_MEDIA_FIELDS = ("s3_upload_key", "s3_segmented_key", "s3_remix_key")
_COMPLIANCE_PREVIEW_SECONDS = 300


def _replace_compliance_media_with_preview_urls(task: dict) -> dict:
    """Expose fresh temporary previews, never durable private S3 keys.

    The caller has already passed project authorization.  Historical task
    pipeline data may contain an expired signed URL; normalising it back to an
    object key lets this read response recover a fresh preview without storing
    that new URL anywhere.
    """
    if task.get("type") != "compliance":
        return task

    compliance = task.get("compliance")
    if not isinstance(compliance, dict):
        return task
    pipeline_state = task.get("pipeline_state")
    saved_result = pipeline_state.get("compliance_result") if isinstance(pipeline_state, dict) else None
    result_json = compliance.get("result_json")

    for field in _COMPLIANCE_MEDIA_FIELDS:
        raw_value = compliance.get(field)
        if not raw_value and isinstance(saved_result, dict):
            raw_value = saved_result.get(field)
        key = normalize_s3_key(str(raw_value or ""))
        if not key:
            compliance[field] = None
            task[field] = None
            if isinstance(saved_result, dict):
                saved_result.pop(field, None)
            if isinstance(result_json, dict):
                result_json.pop(field, None)
            continue
        try:
            preview_url = generate_presigned_url(key, _COMPLIANCE_PREVIEW_SECONDS)
        except Exception:
            logger.exception("Could not prepare compliance preview task=%s", task.get("id"))
            preview_url = None
        compliance[field] = preview_url
        task[field] = preview_url
        if isinstance(saved_result, dict):
            saved_result[field] = preview_url
        if isinstance(result_json, dict):
            result_json[field] = preview_url
    return task


def _remove_compliance_presentation_urls(pipeline_state: dict) -> dict:
    """Do not persist expiring signed URLs in durable pipeline state."""
    clean_state = deepcopy(pipeline_state)
    for result_key in ("compliance_result", "compliance_remix"):
        result = clean_state.get(result_key)
        if not isinstance(result, dict):
            continue
        for field in (*_COMPLIANCE_MEDIA_FIELDS, "s3_remix_url"):
            result.pop(field, None)
        version = result.get("version")
        if isinstance(version, dict):
            version.pop("asset_url", None)
    return clean_state


# -- Request Models ------------------------------------------------------------


class CreateProjectRequest(BaseModel):
    """Request body for POST /api/projects."""

    name: str
    # Accepted for older clients only; the verified Cognito token owns identity.
    username: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Project name cannot be empty")
        if len(stripped) > 255:
            raise ValueError("Project name cannot exceed 255 characters")
        return stripped


class ShareProjectRequest(BaseModel):
    """Request body for POST /api/projects/{project_id}/share."""
    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        stripped = v.strip().lower()
        if not stripped:
            raise ValueError("Email cannot be empty")
        return stripped


# -- Project Endpoints ---------------------------------------------------------


@router.post("/projects")
async def create_project(body: CreateProjectRequest, principal: Principal = Depends(get_current_principal)) -> JSONResponse:
    """Create a new project."""
    store = _get_store()
    if not store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        result = store.create_project(
            user_id=principal.email,
            name=body.name,
        )
        return JSONResponse(status_code=201, content=result)
    except Exception:
        logger.exception("Failed to create project")
        return JSONResponse(status_code=500, content={"error": "Unable to create project"})


@router.get("/projects")
async def list_projects(principal: Principal = Depends(get_current_principal)) -> JSONResponse:
    """List all projects for a user."""
    store = _get_store()
    if not store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        projects = store.get_projects(user_id=principal.email)
        return JSONResponse(content=projects)
    except Exception:
        logger.exception("Failed to list projects for verified user")
        return JSONResponse(status_code=500, content={"error": "Unable to load projects"})


@router.patch("/projects/{project_id}")
async def update_project(project_id: str, body: UpdateProjectRequest, principal: Principal = Depends(get_current_principal)) -> JSONResponse:
    """Update project name."""
    store = _get_store()
    if not store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        require_project_access(store, project_id, principal, write=True)
        result = store.update_project_name(
            project_id=project_id,
            name=body.name,
            description=body.description,
        )
        return JSONResponse(content=result)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to update project %s", project_id)
        return JSONResponse(status_code=500, content={"error": "Unable to update project"})


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str, principal: Principal = Depends(get_current_principal)) -> JSONResponse:
    """Delete a project and all associated data (cascade)."""
    store = _get_store()
    if not store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        access = require_project_access(store, project_id, principal, write=True)
        if not access.is_owner:
            raise HTTPException(status_code=403, detail="Only the project owner can delete it")
        success = store.delete_project(project_id=project_id)
        if not success:
            return JSONResponse(status_code=500, content={"error": "Failed to delete project"})
        return JSONResponse(content={"status": "deleted", "project_id": project_id})
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to delete project %s", project_id)
        return JSONResponse(status_code=500, content={"error": "Unable to delete project"})


@router.post("/projects/{project_id}/share")
async def share_project(project_id: str, body: ShareProjectRequest, principal: Principal = Depends(get_current_principal)) -> JSONResponse:
    """Share a project with another user by email."""
    store = _get_store()
    if not store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        access = require_project_access(store, project_id, principal, write=True)
        if not access.is_owner:
            raise HTTPException(status_code=403, detail="Only the project owner can invite members")

        # Insert into project_members
        data = {"project_id": project_id, "email": body.email}
        # Attempt to insert, ignore if already exists (PostgREST handles unique constraints if setup, or we can just try-catch)
        try:
            store.client.table("project_members").insert(data).execute()
        except Exception as e:
            # Check if it's a unique constraint violation (code 23505)
            err_msg = str(e)
            if "duplicate key value" in err_msg or "23505" in err_msg or "already exists" in err_msg:
                pass  # Already shared, treat as success
            else:
                raise e

        return JSONResponse(content={"status": "shared", "project_id": project_id, "email": body.email})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to share project %s with %s: %s", project_id, body.email, e)
        return JSONResponse(status_code=500, content={"error": "Failed to share project"})


@router.get("/projects/{project_id}/members")
async def list_project_members(project_id: str, principal: Principal = Depends(get_current_principal)) -> JSONResponse:
    """List invited project members. Only the owner may manage membership."""
    store = _get_store()
    if not store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})
    access = require_project_access(store, project_id, principal)
    if not access.is_owner:
        raise HTTPException(status_code=403, detail="Only the project owner can manage members")
    try:
        response = store.client.table("project_members").select("email, role").eq("project_id", project_id).order("email").execute()
        return JSONResponse(content={"members": response.data or []})
    except Exception:
        logger.exception("Failed to list project members project=%s", project_id)
        return JSONResponse(status_code=503, content={"error": "Project members are temporarily unavailable"})


@router.delete("/projects/{project_id}/members/{member_email}")
async def remove_project_member(project_id: str, member_email: str, principal: Principal = Depends(get_current_principal)) -> JSONResponse:
    """Revoke a project invitation. The owner itself is never a member record here."""
    store = _get_store()
    if not store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})
    access = require_project_access(store, project_id, principal, write=True)
    if not access.is_owner:
        raise HTTPException(status_code=403, detail="Only the project owner can remove members")
    email = member_email.strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Member email is required")
    try:
        response = store.client.table("project_members").delete().eq("project_id", project_id).eq("email", email).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Project member not found")
        return JSONResponse(content={"status": "removed", "project_id": project_id, "email": email})
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to remove project member project=%s", project_id)
        return JSONResponse(status_code=503, content={"error": "Project member could not be removed"})


# -- Task Endpoints ------------------------------------------------------------


@router.get("/projects/{project_id}/tasks")
async def list_tasks(project_id: str, principal: Principal = Depends(get_current_principal)) -> JSONResponse:
    """List all tasks for a project."""
    store = _get_store()
    if not store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        require_project_access(store, project_id, principal)
        tasks = store.list_tasks(project_id=project_id)
        return JSONResponse(content=tasks)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to list tasks for project %s", project_id)
        return JSONResponse(status_code=500, content={"error": "Unable to load tasks"})


@router.get("/projects/{project_id}/tasks/{task_id}")
async def get_task_detail(project_id: str, task_id: str, principal: Principal = Depends(get_current_principal)) -> JSONResponse:
    """Get full task detail with type-specific data."""
    store = _get_store()
    if not store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        require_project_access(store, project_id, principal)
        task = store.get_task_detail(project_id=project_id, task_id=task_id)
        if task is None:
            return JSONResponse(status_code=404, content={"error": "Task not found"})
        return JSONResponse(content=_replace_compliance_media_with_preview_urls(task))
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to get task %s", task_id)
        return JSONResponse(status_code=500, content={"error": "Unable to load task"})


@router.post("/projects/{project_id}/tasks")
async def create_task(project_id: str, body: CreateTaskRequest, principal: Principal = Depends(get_current_principal)) -> JSONResponse:
    """Create a new task. Copies generation_settings from the latest task in the project."""
    store = _get_store()
    if not store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        require_project_access(store, project_id, principal, write=True)
        # Copy generation_settings from the most recent task in this project (project-level settings)
        inherited_settings = {}
        try:
            from shared.clients import supabase as sb
            latest = (
                sb.table("tasks")
                .select("pipeline_state")
                .eq("project_id", project_id)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if latest.data:
                ps = latest.data[0].get("pipeline_state") or {}
                if isinstance(ps, dict) and "generation_settings" in ps:
                    inherited_settings = ps["generation_settings"]
        except Exception:
            pass  # Non-fatal — new task just won't have pre-filled settings

        initial_pipeline = {"nodes": [], "edges": [], "viewport": {"panX": 0, "panY": 0, "zoom": 1}}
        if inherited_settings:
            initial_pipeline["generation_settings"] = inherited_settings

        task = store.create_task(
            project_id=project_id,
            task_type=body.type,
            status="created",
            summary=f"New {body.type} task",
            pipeline_state=initial_pipeline if body.type == "generation" else None,
        )
        return JSONResponse(status_code=201, content=task)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to create task for project %s", project_id)
        return JSONResponse(status_code=500, content={"error": "Unable to create task"})


@router.put("/projects/{project_id}/tasks/{task_id}/pipeline")
async def update_task_pipeline(project_id: str, task_id: str, body: UpdatePipelineRequest, principal: Principal = Depends(get_current_principal)) -> JSONResponse:
    """Persist pipeline graph state and status."""
    store = _get_store()
    if not store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        require_project_access(store, project_id, principal, write=True)
        success = store.update_task_pipeline(
            project_id=project_id,
            task_id=task_id,
            status=body.status,
            pipeline_state=_remove_compliance_presentation_urls(body.pipeline_state),
        )
        if not success:
            return JSONResponse(status_code=404, content={"error": "Task not found"})
        return JSONResponse(content={"status": "updated"})
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to update pipeline for task %s", task_id)
        return JSONResponse(status_code=500, content={"error": "Unable to update task pipeline"})


@router.delete("/projects/{project_id}/tasks/{task_id}")
async def delete_task(project_id: str, task_id: str, principal: Principal = Depends(get_current_principal)) -> JSONResponse:
    """Delete a single task."""
    store = _get_store()
    if not store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        require_project_access(store, project_id, principal, write=True)
        success = store.delete_task(project_id=project_id, task_id=task_id)
        if not success:
            return JSONResponse(status_code=500, content={"error": "Failed to delete task"})
        return JSONResponse(content={"status": "deleted", "task_id": task_id})
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to delete task %s", task_id)
        return JSONResponse(status_code=500, content={"error": "Unable to delete task"})
