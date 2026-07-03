"""
fallback_queue.py
─────────────────
Simple deferred retry queue for failed Supabase operations.

When a persistence operation fails (e.g. writing compliance results),
the payload is queued in-memory for later retry. This ensures the pipeline
can still return results to the caller even when Supabase is temporarily
unavailable.
"""

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class QueueItem:
    """A single queued operation awaiting retry."""

    table: str
    operation: str  # "insert" | "update" | "upsert"
    payload: dict
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    retries: int = 0


class FallbackQueue:
    """In-memory queue for deferred Supabase write retries.

    Thread-safe is not required here as LangGraph nodes execute sequentially
    within a single graph invocation.
    """

    def __init__(self, max_size: int = 1000) -> None:
        self._queue: deque[QueueItem] = deque(maxlen=max_size)

    def enqueue(self, table: str, operation: str, payload: dict) -> None:
        """Add a failed operation to the retry queue.

        Args:
            table: Target Supabase table name.
            operation: The operation type ("insert", "update", "upsert").
            payload: The data dict that failed to persist.
        """
        item = QueueItem(table=table, operation=operation, payload=payload)
        self._queue.append(item)
        logger.warning(
            "[FallbackQueue] Enqueued %s on '%s' (queue size: %d)",
            operation, table, len(self._queue),
        )

    def drain(self) -> list[QueueItem]:
        """Remove and return all queued items for retry processing.

        Returns:
            List of QueueItem instances to be retried.
        """
        items = list(self._queue)
        self._queue.clear()
        return items

    @property
    def size(self) -> int:
        """Current number of items in the queue."""
        return len(self._queue)

    @property
    def is_empty(self) -> bool:
        """Whether the queue has no pending items."""
        return len(self._queue) == 0


# Module-level singleton instance for use across the pipeline
fallback_queue = FallbackQueue()
