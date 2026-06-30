"""
supabase_client.py
──────────────────
Supabase CRUD functions organized by table + legacy class wrapper.
Uses the shared supabase client from clients.py.

Each table has: create, list/get, update, delete.
"""

import logging
from datetime import datetime, timezone

from agent.clients import supabase
from agent.models import CheckRecord, HistoryResponse

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

    def update_check_status(self, check_id, status, **fields):
        return update_check(check_id, status, **fields)

    def get_history(self, user_id, page=1, page_size=20):
        return list_checks(user_id, page, page_size)

    def insert_violations(self, check_id, violations):
        return create_violations(check_id, violations)

    def create_project(self, user_id, name, task_type=None):
        return create_project(user_id, name)

    def get_projects(self, user_id):
        return list_projects(user_id)

    def get_project_checks(self, project_id):
        return list_checks_by_project(project_id)

    def create_task(self, project_id, task_type, status, summary, reference_id=None, pipeline_state=None):
        return create_task(project_id, task_type, status, summary, reference_id, pipeline_state)

    def list_tasks(self, project_id):
        return list_tasks(project_id)

    def get_task_detail(self, project_id, task_id):
        return get_task(project_id, task_id)

    def update_task_pipeline(self, project_id, task_id, status, pipeline_state):
        return update_task(project_id, task_id, status, pipeline_state)

    def update_project_name(self, project_id, name):
        return update_project(project_id, name)

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


def update_project(project_id: str, name: str) -> dict:
    """Update a project's name. Returns the updated row dict."""
    update_data = {
        "name": name.strip(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
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
    """Delete a project (cascades to tasks, checks, violations)."""
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
        data["project_id"] = str(data["project_id"])
        data["created_at"] = data["created_at"].isoformat()
        data["updated_at"] = data["updated_at"].isoformat()
        supabase.table("compliance_checks").insert(data).execute()
        logger.info("Inserted check: %s", record.check_id)
        return True
    except Exception as e:
        logger.error("Failed to insert check %s: %s", record.check_id, e)
        return False


def list_checks(user_id: str, page: int = 1, page_size: int = 20) -> HistoryResponse:
    """Paginated compliance check history for a user."""
    page = max(1, page)
    page_size = max(1, min(100, page_size))
    offset = (page - 1) * page_size

    try:
        count_response = (
            supabase.table("compliance_checks")
            .select("*", count="exact")
            .eq("user_email", user_id)
            .execute()
        )
        total = count_response.count if count_response.count is not None else 0

        response = (
            supabase.table("compliance_checks")
            .select("*")
            .eq("user_email", user_id)
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
        .select("check_id, media_type, market, risk_percentage, status, created_at")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )
    return response.data or []


def update_check(check_id: str, status: str, **fields) -> bool:
    """Update a compliance check's status and optional fields."""
    try:
        update_data = {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}
        update_data.update(fields)
        for key, value in update_data.items():
            if hasattr(value, "hex"):
                update_data[key] = str(value)

        supabase.table("compliance_checks").update(update_data).eq("check_id", check_id).execute()
        logger.info("Updated check %s -> status: %s", check_id, status)
        return True
    except Exception as e:
        logger.error("Failed to update check %s: %s", check_id, e)
        return False


# ═════════════════════════════════════════════════════════════════════════════
# VIOLATIONS
# ═════════════════════════════════════════════════════════════════════════════


def create_violations(check_id: str, violations: list[dict]) -> bool:
    """Bulk insert violations for a compliance check.

    Each dict should have: violation_index, type, severity.
    Optional: description, start_time, end_time.
    """
    if not violations:
        return True

    try:
        rows = [
            {
                "check_id": check_id,
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
        logger.info("Inserted %d violations for check %s", len(rows), check_id)
        return True
    except Exception as e:
        logger.error("Failed to insert violations for check %s: %s", check_id, e)
        return False


# ═════════════════════════════════════════════════════════════════════════════
# TASKS
# ═════════════════════════════════════════════════════════════════════════════


def create_task(
    project_id: str,
    task_type: str,
    status: str,
    summary: str,
    reference_id: str | None = None,
    pipeline_state: dict | None = None,
) -> dict:
    """Create a task row. Returns the inserted row dict (id as string)."""
    data: dict = {
        "project_id": project_id,
        "type": task_type,
        "status": status,
        "summary": summary,
    }
    if reference_id is not None:
        data["reference_id"] = reference_id
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

        # Collect reference_ids for compliance tasks to batch-fetch metadata
        ref_ids = [r["reference_id"] for r in rows if r.get("type") == "compliance" and r.get("reference_id")]

        compliance_meta: dict[str, dict] = {}
        if ref_ids:
            try:
                meta_resp = (
                    supabase.table("compliance_checks")
                    .select("check_id, market, ethnicity, age_group, platform, media_type")
                    .in_("check_id", ref_ids)
                    .execute()
                )
                for m in (meta_resp.data or []):
                    compliance_meta[m["check_id"]] = m
            except Exception as e:
                logger.warning("[list_tasks] Failed to fetch compliance metadata: %s", e)

        for row in rows:
            row["id"] = str(row["id"])
            # Attach compliance metadata if available
            ref = row.get("reference_id")
            if ref and ref in compliance_meta:
                meta = compliance_meta[ref]
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

        if task["type"] == "compliance" and task.get("reference_id"):
            task["compliance"] = _get_compliance_enrichment(task["reference_id"])
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
    """Delete a single task."""
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
        supabase.table("compliance_checks").select("check_id").limit(1).execute()
        return True
    except Exception:
        return False


# ─── Private helpers ──────────────────────────────────────────────────────────


def _get_compliance_enrichment(reference_id: str) -> dict:
    """Fetch compliance_checks + violations for a task's reference_id."""
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
                    "s3_upload_key, s3_segmented_key, s3_remix_key, result_json, check_id, media_type")
            .eq("check_id", reference_id)
            .execute()
        )
        check_rows = check_resp.data or []
    except Exception as e:
        logger.error("compliance_checks lookup failed for %s: %s", reference_id, e)
        return empty

    if not check_rows:
        return empty

    check = check_rows[0]

    try:
        viol_resp = (
            supabase.table("violations")
            .select("*")
            .eq("check_id", reference_id)
            .execute()
        )
        violations = viol_resp.data or []
    except Exception as e:
        logger.error("violations lookup failed for %s: %s", reference_id, e)
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
