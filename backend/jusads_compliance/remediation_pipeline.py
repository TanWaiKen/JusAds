"""LangGraph orchestration for concrete compliance remediation agents.

Media-specific work belongs in :mod:`jusads_compliance.remix_agent`. This
module only loads the check, obtains a user-approved aspect ratio where needed,
routes to the appropriate agent, and persists the resulting asset URL.
"""

import logging
import os

from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from jusads_compliance.progress_tracker import ProgressTracker
from jusads_compliance.remix_agent import (
    remediate_audio as audio_agent,
    remediate_image as image_agent,
    remediate_text as text_agent,
    remediate_video as video_agent,
)
from jusads_compliance.remix_agent.localization import plan_localization
from shared.clients import supabase
from shared.models import Remediation_State
from shared.s3_client import build_s3_key, upload_file_public

logger = logging.getLogger(__name__)
_tracker = ProgressTracker()


def fetch_compliance_result(state: dict) -> dict:
    """Load persisted compliance context and construct an agent input plan."""
    task_id = state["task_id"]
    _tracker.start_step(task_id, "fetch_compliance_result")
    try:
        rows = supabase.table("compliance_checks").select("*").eq("task_id", task_id).execute().data or []
        if not rows:
            message = f"task_id '{task_id}' not found"
            _tracker.fail_step(task_id, "fetch_compliance_result", message)
            return {"status": "remix_failed", "compliance_result": {"error": message}}

        record = rows[0]
        result = record.get("result_json") or {}
        # result_json is the analytical report; table fields are the stable
        # audience context selected for this particular compliance task.
        result = {
            **result,
            "market": record.get("market", result.get("market", "malaysia")),
            "ethnicity": record.get("ethnicity", result.get("ethnicity", "all")),
            "age_group": record.get("age_group", result.get("age_group", "all_ages")),
            "platform": record.get("platform", result.get("platform", "general")),
        }
        plan = {
            "high_risk_indicators": result.get("high_risk_indicator", []),
            "suggestion": result.get("suggestion", ""),
            "localization_plan": result.get("localization_plan", ""),
            "violations_timeline": result.get("violations_timeline") or [],
            "segmentation": result.get("segmentation"),
        }
        media_type = record.get("media_type", "")
        _tracker.complete_step(task_id, "fetch_compliance_result", f"Retrieved {media_type} check record")
        return {
            "project_id": record.get("project_id") or "",
            "compliance_result": result,
            "remediation_plan": plan,
            "media_type": media_type,
            "source_media_url": record.get("s3_upload_key", ""),
            "platform_target": record.get("platform", "general"),
            "status": "remediating",
        }
    except Exception as exc:
        logger.exception("[RemediationPipeline] Failed to fetch task %s", task_id)
        _tracker.fail_step(task_id, "fetch_compliance_result", str(exc))
        return {"status": "remix_failed", "compliance_result": {"error": str(exc)}}


def plan_localization_for_remediation(state: dict) -> dict:
    """Make an auditable locale decision before any media generator is invoked."""
    if state.get("status") == "remix_failed":
        return {}
    task_id = state["task_id"]
    _tracker.start_step(task_id, "plan_localization")
    try:
        result = state.get("compliance_result") or {}
        language_compliance = result.get("language_compliance") or {}
        decision = plan_localization(
            market=result.get("market", "malaysia"),
            ethnicity=result.get("ethnicity", "all"),
            age_group=result.get("age_group", "all_ages"),
            platform=state.get("platform_target", "general"),
            required_language=language_compliance.get("required_language", "") if isinstance(language_compliance, dict) else "",
            localization_plan=(state.get("remediation_plan") or {}).get("localization_plan", ""),
        )
        plan = {**(state.get("remediation_plan") or {}), "localization": decision}
        _tracker.complete_step(task_id, "plan_localization", f"Output: {decision['output_language']}")
        return {"remediation_plan": plan}
    except Exception as exc:
        logger.exception("[RemediationPipeline] Localization planning failed")
        _tracker.fail_step(task_id, "plan_localization", str(exc))
        return {"status": "remix_failed"}


