"""
chat_store.py
─────────────
Chat-history persistence for the Agentic Ad Studio (Req 6).

This module is the *only* persistence concern for chat turns. It stores each
turn in the dedicated ``chat_messages`` Supabase table (migration 013), scoped
by ``project_id`` and ``task_id``, and reuses the shared Supabase client and the
existing ``fallback_queue`` singleton for deferred retry.

Follows the module-function pattern established in ``agent/supabase_client.py``:
plain module-level functions (no class wrapper), resilient try/except around the
external Supabase call, and ``[ChatStore]``-prefixed logging.
"""

import logging
from typing import Literal

from shared.clients import supabase
from shared.fallback_queue import fallback_queue

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
MAX_CONTENT_CHARS = 10000  # DB CHECK: char_length(content) <= 10000 (Req 6.2)
DEFAULT_RECENT_LIMIT = 20  # last-N conversational-memory read (Req 6.6)
CHAT_MESSAGES_TABLE = "chat_messages"

Role = Literal["user", "assistant"]


class ChatPersistenceError(Exception):
    """Raised when a chat turn cannot be persisted to the Chat_Message_Store.

    The unsaved turn is enqueued to the shared ``fallback_queue`` for deferred
    retry before this error is raised, so the turn is never silently dropped
    (Req 6.7).
    """


def create_chat_message(
    project_id: str,
    task_id: str,
    role: Role,
    content: str,
    attachments: list | None = None,
) -> dict:
    """Insert one chat turn into the ``chat_messages`` table.

    ``content`` is truncated to at most ``MAX_CONTENT_CHARS`` characters to
    satisfy the table CHECK constraint (Req 6.2). On persistence failure the
    turn is enqueued to the shared ``fallback_queue`` for deferred retry and a
    ``ChatPersistenceError`` is raised so the caller can surface the failure
    without discarding the turn (Req 6.7).

    Args:
        project_id: Owning project id.
        task_id: Owning task id.
        role: Either ``"user"`` or ``"assistant"``.
        content: The turn text; truncated to 10,000 chars if longer.
        attachments: Optional list of attachment refs; defaults to ``[]``.

    Returns:
        The inserted row dict with ``id`` coerced to ``str``.

    Raises:
        ChatPersistenceError: When the insert fails (after enqueuing for retry).
    """
    safe_content = content[:MAX_CONTENT_CHARS] if content else ""
    if content and len(content) > MAX_CONTENT_CHARS:
        logger.warning(
            "[ChatStore] Truncated %s content from %d to %d chars (task %s)",
            role, len(content), MAX_CONTENT_CHARS, task_id,
        )

    payload = {
        "project_id": str(project_id),
        "task_id": str(task_id),
        "role": role,
        "content": safe_content,
        "attachments": attachments if attachments is not None else [],
    }

    try:
        response = supabase.table(CHAT_MESSAGES_TABLE).insert(payload).execute()
        if response.data:
            row = response.data[0]
            row["id"] = str(row["id"])
            logger.info(
                "[ChatStore] Persisted %s turn for task %s (message %s)",
                role, task_id, row["id"],
            )
            return row
        # No data returned — treat as a failed insert.
        raise RuntimeError("Supabase insert returned no data")
    except Exception as e:
        logger.error(
            "[ChatStore] Failed to persist %s turn for task %s: %s",
            role, task_id, e,
        )
        # Preserve the unsaved turn for deferred retry (Req 6.7).
        fallback_queue.enqueue(CHAT_MESSAGES_TABLE, "insert", payload)
        raise ChatPersistenceError(
            f"Failed to persist {role} chat turn for task {task_id}: {e}"
        ) from e


def list_recent_chat_messages(
    project_id: str,
    task_id: str,
    limit: int = DEFAULT_RECENT_LIMIT,
) -> list[dict]:
    """Return up to ``limit`` most-recent chat turns in ascending time order.

    Used as the Orchestrator's conversational memory (Req 6.6). The rows are
    read most-recent-first (to take the last ``limit``) and then reversed so the
    returned list is ordered by ``created_at`` ascending. Returns an empty list
    when no history exists, without raising (Req 6.8).

    Args:
        project_id: Owning project id.
        task_id: Owning task id.
        limit: Maximum number of recent turns to return (default 20).

    Returns:
        A list of turn dicts (``id`` coerced to ``str``) ordered oldest → newest.
    """
    try:
        response = (
            supabase.table(CHAT_MESSAGES_TABLE)
            .select("*")
            .eq("project_id", str(project_id))
            .eq("task_id", str(task_id))
            .order("created_at", desc=True)
            .limit(max(1, limit))
            .execute()
        )
        rows = response.data or []
        rows.reverse()  # newest-first → oldest-first (ascending by created_at)
        for row in rows:
            row["id"] = str(row["id"])
        logger.info(
            "[ChatStore] Read %d recent turns for task %s (limit %d)",
            len(rows), task_id, limit,
        )
        return rows
    except Exception as e:
        logger.error(
            "[ChatStore] Failed to read recent turns for task %s: %s",
            task_id, e,
        )
        return []


def list_chat_history(project_id: str, task_id: str) -> list[dict]:
    """Return the full ordered chat history for a (project, task).

    Backs the ``GET .../chat-history`` endpoint (Req 11.5). Rows are ordered by
    ``created_at`` ascending. Returns an empty list when no history exists,
    without raising.

    Args:
        project_id: Owning project id.
        task_id: Owning task id.

    Returns:
        A list of turn dicts (``id`` coerced to ``str``) ordered oldest → newest.
    """
    try:
        response = (
            supabase.table(CHAT_MESSAGES_TABLE)
            .select("*")
            .eq("project_id", str(project_id))
            .eq("task_id", str(task_id))
            .order("created_at", desc=False)
            .execute()
        )
        rows = response.data or []
        for row in rows:
            row["id"] = str(row["id"])
        logger.info(
            "[ChatStore] Read full history (%d turns) for task %s",
            len(rows), task_id,
        )
        return rows
    except Exception as e:
        logger.error(
            "[ChatStore] Failed to read history for task %s: %s",
            task_id, e,
        )
        return []
