"""
routes/progress.py
──────────────────
Retired progress polling endpoint.

The pipeline_progress table was retired in favour of task pipeline-state JSON
and the authenticated compliance SSE stream. This router is not mounted by the
application; it safely documents the replacement if mounted accidentally.
"""

import re

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["progress"])

# Valid task_id: uuid format or 1-64 alphanumeric/hex characters
_TASK_ID_PATTERN = re.compile(r"^[a-zA-Z0-9\-]{1,64}$")


def _is_valid_task_id(task_id: str) -> bool:
    """Validate task_id format (alphanumeric/hex/uuid, 1-64 chars)."""
    return bool(_TASK_ID_PATTERN.match(task_id))


def compute_is_terminal(steps: list[dict]) -> bool:
    """Determine if a pipeline has reached a terminal state.

    Terminal = all statuses are "completed" OR at least one is "error".
    Empty list is NOT terminal (pipeline hasn't started).
    """
    if not steps:
        return False
    statuses = [s["status"] for s in steps]
    if any(s == "error" for s in statuses):
        return True
    if all(s == "completed" for s in statuses):
        return True
    return False


@router.get("/api/compliance/{task_id}/progress")
async def get_progress(task_id: str) -> JSONResponse:
    """Explain that polling progress has been retired."""
    # Validate task_id format
    if not _is_valid_task_id(task_id):
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid task_id format"},
        )

    return JSONResponse(
        status_code=410,
        content={
            "error": "Progress polling was retired; use the compliance event stream instead",
        },
    )