def confirm_aspect_ratio(state: dict) -> dict:
    """Request a ratio choice for visual media; audio and text need none."""
    task_id = state["task_id"]
    media_type = state["media_type"]
    platform = state["platform_target"]
    _tracker.start_step(task_id, "confirm_aspect_ratio")
    if media_type not in {"image", "video"}:
        _tracker.complete_step(task_id, "confirm_aspect_ratio", f"Skipped for {media_type}")
        return {"aspect_ratio": ""}

    try:
        rules = (
            supabase.table("platform_rules")
            .select("aspect_ratio, max_duration_seconds, max_file_size_mb")
            .eq("platform", platform)
            .eq("media_type", media_type)
            .execute()
            .data
            or []
        )
        if not rules:
            ratio = {"image": "1:1", "video": "16:9"}[media_type]
        else:
            options = [{
                "aspect_ratio": item["aspect_ratio"],
                "max_duration_seconds": item.get("max_duration_seconds"),
                "max_file_size_mb": item.get("max_file_size_mb"),
            } for item in rules]
            answer = interrupt({
                "message": f"Confirm target aspect ratio for {platform} {media_type}",
                "options": options,
                "default": options[0]["aspect_ratio"],
            })
            ratio = answer.get("aspect_ratio", options[0]["aspect_ratio"]) if isinstance(answer, dict) else answer
            ratio = ratio if isinstance(ratio, str) else options[0]["aspect_ratio"]

        _tracker.complete_step(task_id, "confirm_aspect_ratio", f"Confirmed: {ratio}")
        return {"aspect_ratio": ratio}
    except Exception as exc:
        logger.exception("[RemediationPipeline] Aspect-ratio confirmation failed")
        _tracker.fail_step(task_id, "confirm_aspect_ratio", str(exc))
        return {"status": "remix_failed", "aspect_ratio": ""}


def media_remediation(state: dict) -> dict:
    """Run the dedicated concrete agent for the checked media type."""
    if state.get("status") == "remix_failed":
        return {}

    task_id = state["task_id"]
    media_type = state["media_type"]
    _tracker.start_step(task_id, "media_remediation")
    agents = {"audio": audio_agent, "image": image_agent, "text": text_agent, "video": video_agent}
    try:
        agent = agents.get(media_type)
        if agent is None:
            raise ValueError(f"Unsupported media type: {media_type}")
        result = agent(state)
        if result.get("error"):
            raise RuntimeError(result["error"])

        paths = list(state.get("remediated_paths") or [])
        if result.get("output_path"):
            paths.append(result["output_path"])
        _tracker.complete_step(task_id, "media_remediation", f"{media_type} remediation completed")
        return {
            "remediated_paths": paths,
            "strategy": result.get("strategy", media_type),
            "remix_url": result.get("asset_url") or state.get("remix_url", ""),
        }
    except Exception as exc:
        logger.exception("[RemediationPipeline] %s remediation failed", media_type)
        _tracker.fail_step(task_id, "media_remediation", str(exc))
        return {"status": "remix_failed", "remediated_paths": state.get("remediated_paths", [])}


def upload_and_finalize(state: dict) -> dict:
    """Publish an agent result (if needed) and persist its stable public URL."""
    if state.get("status") == "remix_failed":
        return {}

    task_id = state["task_id"]
    _tracker.start_step(task_id, "upload_and_finalize")
    try:
        remix_url = state.get("remix_url")
        paths = state.get("remediated_paths") or []
        if not remix_url:
            if not paths:
                raise ValueError("No remediated asset was produced")
            output_path = paths[-1]
            remix_url = upload_file_public(
                output_path,
                build_s3_key(
                    asset_type="remixed",
                    username="pipeline",
                    project_id=str(state.get("project_id") or task_id),
                    check_id=task_id,
                    filename=os.path.basename(output_path),
                ),
            )

        supabase.table("compliance_checks").update({
            "status": "remediated",
            "s3_remix_key": remix_url,
        }).eq("task_id", task_id).execute()
        _tracker.complete_step(task_id, "upload_and_finalize", f"Published: {remix_url}")
        return {"status": "remediated", "remix_url": remix_url}
    except Exception as exc:
        logger.exception("[RemediationPipeline] Finalization failed for %s", task_id)
        _tracker.fail_step(task_id, "upload_and_finalize", str(exc))
        try:
            supabase.table("compliance_checks").update({"status": "remix_failed"}).eq("task_id", task_id).execute()
        except Exception:
            logger.exception("[RemediationPipeline] Could not mark %s as remix_failed", task_id)
        return {"status": "remix_failed"}


_graph = StateGraph(Remediation_State)
_graph.add_node("fetch_compliance_result", fetch_compliance_result)
_graph.add_node("plan_localization", plan_localization_for_remediation)
_graph.add_node("confirm_aspect_ratio", confirm_aspect_ratio)
_graph.add_node("media_remediation", media_remediation)
_graph.add_node("upload_and_finalize", upload_and_finalize)
_graph.set_entry_point("fetch_compliance_result")
_graph.add_edge("fetch_compliance_result", "plan_localization")
_graph.add_edge("plan_localization", "confirm_aspect_ratio")
_graph.add_edge("confirm_aspect_ratio", "media_remediation")
_graph.add_edge("media_remediation", "upload_and_finalize")
_graph.add_edge("upload_and_finalize", END)

remediation_pipeline = _graph.compile()
