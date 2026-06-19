"""
supabase_client.py
──────────────────
Supabase compliance store client for persisting compliance check records
and violations to the Supabase Postgres database.

Reads SUPABASE_URL and SUPABASE_KEY from environment variables.
Implements insert, update, paginated history retrieval, bulk violation insert,
and health check operations.

Requirements: 4.1, 4.2, 4.3, 8.1, 8.2, 8.3
"""

import logging
import os
from datetime import datetime, timezone

from supabase import create_client, Client

from agent.models import CheckRecord, HistoryResponse

logger = logging.getLogger(__name__)


class SupabaseComplianceStore:
    """Manages compliance record persistence in Supabase."""

    def __init__(self, url: str | None = None, key: str | None = None):
        """Initialize the Supabase client.

        Args:
            url: Supabase project URL. Falls back to SUPABASE_URL env var.
            key: Supabase anon/service key. Falls back to SUPABASE_KEY env var.
        """
        self.url = url or os.environ.get("SUPABASE_URL", "")
        self.key = key or os.environ.get("SUPABASE_KEY", "")

        if not self.url or not self.key:
            raise ValueError(
                "Supabase URL and key are required. "
                "Set SUPABASE_URL and SUPABASE_KEY environment variables."
            )

        self.client: Client = create_client(self.url, self.key)

    def insert_check(self, record: CheckRecord) -> bool:
        """Insert a new compliance check record into the compliance_checks table.

        Args:
            record: The CheckRecord to insert.

        Returns:
            True if the insert succeeded, False otherwise.
        """
        try:
            data = record.model_dump()
            # Convert UUID and datetime to string for JSON serialization
            data["project_id"] = str(data["project_id"])
            data["created_at"] = data["created_at"].isoformat()
            data["updated_at"] = data["updated_at"].isoformat()

            self.client.table("compliance_checks").insert(data).execute()
            logger.info("Inserted check record: %s", record.check_id)
            return True
        except Exception as e:
            logger.error("Failed to insert check record %s: %s", record.check_id, e)
            return False

    def update_check_status(self, check_id: str, status: str, **fields) -> bool:
        """Update check status and optional fields for a compliance check record.

        Args:
            check_id: The unique check identifier.
            status: New status value.
            **fields: Additional fields to update (e.g., s3_remix_key, result_json).

        Returns:
            True if the update succeeded, False otherwise.
        """
        try:
            update_data = {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}
            update_data.update(fields)

            # Convert any UUID values to strings
            for key, value in update_data.items():
                if hasattr(value, "hex"):  # UUID-like
                    update_data[key] = str(value)

            self.client.table("compliance_checks").update(update_data).eq(
                "check_id", check_id
            ).execute()
            logger.info("Updated check %s to status: %s", check_id, status)
            return True
        except Exception as e:
            logger.error("Failed to update check %s: %s", check_id, e)
            return False

    def get_history(
        self, user_id: str, page: int = 1, page_size: int = 20
    ) -> HistoryResponse:
        """Fetch paginated check history for a user.

        Args:
            user_id: The user to fetch history for.
            page: Page number (minimum 1).
            page_size: Number of records per page (clamped to 1–100).

        Returns:
            HistoryResponse with paginated records, total count, page, and page_size.
        """
        # Clamp pagination parameters
        page = max(1, page)
        page_size = max(1, min(100, page_size))
        offset = (page - 1) * page_size

        try:
            # Get total count for the user
            count_response = (
                self.client.table("compliance_checks")
                .select("*", count="exact")
                .eq("user_id", user_id)
                .execute()
            )
            total = count_response.count if count_response.count is not None else 0

            # Fetch paginated records ordered by created_at descending
            response = (
                self.client.table("compliance_checks")
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .range(offset, offset + page_size - 1)
                .execute()
            )

            records = [CheckRecord(**row) for row in (response.data or [])]

            return HistoryResponse(
                records=records,
                total=total,
                page=page,
                page_size=page_size,
            )
        except Exception as e:
            logger.error("Failed to fetch history for user %s: %s", user_id, e)
            return HistoryResponse(records=[], total=0, page=page, page_size=page_size)

    def insert_violations(self, check_id: str, violations: list[dict]) -> bool:
        """Bulk insert violations for a compliance check.

        Args:
            check_id: The check_id to associate violations with.
            violations: List of violation dicts. Each must contain at minimum:
                violation_index, type, severity. Optional: description, start_time, end_time.

        Returns:
            True if all violations were inserted, False otherwise.
        """
        if not violations:
            return True

        try:
            rows = []
            for v in violations:
                row = {
                    "check_id": check_id,
                    "violation_index": v.get("violation_index"),
                    "type": v.get("type"),
                    "severity": v.get("severity"),
                    "description": v.get("description"),
                    "start_time": v.get("start_time"),
                    "end_time": v.get("end_time"),
                }
                rows.append(row)

            self.client.table("violations").insert(rows).execute()
            logger.info(
                "Inserted %d violations for check %s", len(rows), check_id
            )
            return True
        except Exception as e:
            logger.error(
                "Failed to insert violations for check %s: %s", check_id, e
            )
            return False

    def create_project(self, user_id: str, name: str, media_type: str) -> dict:
        """Insert a new project into the projects table.

        Args:
            user_id: The user who owns the project.
            name: Project name (non-empty, ≤255 chars).
            media_type: One of text, image, audio, video.

        Returns:
            The inserted row as a dict including the generated UUID id as string.

        Raises:
            RuntimeError: If Supabase insert returned no data.
        """
        data = {
            "user_id": user_id,
            "name": name,
            "media_type": media_type,
        }
        response = self.client.table("projects").insert(data).execute()
        if response.data:
            row = response.data[0]
            # Convert UUID to string for JSON serialization
            row["id"] = str(row["id"])
            return row
        raise RuntimeError("Supabase insert returned no data")

    def get_projects(self, user_id: str) -> list[dict]:
        """Fetch all projects for a user, ordered by created_at descending.

        Args:
            user_id: The user whose projects to fetch.

        Returns:
            List of project dicts with UUID id converted to string.
        """
        response = (
            self.client.table("projects")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        rows = response.data or []
        for row in rows:
            row["id"] = str(row["id"])
        return rows

    def get_project_checks(self, project_id: str) -> list[dict]:
        """Fetch compliance checks for a project, ordered by created_at descending.

        Args:
            project_id: The project UUID to fetch checks for.

        Returns:
            List of check record dicts (up to 50) for the sidebar history.
        """
        response = (
            self.client.table("compliance_checks")
            .select("check_id, media_type, market, risk_band, status, created_at")
            .eq("project_id", project_id)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        return response.data or []

    # ─── Task CRUD ────────────────────────────────────────────────────────

    def create_task(
        self,
        project_id: str,
        task_type: str,
        status: str,
        summary: str,
        reference_id: str | None = None,
        pipeline_state: dict | None = None,
    ) -> dict:
        """Insert a unified task row into the tasks table.

        Args:
            project_id: The project UUID this task belongs to.
            task_type: Either 'compliance' or 'generation'.
            status: Initial status string.
            summary: Human-readable summary of the task.
            reference_id: Optional compliance_checks id (for compliance tasks).
            pipeline_state: Optional pipeline graph state (for generation tasks).

        Returns:
            The created row as a dict with id as string.

        Raises:
            RuntimeError: If Supabase insert returned no data.
        """
        try:
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

            response = self.client.table("tasks").insert(data).execute()
            if response.data:
                row = response.data[0]
                row["id"] = str(row["id"])
                logger.info(
                    "[SupabaseComplianceStore] Created task %s for project %s",
                    row["id"],
                    project_id,
                )
                return row
            raise RuntimeError("Supabase insert returned no data")
        except RuntimeError:
            raise
        except Exception as e:
            logger.error(
                "[SupabaseComplianceStore] Failed to create task for project %s: %s",
                project_id,
                e,
            )
            raise

    def list_tasks(self, project_id: str) -> list[dict]:
        """Return all tasks for a project ordered by created_at descending.

        Args:
            project_id: The project UUID to fetch tasks for.

        Returns:
            List of task dicts with UUID id converted to string.
            Returns an empty list on failure.
        """
        try:
            response = (
                self.client.table("tasks")
                .select("*")
                .eq("project_id", project_id)
                .order("created_at", desc=True)
                .execute()
            )
            rows = response.data or []
            for row in rows:
                row["id"] = str(row["id"])
            logger.info(
                "[SupabaseComplianceStore] Listed %d tasks for project %s",
                len(rows),
                project_id,
            )
            return rows
        except Exception as e:
            logger.error(
                "[SupabaseComplianceStore] Failed to list tasks for project %s: %s",
                project_id,
                e,
            )
            return []

    def get_task_detail(self, project_id: str, task_id: str) -> dict | None:
        """Return full task detail with type-specific enrichment.

        For compliance tasks, joins compliance_checks and violations via
        reference_id. Returns the task row enriched with a 'compliance' key
        containing: risk_percentage, status, market, violations list, s3_remix_key.

        For generation tasks, simply includes the pipeline_state field.

        Args:
            project_id: The project UUID the task belongs to.
            task_id: The task UUID to fetch.

        Returns:
            Enriched task dict, or None if not found.
        """
        try:
            response = (
                self.client.table("tasks")
                .select("*")
                .eq("id", task_id)
                .eq("project_id", project_id)
                .execute()
            )
            rows = response.data or []
            if not rows:
                logger.info(
                    "[SupabaseComplianceStore] Task %s not found in project %s",
                    task_id,
                    project_id,
                )
                return None

            task = rows[0]
            task["id"] = str(task["id"])

            if task["type"] == "compliance" and task.get("reference_id"):
                # Join compliance_checks data
                check_response = (
                    self.client.table("compliance_checks")
                    .select("risk_percentage, status, market, s3_upload_key, s3_segmented_key, s3_remix_key, result_json, check_id, media_type")
                    .eq("check_id", task["reference_id"])
                    .execute()
                )
                check_rows = check_response.data or []
                if check_rows:
                    check = check_rows[0]
                    # Fetch violations for this check
                    violations_response = (
                        self.client.table("violations")
                        .select("*")
                        .eq("check_id", task["reference_id"])
                        .execute()
                    )
                    violations = violations_response.data or []

                    task["compliance"] = {
                        "risk_percentage": check.get("risk_percentage"),
                        "status": check.get("status"),
                        "market": check.get("market"),
                        "media_type": check.get("media_type"),
                        "violations": violations,
                        "s3_upload_key": check.get("s3_upload_key"),
                        "s3_segmented_key": check.get("s3_segmented_key"),
                        "s3_remix_key": check.get("s3_remix_key"),
                        "result_json": check.get("result_json"),
                    }
                    # Also expose pipeline_state at the task level
                    # (it's already in the task row from the tasks table)

            logger.info(
                "[SupabaseComplianceStore] Fetched detail for task %s", task_id
            )
            return task
        except Exception as e:
            logger.error(
                "[SupabaseComplianceStore] Failed to get task detail %s: %s",
                task_id,
                e,
            )
            return None

def update_task_pipeline(
        self, project_id: str, task_id: str, status: str, pipeline_state: dict
    ) -> bool:
        """Persist compliance pipeline state and workflow status for a task.

        Status should reflect the actual workflow stage:
        - 'checked'  — compliance analysis completed
        - 'reviewed' — user has reviewed the results
        - 'remixed'  — remediation has been applied
        - 'compared' — comparison between original and remix completed
        - 'saved'    — pipeline state saved (for generation tasks)

        Args:
            project_id: The project UUID the task belongs to.
            task_id: The task UUID to update.
            status: New status value.
            pipeline_state: The pipeline graph state to persist.

        Returns:
            True if the update succeeded, False otherwise.
        """
        try:
            update_data = {
                "status": status,
                "pipeline_state": pipeline_state,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            self.client.table("tasks").update(update_data).eq(
                "id", task_id
            ).eq("project_id", project_id).execute()
            logger.info(
                "[SupabaseComplianceStore] Updated pipeline for task %s to status: %s",
                task_id,
                status,
            )
            return True
        except Exception as e:
            logger.error(
                "[SupabaseComplianceStore] Failed to update pipeline for task %s: %s",
                task_id,
                e,
            )
            return False

    def update_project_name(self, project_id: str, name: str) -> dict:
        """Update the project name and return the updated row.

        Args:
            project_id: The project UUID to update.
            name: The new project name (will be trimmed).

        Returns:
            The updated project row as a dict with id as string.

        Raises:
            RuntimeError: If Supabase update returned no data.
        """
        try:
            trimmed_name = name.strip()
            update_data = {
                "name": trimmed_name,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            response = (
                self.client.table("projects")
                .update(update_data)
                .eq("id", project_id)
                .execute()
            )
            if response.data:
                row = response.data[0]
                row["id"] = str(row["id"])
                logger.info(
                    "[SupabaseComplianceStore] Updated project %s name to '%s'",
                    project_id,
                    trimmed_name,
                )
                return row
            raise RuntimeError("Supabase update returned no data")
        except RuntimeError:
            raise
        except Exception as e:
            logger.error(
                "[SupabaseComplianceStore] Failed to update project %s name: %s",
                project_id,
                e,
            )
            raise

    # ─── Delete Operations ────────────────────────────────────────────────

    def delete_project(self, project_id: str) -> bool:
        """Delete a project and all its associated data (CASCADE).

        Due to ON DELETE CASCADE on foreign keys, this also removes:
        - All tasks for this project
        - All compliance_checks for this project
        - All violations for those checks

        Args:
            project_id: The project UUID to delete.

        Returns:
            True if deleted successfully, False otherwise.
        """
        try:
            self.client.table("projects").delete().eq("id", project_id).execute()
            logger.info(
                "[SupabaseComplianceStore] Deleted project %s (cascade)",
                project_id,
            )
            return True
        except Exception as e:
            logger.error(
                "[SupabaseComplianceStore] Failed to delete project %s: %s",
                project_id,
                e,
            )
            return False

    def delete_task(self, project_id: str, task_id: str) -> bool:
        """Delete a single task from a project.

        Args:
            project_id: The project UUID the task belongs to.
            task_id: The task UUID to delete.

        Returns:
            True if deleted successfully, False otherwise.
        """
        try:
            self.client.table("tasks").delete().eq(
                "id", task_id
            ).eq("project_id", project_id).execute()
            logger.info(
                "[SupabaseComplianceStore] Deleted task %s from project %s",
                task_id,
                project_id,
            )
            return True
        except Exception as e:
            logger.error(
                "[SupabaseComplianceStore] Failed to delete task %s: %s",
                task_id,
                e,
            )
            return False

    # ─── Health ─────────────────────────────────────────────────────────

    def health_check(self) -> bool:
        """Check Supabase connectivity by querying the compliance_checks table.

        Returns:
            True if the connection is healthy, False otherwise.
        """
        try:
            self.client.table("compliance_checks").select("check_id").limit(1).execute()
            return True
        except Exception:
            return False
