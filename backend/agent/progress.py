"""
progress.py
───────────
Thread-safe progress emitter for pipeline nodes.

Uses a simple list buffer that pipeline nodes append to synchronously.
The pipeline_runner drains and sends these messages after each node completes.

Usage in pipeline nodes:
    from agent.progress import emit_progress
    emit_progress("Fetching regulatory rules for Malaysia...")

Usage in pipeline_runner (after each node):
    from agent.progress import drain_progress
    messages = drain_progress()
    for msg in messages:
        await manager.send_message(check_id, {"type": "progress", "message": msg})
"""

import logging
import threading

logger = logging.getLogger(__name__)

# Thread-safe buffer for progress messages
_progress_lock = threading.Lock()
_progress_buffer: list[str] = []


def emit_progress(message: str) -> None:
    """Buffer a progress message for the current pipeline step.

    Safe to call from synchronous pipeline nodes. Messages are buffered
    and drained by the pipeline_runner after each node completes.

    Args:
        message: Human-readable progress description.
    """
    with _progress_lock:
        _progress_buffer.append(message)


def drain_progress() -> list[str]:
    """Drain all buffered progress messages and return them.

    Called by the pipeline_runner after each node to send via WebSocket.

    Returns:
        List of progress message strings (may be empty).
    """
    with _progress_lock:
        messages = _progress_buffer.copy()
        _progress_buffer.clear()
    return messages
