"""
supabase_client.py
──────────────────
Supabase CRUD functions organized by table + legacy class wrapper.
Uses the shared supabase client from clients.py.

Each table has: create, list/get, update, delete.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from shared.clients import supabase
from shared.models import CheckRecord, HistoryResponse

logger = logging.getLogger(__name__)


class SupabaseComplianceStore:
    """Legacy class wrapper — prefer using the module functions directly."""

    def __init__(self, url=None, key=None):
        pass

    @property
    def client(self):
        """Expose the shared Supabase client for direct queries."""
        return supabase

    def insert_check(self, record):
        return create_check(record)

    def update_check_status(self, task_id, status, **fields):
        return update_check(task_id, status, **fields)

    def get_history(self, user_id, page=1, page_size=20):
        return list_checks(user_id, page, page_size)

    def insert_violations(self, task_id, violations):
        return create_violations(task_id, violations)

    def create_project(self, user_id, name, task_type=None):
        return create_project(user_id, name)

    def get_projects(self, user_id):
        return list_projects(user_id)

    def get_project_checks(self, project_id):
        return list_checks_by_project(project_id)

    def create_task(self, project_id, task_type, status, summary, pipeline_state=None):
        return create_task(project_id, task_type, status, summary, pipeline_state)

    def list_tasks(self, project_id):
        return list_tasks(project_id)

    def get_task_detail(self, project_id, task_id):
        return get_task(project_id, task_id)

    def update_task_pipeline(self, project_id, task_id, status, pipeline_state):
        return update_task(project_id, task_id, status, pipeline_state)

    def update_project_name(self, project_id, name=None, description=None):
        return update_project(project_id, name=name, description=description)

    def delete_project(self, project_id):
        return delete_project(project_id)

    def delete_task(self, project_id, task_id):
        return delete_task(project_id, task_id)

    def health_check(self):
        return health_check()


# ═════════════════════════════════════════════════════════════════════════════
# PROJECTS
# ═════════════════════════════════════════════════════════════════════════════


def create_project(user_id: str, name: str) -> dict:
    """Create a new project.

    Args:
        user_id: Owner's email address.
        name: Project name (max 255 chars).

    Returns:
        The inserted row dict (id as string).
    """
    data = {"owner_email": user_id, "name": name}
    response = supabase.table("projects").insert(data).execute()
    if response.data:
        row = response.data[0]
        row["id"] = str(row["id"])
        return row
    raise RuntimeError("Supabase insert returned no data")


def list_projects(user_id: str) -> list[dict]:
    """List all projects for a user (newest first)."""
    response = (
        supabase.table("projects")
        .select("*")
        .eq("owner_email", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    rows = response.data or []
    for row in rows:
        row["id"] = str(row["id"])
    return rows


def update_project(project_id: str, name: Optional[str] = None, description: Optional[str] = None) -> dict:
    """Update a project's name and/or description. Returns the updated row dict."""
    update_data = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if name is not None:
        update_data["name"] = name.strip()
    if description is not None:
        update_data["description"] = description.strip()
    response = (
        supabase.table("projects")
        .update(update_data)
        .eq("id", project_id)
        .execute()
    )
    if response.data:
        row = response.data[0]
        row["id"] = str(row["id"])
        return row
    raise RuntimeError("Supabase update returned no data")


