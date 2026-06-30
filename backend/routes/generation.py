"""
routes/generation.py
────────────────────
FastAPI routes for ad generation chat.
"""

import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agent.supabase_client import SupabaseComplianceStore
from agent.generation_agent import run_generation_chat_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["generation"])

_store: SupabaseComplianceStore | None = None


def init_generation(store: SupabaseComplianceStore | None):
    """Injects the Supabase client store at app startup."""
    global _store
    _store = store


class ChatRequest(BaseModel):
    message: str


@router.post("/projects/{project_id}/tasks/{task_id}/chat")
async def chat_with_generation_agent(project_id: str, task_id: str, body: ChatRequest) -> JSONResponse:
    """Send a message to the AI generation agent, update canvas state, and save in database."""
    if not _store:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    try:
        # 1. Fetch current task detail to get the current pipeline_state
        task = _store.get_task_detail(project_id=project_id, task_id=task_id)
        if not task:
            return JSONResponse(status_code=404, content={"error": "Task not found"})

        current_pipeline_state = task.get("pipeline_state") or {
            "nodes": [],
            "edges": [],
            "viewport": {"panX": 0, "panY": 0, "zoom": 1}
        }

        # 2. Run the orchestrator agent loop
        reply, new_pipeline_state = await run_generation_chat_agent(
            project_id=project_id,
            task_id=task_id,
            user_message=body.message,
            current_state=current_pipeline_state
        )

        # 3. Persist the updated pipeline state to the task row in Supabase
        _store.update_task_pipeline(
            project_id=project_id,
            task_id=task_id,
            status="completed",
            pipeline_state=new_pipeline_state
        )

        return JSONResponse(content={
            "reply": reply,
            "pipeline_state": new_pipeline_state
        })

    except Exception as e:
        logger.error("Error in generation chat route: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})
