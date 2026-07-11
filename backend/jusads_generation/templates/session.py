"""
templates/session.py
────────────────────
Session memory persistence for iterative prompt generation.

Manages loading and saving of generation turns per project/task pair,
with Supabase persistence and graceful in-memory fallback on failure.

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 8.1, 8.2, 8.3
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

from shared.clients import supabase
from shared.fallback_queue import fallback_queue

from . import CompositionResult, GenerationTurn, SessionContext
from .registry import _REGISTRY

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

_MAX_TURNS = 20
_TABLE_NAME = "generation_sessions"


# ─── Public API ───────────────────────────────────────────────────────────────


def load_session(project_id: str, task_id: str) -> SessionContext:
    """Load or create session memory for the given project/task.

    Attempts to load from Supabase first. If Supabase is unavailable or
    the query fails, returns an in-memory fallback (empty session).

    Args:
        project_id: The project identifier.
        task_id: The task identifier within the project.

    Returns:
        A SessionContext with turns ordered by timestamp ascending.
    """
    # Default empty session as fallback
    empty_session: SessionContext = SessionContext(
        project_id=project_id,
        task_id=task_id,
        turns=[],
        active_style=None,
        active_template_id=None,
    )

    if supabase is None:
        logger.warning(
            "[SessionMemory] Supabase unavailable, returning in-memory fallback"
        )
        return empty_session

    try:
        response = (
            supabase.table(_TABLE_NAME)
            .select("*")
            .eq("project_id", project_id)
            .eq("task_id", task_id)
            .execute()
        )

        if not response.data:
            logger.info(
                "[SessionMemory] No existing session for project=%s task=%s, "
                "returning empty session",
                project_id,
                task_id,
            )
            return empty_session

        row = response.data[0]
        turns: list[GenerationTurn] = row.get("turns", [])

        # Order turns by timestamp ascending
        turns.sort(key=lambda t: t.get("timestamp", ""))

        session = SessionContext(
            project_id=project_id,
            task_id=task_id,
            turns=turns,
            active_style=row.get("active_style"),
            active_template_id=row.get("active_template_id"),
        )

        logger.info(
            "[SessionMemory] Loaded session for project=%s task=%s (%d turns)",
            project_id,
            task_id,
            len(turns),
        )
        return session

    except Exception as e:
        logger.warning(
            "[SessionMemory] Failed to load session from Supabase, "
            "using in-memory fallback: %s",
            e,
        )
        return empty_session


def save_generation_turn(
    session_ctx: SessionContext,
    result: CompositionResult,
    output_urls: list[str],
) -> SessionContext:
    """Persist a generation turn and update session memory.

    Appends the new turn, caps at 20, extracts style-group fields into
    active_style, and persists to Supabase (or enqueues to FallbackQueue
    on failure).

    Args:
        session_ctx: The current session context to update.
        result: The composition result from compose_prompt/compose_iteration.
        output_urls: URLs of generated outputs (may be empty).

    Returns:
        Updated SessionContext with the new turn appended.
    """
    # Step 1: Build the turn record
    template_id = result["template_id"]
    ad_type = _get_ad_type_for_template(template_id)

    turn = GenerationTurn(
        turn_id=str(uuid.uuid4()),
        template_id=template_id,
        field_values=result["field_values"],
        composed_prompt=result["composed_prompt"],
        negative_prompt=result.get("negative_prompt"),
        output_urls=output_urls,
        ad_type=ad_type,
        timestamp=datetime.utcnow().isoformat(),
    )

    # Step 2: Append to session turns (cap at 20)
    session_ctx["turns"].append(turn)
    if len(session_ctx["turns"]) > _MAX_TURNS:
        session_ctx["turns"] = session_ctx["turns"][-_MAX_TURNS:]

    # Step 3: Extract style fields for persistence across iterations
    style_fields = _extract_style_fields(template_id, result["field_values"])
    session_ctx["active_style"] = style_fields
    session_ctx["active_template_id"] = template_id

    # Step 4: Persist to Supabase (graceful degradation)
    _persist_session(session_ctx, style_fields, template_id)

    logger.info(
        "[SessionMemory] Saved turn %s for project=%s task=%s (%d total turns)",
        turn["turn_id"],
        session_ctx["project_id"],
        session_ctx["task_id"],
        len(session_ctx["turns"]),
    )

    return session_ctx


# ─── Internal Helpers ─────────────────────────────────────────────────────────


def _get_ad_type_for_template(template_id: str) -> str:
    """Look up the ad_type for a given template_id from the registry."""
    template = _REGISTRY.get(template_id)
    if template:
        return template["ad_type"]
    # Fallback if template not found (shouldn't happen in normal flow)
    logger.warning(
        "[SessionMemory] Template '%s' not found in registry, defaulting ad_type to 'poster'",
        template_id,
    )
    return "poster"


def _extract_style_fields(
    template_id: str, field_values: dict[str, str]
) -> dict[str, str]:
    """Extract style-group fields from field values based on template definition."""
    template = _REGISTRY.get(template_id)
    if not template:
        return {}

    style_fields: dict[str, str] = {}
    for field in template["fields"]:
        if field["group"] == "style" and field["name"] in field_values:
            style_fields[field["name"]] = field_values[field["name"]]

    return style_fields


def _persist_session(
    session_ctx: SessionContext,
    style_fields: dict[str, str],
    template_id: str,
) -> None:
    """Persist session to Supabase with graceful degradation.

    On failure, enqueues the operation to FallbackQueue for deferred retry.
    """
    if supabase is None:
        logger.warning(
            "[SessionMemory] Supabase unavailable, enqueuing to fallback queue"
        )
        fallback_queue.enqueue(
            table=_TABLE_NAME,
            operation="upsert",
            payload={
                "project_id": session_ctx["project_id"],
                "task_id": session_ctx["task_id"],
                "turns": session_ctx["turns"],
                "active_style": style_fields,
                "active_template_id": template_id,
            },
        )
        return

    try:
        supabase.table(_TABLE_NAME).upsert({
            "project_id": session_ctx["project_id"],
            "task_id": session_ctx["task_id"],
            "turns": session_ctx["turns"],
            "active_style": style_fields,
            "active_template_id": template_id,
        }).execute()
    except Exception as e:
        logger.warning(
            "[SessionMemory] Persistence failed, enqueuing to fallback queue: %s", e
        )
        fallback_queue.enqueue(
            table=_TABLE_NAME,
            operation="upsert",
            payload={
                "project_id": session_ctx["project_id"],
                "task_id": session_ctx["task_id"],
                "turns": session_ctx["turns"],
                "active_style": style_fields,
                "active_template_id": template_id,
            },
        )