def delete_project(project_id: str) -> bool:
    """Delete a project and its S3 media (cascades to tasks, checks, violations).

    Order matters: the project's owner is resolved and all project-scoped S3
    media is purged *before* the DB row is deleted, because the compliance S3
    keys are owner-scoped (``uploads/{owner_email}/{project_id}/`` etc.) and the
    owner is only readable while the row still exists. S3 cleanup is best-effort
    — a purge failure is logged but does not block the DB deletion, so a project
    is never left undeletable due to a storage hiccup.

    Args:
        project_id: The project to delete.

    Returns:
        ``True`` when the DB deletion succeeds, ``False`` otherwise.
    """
    # 1. Resolve the owner while the row still exists (needed for owner-scoped keys).
    owner_email: str | None = None
    try:
        resp = (
            supabase.table("projects")
            .select("owner_email")
            .eq("id", project_id)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        if rows:
            owner_email = rows[0].get("owner_email")
    except Exception as e:
        logger.warning("Could not resolve owner for project %s (S3 cleanup best-effort): %s", project_id, e)

    # 2. Purge S3 media (best-effort; never blocks the DB delete).
    try:
        from shared.s3_client import delete_project_media

        delete_project_media(project_id, owner_email)
    except Exception as e:
        logger.error("S3 media cleanup failed for project %s: %s", project_id, e)

    # 3. Delete the DB row (cascades to tasks, checks, violations).
    try:
        supabase.table("projects").delete().eq("id", project_id).execute()
        logger.info("Deleted project %s", project_id)
        return True
    except Exception as e:
        logger.error("Failed to delete project %s: %s", project_id, e)
        return False


# ═════════════════════════════════════════════════════════════════════════════
# COMPLIANCE CHECKS
# ═════════════════════════════════════════════════════════════════════════════


def create_check(record: CheckRecord) -> bool:
    """Insert a compliance check record. Returns True on success."""
    try:
        data = record.model_dump()
        data["task_id"] = str(data["task_id"])
        data["project_id"] = str(data["project_id"])
        data["created_at"] = data["created_at"].isoformat()
        data["updated_at"] = data["updated_at"].isoformat()
        supabase.table("compliance_checks").insert(data).execute()
        logger.info("Inserted check for task_id: %s", record.task_id)
        return True
    except Exception as e:
        logger.error("Failed to insert check for task_id %s: %s", record.task_id, e)
        return False


def list_checks(user_id: str, page: int = 1, page_size: int = 20) -> HistoryResponse:
    """Paginated compliance check history for a user (via project ownership)."""
    page = max(1, page)
    page_size = max(1, min(100, page_size))
    offset = (page - 1) * page_size

    try:
        # Get user's project IDs first
        proj_resp = (
            supabase.table("projects")
            .select("id")
            .eq("owner_email", user_id)
            .execute()
        )
        project_ids = [str(r["id"]) for r in (proj_resp.data or [])]

        if not project_ids:
            return HistoryResponse(records=[], total=0, page=page, page_size=page_size)

        count_response = (
            supabase.table("compliance_checks")
            .select("*", count="exact")
            .in_("project_id", project_ids)
            .execute()
        )
        total = count_response.count if count_response.count is not None else 0

        response = (
            supabase.table("compliance_checks")
            .select("*")
            .in_("project_id", project_ids)
            .order("created_at", desc=True)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        records = [CheckRecord(**row) for row in (response.data or [])]
        return HistoryResponse(records=records, total=total, page=page, page_size=page_size)
    except Exception as e:
        logger.error("Failed to list checks for user %s: %s", user_id, e)
        return HistoryResponse(records=[], total=0, page=page, page_size=page_size)


def list_checks_by_project(project_id: str) -> list[dict]:
    """List compliance checks for a project (newest first, max 50)."""
    response = (
        supabase.table("compliance_checks")
        .select("task_id, media_type, market, risk_percentage, status, created_at")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )
    return response.data or []


def update_check(task_id: str, status: str, **fields) -> bool:
    """Update a compliance check's status and optional fields."""
    try:
        update_data = {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}
        update_data.update(fields)
        for key, value in update_data.items():
            if hasattr(value, "hex"):
                update_data[key] = str(value)

        supabase.table("compliance_checks").update(update_data).eq("task_id", task_id).execute()
        logger.info("Updated check %s -> status: %s", task_id, status)
        return True
    except Exception as e:
        logger.error("Failed to update check %s: %s", task_id, e)
        return False


# ═════════════════════════════════════════════════════════════════════════════
# VIOLATIONS
# ═════════════════════════════════════════════════════════════════════════════


def create_violations(task_id: str, violations: list[dict]) -> bool:
    """Bulk insert violations for a compliance check.

    Each dict should have: violation_index, type, severity.
    Optional: description, start_time, end_time.
    """
    if not violations:
        return True

    try:
        rows = [
            {
                "task_id": task_id,
                "violation_index": v.get("violation_index"),
                "type": v.get("type"),
                "severity": v.get("severity"),
                "description": v.get("description"),
                "start_time": v.get("start_time"),
                "end_time": v.get("end_time"),
            }
            for v in violations
        ]
        supabase.table("violations").insert(rows).execute()
        logger.info("Inserted %d violations for task %s", len(rows), task_id)
        return True
    except Exception as e:
        logger.error("Failed to insert violations for task %s: %s", task_id, e)
        return False


# ═════════════════════════════════════════════════════════════════════════════
# TASKS
# ═════════════════════════════════════════════════════════════════════════════


def create_task(
    project_id: str,
    task_type: str,
    status: str,
    summary: str,
    pipeline_state: dict | None = None,
) -> dict:
    """Create a task row. Returns the inserted row dict (id as string)."""
    data: dict = {
        "project_id": project_id,
        "type": task_type,
        "status": status,
        "summary": summary,
    }
    if pipeline_state is not None:
        data["pipeline_state"] = pipeline_state

    response = supabase.table("tasks").insert(data).execute()
    if response.data:
        row = response.data[0]
        row["id"] = str(row["id"])
        logger.info("Created task %s for project %s", row["id"], project_id)
        return row
    raise RuntimeError("Supabase insert returned no data")


def list_tasks(project_id: str) -> list[dict]:
    """List all tasks for a project (newest first), enriched with compliance metadata."""
    try:
        response = (
            supabase.table("tasks")
            .select("*")
            .eq("project_id", project_id)
            .order("created_at", desc=True)
            .execute()
        )
        rows = response.data or []

        # Collect task IDs for compliance tasks to batch-fetch metadata
        compliance_task_ids = [str(r["id"]) for r in rows if r.get("type") == "compliance"]

        compliance_meta: dict[str, dict] = {}
        if compliance_task_ids:
            try:
                meta_resp = (
                    supabase.table("compliance_checks")
                    .select("task_id, market, ethnicity, age_group, platform, media_type")
                    .in_("task_id", compliance_task_ids)
                    .execute()
                )
                for m in (meta_resp.data or []):
                    compliance_meta[str(m["task_id"])] = m
            except Exception as e:
                logger.warning("[list_tasks] Failed to fetch compliance metadata: %s", e)

        for row in rows:
            row["id"] = str(row["id"])
            # Attach compliance metadata if available
            if row["id"] in compliance_meta:
                meta = compliance_meta[row["id"]]
                row["market"] = meta.get("market")
                row["ethnicity"] = meta.get("ethnicity")
                row["age_group"] = meta.get("age_group")
                row["platform"] = meta.get("platform")
                row["media_type"] = meta.get("media_type")

        return rows
    except Exception as e:
        logger.error("Failed to list tasks for project %s: %s", project_id, e)
        return []


def get_task(project_id: str, task_id: str) -> dict | None:
    """Get full task detail with compliance enrichment if applicable."""
    try:
        response = (
            supabase.table("tasks")
            .select("*")
            .eq("id", task_id)
            .eq("project_id", project_id)
            .execute()
        )
        rows = response.data or []
        if not rows:
            return None

        task = rows[0]
        task["id"] = str(task["id"])

        if task["type"] == "compliance":
            task["compliance"] = _get_compliance_enrichment(task_id)
            # Expose S3 URLs at top level for frontend convenience
            task["s3_upload_key"] = task["compliance"].get("s3_upload_key")
            task["s3_segmented_key"] = task["compliance"].get("s3_segmented_key")
            task["s3_remix_key"] = task["compliance"].get("s3_remix_key")
            logger.info(
                f"[get_task] task={task_id} | s3_upload_key={task['s3_upload_key']} | "
                f"s3_segmented_key={task['s3_segmented_key']} | s3_remix_key={task['s3_remix_key']}"
            )

        return task
    except Exception as e:
        logger.error("Failed to get task %s: %s", task_id, e)
        return None


def update_task(project_id: str, task_id: str, status: str, pipeline_state: dict) -> bool:
    """Update a task's status and pipeline_state."""
    try:
        update_data = {
            "status": status,
            "pipeline_state": pipeline_state,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        supabase.table("tasks").update(update_data).eq("id", task_id).eq("project_id", project_id).execute()
        logger.info("Updated task %s -> status: %s", task_id, status)
        return True
    except Exception as e:
        logger.error("Failed to update task %s: %s", task_id, e)
        return False


def delete_task(project_id: str, task_id: str) -> bool:
    """Delete a single task and its S3 media (generated ads + references).

    A task's generated media lives under the task-scoped prefix
    ``generated_ads/{project_id}/{task_id}/`` (generated ads and uploaded chat
    references), so that prefix is purged before the DB row is removed. S3
    cleanup is best-effort — a purge failure is logged but never blocks the DB
    deletion. Compliance uploads are also task-scoped and cascade-deleted via DB.

    Args:
        project_id: The owning project id.
        task_id: The task to delete.

    Returns:
        ``True`` when the DB deletion succeeds, ``False`` otherwise.
    """
    # 1. Purge task-scoped S3 media (best-effort; never blocks the DB delete).
    try:
        from shared.s3_client import delete_prefix

        delete_prefix(f"generated_ads/{project_id}/{task_id}/")
    except Exception as e:
        logger.error("S3 media cleanup failed for task %s: %s", task_id, e)

    # 2. Delete the DB row.
    try:
        supabase.table("tasks").delete().eq("id", task_id).eq("project_id", project_id).execute()
        logger.info("Deleted task %s from project %s", task_id, project_id)
        return True
    except Exception as e:
        logger.error("Failed to delete task %s: %s", task_id, e)
        return False


# ═════════════════════════════════════════════════════════════════════════════
# HEALTH
# ═════════════════════════════════════════════════════════════════════════════


def health_check() -> bool:
    """Quick connectivity check against Supabase."""
    try:
        supabase.table("compliance_checks").select("task_id").limit(1).execute()
        return True
    except Exception:
        return False


# ─── Private helpers ──────────────────────────────────────────────────────────


def _get_compliance_enrichment(task_id: str) -> dict:
    """Fetch compliance_checks + violations for a task_id."""
    empty = {
        "risk_percentage": None,
        "status": "pending",
        "market": None,
        "ethnicity": None,
        "age_group": None,
        "platform": None,
        "media_type": None,
        "violations": [],
        "s3_upload_key": None,
        "s3_segmented_key": None,
        "s3_remix_key": None,
        "result_json": None,
    }

    try:
        check_resp = (
            supabase.table("compliance_checks")
            .select("risk_percentage, status, market, ethnicity, age_group, platform, "
                    "s3_upload_key, s3_segmented_key, s3_remix_key, result_json, task_id, media_type")
            .eq("task_id", task_id)
            .execute()
        )
        check_rows = check_resp.data or []
    except Exception as e:
        logger.error("compliance_checks lookup failed for %s: %s", task_id, e)
        return empty

    if not check_rows:
        return empty

    check = check_rows[0]

    try:
        viol_resp = (
            supabase.table("violations")
            .select("*")
            .eq("task_id", task_id)
            .execute()
        )
        violations = viol_resp.data or []
    except Exception as e:
        logger.error("violations lookup failed for %s: %s", task_id, e)
        violations = []

    return {
        "risk_percentage": check.get("risk_percentage"),
        "status": check.get("status"),
        "market": check.get("market"),
        "ethnicity": check.get("ethnicity"),
        "age_group": check.get("age_group"),
        "platform": check.get("platform"),
        "media_type": check.get("media_type"),
        "violations": violations,
        "s3_upload_key": check.get("s3_upload_key"),
        "s3_segmented_key": check.get("s3_segmented_key"),
        "s3_remix_key": check.get("s3_remix_key"),
        "result_json": check.get("result_json"),
    }
