"""
routes/progress.py
──────────────────
Progress polling endpoint for pipeline execution tracking.

Replaces WebSocket-based progress delivery with HTTP polling against
the `pipeline_progress` Supabase table.
"""

import logging
import re

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from agent.clients import supabase

logger = logging.getLogger(__name__)

router = APIRouter(tags=["progress"])

# Valid check_id: 1-64 alphanumeric/hex characters (covers uuid hex substrings)
_CHECK_ID_PATTERN = re.compile(r"^[a-zA-Z0-9\-]{1,64}$")


def _is_valid_check_id(check_id: str) -> bool:
    """Validate check_id format (alphanumeric/hex, 1-64 chars)."""
    return bool(_CHECK_ID_PATTERN.match(check_id))


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


@router.get("/api/compliance/{check_id}/progress")
async def get_progress(check_id: str) -> JSONResponse:
    """Return all progress rows for a check_id, ordered by created_at ASC.

    Response:
      - steps: list of {step_name, status, message, created_at}
      - is_terminal: bool (True if all completed or any error)
    """
    # Validate check_id format
    if not _is_valid_check_id(check_id):
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid check_id format"},
        )

    # Query pipeline_progress table
    try:
        response = (
            supabase.table("pipeline_progress")
            .select("step_name, status, message, created_at")
            .eq("check_id", check_id)
            .order("created_at", desc=False)
            .execute()
        )
    except Exception as e:
        logger.error("[Progress] Database query failed for %s: %s", check_id, e)
        return JSONResponse(
            status_code=503,
            content={"error": "Service temporarily unavailable"},
        )

    rows = response.data or []

    # Format steps for response
    steps = [
        {
            "step_name": row["step_name"],
            "status": row["status"],
            "message": row.get("message") or "",
            "created_at": row["created_at"],
        }
        for row in rows
    ]

    return JSONResponse(
        status_code=200,
        content={
            "steps": steps,
            "is_terminal": compute_is_terminal(steps),
        },
    )
