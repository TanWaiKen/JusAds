"""
progress_tracker.py
───────────────────
Compatibility progress tracker for legacy pipeline components.

The pipeline_progress table was intentionally retired. Current user-facing
progress is delivered by the pipeline SSE stream and task pipeline_state JSON,
so this class records structured application logs only. It remains deliberately
non-blocking while old pipeline agents are migrated away from this interface.
"""

import logging
logger = logging.getLogger(__name__)


class ProgressTracker:
    """Non-blocking compatibility layer; does not persist a duplicate tracker."""

    def start_step(self, task_id: str, step_name: str) -> None:
        """Log a pipeline step start.

        Args:
            task_id: The compliance task identifier.
            step_name: Name of the pipeline step being started.
        """
        logger.info("[ProgressTracker] Started step '%s' for task_id=%s", step_name, task_id)

    def complete_step(self, task_id: str, step_name: str, message: str = "") -> None:
        """Log a completed pipeline step.

        Args:
            task_id: The compliance task identifier.
            step_name: Name of the pipeline step that completed.
            message: Optional outcome summary (truncated to 500 chars).
        """
        logger.info("[ProgressTracker] Completed step '%s' for task_id=%s: %s", step_name, task_id, self._truncate(message))

    def fail_step(self, task_id: str, step_name: str, error_message: str = "") -> None:
        """Log a failed pipeline step.

        Args:
            task_id: The compliance task identifier.
            step_name: Name of the pipeline step that failed.
            error_message: Error description (truncated to 500 chars).
        """
        logger.error("[ProgressTracker] Failed step '%s' for task_id=%s: %s", step_name, task_id, self._truncate(error_message))

    def _truncate(self, text: str, max_length: int = 500) -> str:
        """Truncate text to max_length characters.

        Args:
            text: The text to truncate.
            max_length: Maximum allowed length (default 500).

        Returns:
            The original text if within limit, otherwise truncated to max_length.
        """
        return text[:max_length] if len(text) > max_length else text
