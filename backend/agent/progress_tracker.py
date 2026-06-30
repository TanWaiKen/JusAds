"""
progress_tracker.py
───────────────────
Persists pipeline step progress to the pipeline_progress Supabase table.

Replaces the old WebSocket-based progress.py with a fire-and-forget
pattern: all methods catch exceptions and never raise, ensuring
pipeline execution is never blocked by progress tracking failures.
"""

import logging
from datetime import datetime, timezone

from agent.clients import supabase

logger = logging.getLogger(__name__)


class ProgressTracker:
    """Persists pipeline step progress to the pipeline_progress Supabase table.

    All methods are fire-and-forget: failures are logged but never raised.
    """

    def start_step(self, check_id: str, step_name: str) -> None:
        """Insert a 'running' row for a pipeline step.

        Args:
            check_id: The compliance check identifier.
            step_name: Name of the pipeline step being started.
        """
        try:
            supabase.table("pipeline_progress").insert({
                "check_id": check_id,
                "step_name": step_name,
                "status": "running",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).execute()
            logger.info("[ProgressTracker] Started step '%s' for check_id=%s", step_name, check_id)
        except Exception as e:
            logger.error(
                "[ProgressTracker] Failed to start step '%s' for check_id=%s: %s",
                step_name, check_id, e,
            )

    def complete_step(self, check_id: str, step_name: str, message: str = "") -> None:
        """Update step row to 'completed' with truncated message.

        Args:
            check_id: The compliance check identifier.
            step_name: Name of the pipeline step that completed.
            message: Optional outcome summary (truncated to 500 chars).
        """
        try:
            supabase.table("pipeline_progress").update({
                "status": "completed",
                "message": self._truncate(message),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("check_id", check_id).eq("step_name", step_name).execute()
            logger.info("[ProgressTracker] Completed step '%s' for check_id=%s", step_name, check_id)
        except Exception as e:
            logger.error(
                "[ProgressTracker] Failed to complete step '%s' for check_id=%s: %s",
                step_name, check_id, e,
            )

    def fail_step(self, check_id: str, step_name: str, error_message: str = "") -> None:
        """Update step row to 'error' with truncated error message.

        Args:
            check_id: The compliance check identifier.
            step_name: Name of the pipeline step that failed.
            error_message: Error description (truncated to 500 chars).
        """
        try:
            supabase.table("pipeline_progress").update({
                "status": "error",
                "message": self._truncate(error_message),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("check_id", check_id).eq("step_name", step_name).execute()
            logger.info("[ProgressTracker] Failed step '%s' for check_id=%s", step_name, check_id)
        except Exception as e:
            logger.error(
                "[ProgressTracker] Failed to record error for step '%s' check_id=%s: %s",
                step_name, check_id, e,
            )

    def _truncate(self, text: str, max_length: int = 500) -> str:
        """Truncate text to max_length characters.

        Args:
            text: The text to truncate.
            max_length: Maximum allowed length (default 500).

        Returns:
            The original text if within limit, otherwise truncated to max_length.
        """
        return text[:max_length] if len(text) > max_length else text
