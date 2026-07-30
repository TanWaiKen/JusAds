"""
routes/remix.py
───────────────
Remix/remediation endpoints for compliance checks.
Handles text rewrite, audio TTS generation, and image editing.

DEPRECATION NOTE: The new Remediation Pipeline (POST /api/compliance/{task_id}/remediate)
supersedes this SSE-based remix endpoint for new clients. This module is retained for
backward compatibility with existing frontend code that uses the SSE streaming approach.
New integrations should use the /remediate endpoint + progress polling instead.
"""

import asyncio
import hashlib
import json
import logging
import mimetypes
import os
import re
import tempfile
import time as _time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from shared.supabase_client import SupabaseComplianceStore
from shared.auth import Principal, get_current_principal
from shared.authorization import get_authorized_compliance_check
from shared.s3_client import build_s3_key, generate_presigned_url, upload_file
from jusads_compliance.capcut_artifact import CapCutArtifactError, build_capcut_editing_package
from jusads_compliance.remediation_store import RemediationStore

logger = logging.getLogger(__name__)

router = APIRouter(tags=["remix"])

# -- Shared state (injected from app.py) ---------------------------------------
_supabase_store: SupabaseComplianceStore | None = None


def init_remix(supabase_store: SupabaseComplianceStore | None) -> None:
    """Called from app.py to inject shared clients."""
    global _supabase_store
    _supabase_store = supabase_store


def _publish_remediated_asset(
    output_path: str, check: dict, task_id: str, subject: str,
) -> tuple[str, str, int]:
    """Upload one generated remediation asset and return its private key + hash."""
    if not output_path or not os.path.isfile(output_path):
        raise FileNotFoundError(f"Remediated asset was not created: {output_path}")

    project_id = str(check.get("project_id") or "remediation")
    s3_key = build_s3_key(
        "remixed",
        subject,
        project_id,
        task_id,
        os.path.basename(output_path),
    )
    upload_file(output_path, s3_key)
    digest = hashlib.sha256()
    with open(output_path, "rb") as asset:
        for chunk in iter(lambda: asset.read(1024 * 1024), b""):
            digest.update(chunk)
    return s3_key, digest.hexdigest(), os.path.getsize(output_path)


def _publish_capcut_package(
    package: dict, check: dict, task_id: str, subject: str, version_id: str,
) -> dict:
    """Upload a private editing package and return only durable metadata."""
    archive_path = str(package["archive_path"])
    filename = f"capcut-{version_id}.zip"
    key = build_s3_key(
        "remixed", subject, str(check.get("project_id") or "remediation"), task_id, filename,
    )
    try:
        upload_file(archive_path, key)
    finally:
        if os.path.exists(archive_path):
            os.remove(archive_path)
    return {
        "available": True,
        "key": key,
        "file_name": package["file_name"],
        "sha256": package["sha256"],
        "size_bytes": package["size_bytes"],
        "format": package["format"],
        "relink_media_if_prompted": package["relink_media_if_prompted"],
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# POST /api/compliance/{task_id}/remix
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.post("/api/compliance/{task_id}/remix")
async def remix_compliance(
    task_id: str,
    principal: Principal = Depends(get_current_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    """Run AI remediation for a compliance check. Returns SSE stream.

    Routes to the appropriate remix strategy based on media type:
    - text: Gemini rewrite preserving brand voice
    - audio: Rewrite + ElevenLabs TTS generation
    - image: Concept analysis → edit (Imagen) or recreate guidance
    - video: Timeline-aware media remediation and publish
    """
    if not _supabase_store:
        return JSONResponse(status_code=503, content={"error": {"code": "DATASTORE_UNAVAILABLE", "message": "Service temporarily unavailable"}})

    try:
        check = get_authorized_compliance_check(
            _supabase_store, task_id, principal, write=True,
            fields="task_id, media_type, market, ethnicity, age_group, platform, result_json, s3_upload_key, project_id",
        ).record
        version = RemediationStore(_supabase_store.client).begin_version(
            task_id=task_id,
            idempotency_key=(idempotency_key or str(uuid.uuid4()))[:200],
            media_type=str(check.get("media_type") or "text"),
            source_asset_key=check.get("s3_upload_key"),
            created_by_subject=principal.subject,
            agent_strategy="legacy_remix_adapter",
            policy_version="current",
            rule_version="current",
            model_provider="jusads",
            prompt_template_version="remix-v1",
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("[Remix] Failed to prepare remediation task_id=%s", task_id)
        return JSONResponse(status_code=503, content={"error": {"code": "REMEDIATION_UNAVAILABLE", "message": "Remediation is temporarily unavailable"}})
    media_type = check["media_type"]
    result_json = check.get("result_json") or {}
    market = check.get("market", "malaysia")
    ethnicity = check.get("ethnicity", "malay")
    age_group = check.get("age_group", "all_ages")
    platform = check.get("platform", "general")
    # Legacy remediation helpers still accept a URL. The durable record keeps
    # only the private object key; this short-lived URL never reaches clients.
    if check.get("s3_upload_key"):
        check["s3_upload_key"] = generate_presigned_url(check["s3_upload_key"], 300)

    async def generate_events():
        def emit(event: dict) -> str:
            return f"data: {json.dumps(event)}\n\n"

        try:
            violations = result_json.get("high_risk_indicator", [])
            suggestion = result_json.get("suggestion", "")

            yield emit({"type": "node_status", "node": "generate_remediation", "status": "running", "description": "Generating compliant remediation"})
            start_t = _time.time()
            remix_result_data: dict = {}

            if media_type == "text":
                remix_result_data = await asyncio.to_thread(
                    _remix_text, violations, result_json, market, platform, ethnicity, age_group
                )

            elif media_type == "audio":
                # TTS, FFmpeg, and Gemini calls are synchronous.  Offload them
                # so the preceding SSE status is sent before generation ends.
                remix_result_data = await asyncio.to_thread(
                    _remix_audio, check, violations, suggestion, result_json,
                    market, platform, ethnicity, age_group,
                )

            elif media_type == "image":
                # Image remix uses yield for progress streaming
                async for event_str in _remix_image_stream(
                    check, task_id, violations, suggestion, result_json,
                    market, platform, ethnicity, age_group
                ):
                    if isinstance(event_str, dict):
                        remix_result_data = event_str
                    else:
                        yield event_str

            elif media_type == "video":
                # Keep the established SSE UX while routing video through the
                # real remediation agent.  The previous fallback returned a
                # text suggestion and then incorrectly persisted it as a
                # successfully remediated video.
                yield emit({"type": "node_status", "node": "prepare_video_segments", "status": "running", "description": "Preparing timestamped video remediation segments"})
                yield emit({"type": "node_status", "node": "edit_video_with_omni", "status": "running", "description": "Editing affected scenes with Gemini Omni"})
                remix_result_data = await asyncio.to_thread(
                    _remix_video, check, task_id, result_json, market, platform, ethnicity, age_group
                )
                yield emit({"type": "node_status", "node": "prepare_video_segments", "status": "completed", "description": "Video remediation segments prepared"})
                if not remix_result_data.get("error"):
                    yield emit({"type": "node_status", "node": "edit_video_with_omni", "status": "completed", "description": "Gemini Omni scenes assembled into the original timeline"})

            else:
                raise RuntimeError(f"Unsupported remediation media type: {media_type}")

            if remix_result_data.get("error"):
                raise RuntimeError(remix_result_data["error"])

            # A generated media file must be published before a remediation can
            # be marked complete. Text-only remediations intentionally have no
            # asset URL, but audio/image generated files do.
            output_path = (
                remix_result_data.pop("audio_output_path", None)
                or remix_result_data.pop("image_output_path", None)
                or remix_result_data.pop("video_output_path", None)
            )
            if not output_path and media_type == "text":
                rewritten = str(remix_result_data.get("rewritten_text") or "")
                if not rewritten:
                    raise RuntimeError("No remediated text was produced")
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".txt", delete=False) as text_asset:
                    text_asset.write(rewritten)
                    output_path = text_asset.name
            if output_path:
                yield emit({"type": "node_status", "node": "upload_remediated_asset", "status": "running", "description": "Uploading remediated media"})
                try:
                    package = None
                    if media_type == "video":
                        try:
                            package = build_capcut_editing_package(
                                remix_result_data.get("capcut_draft"), task_id=task_id,
                            )
                        except CapCutArtifactError as exc:
                            # An editable package is optional, but never claim a
                            # broken local draft is a downloadable user result.
                            logger.warning("[Remix] CapCut package unavailable task_id=%s: %s", task_id, exc)
                        except Exception:
                            logger.exception("[Remix] CapCut package build failed task_id=%s", task_id)

                    asset_key, asset_hash, asset_size = _publish_remediated_asset(
                        output_path, check, task_id, principal.subject,
                    )
                    capcut_metadata = None
                    if package:
                        try:
                            capcut_metadata = _publish_capcut_package(
                                package, check, task_id, principal.subject, str(version["id"]),
                            )
                        except Exception:
                            logger.exception("[Remix] CapCut package upload failed task_id=%s", task_id)
                    generation_metadata = {"media_type": media_type}
                    if capcut_metadata:
                        generation_metadata["capcut_draft"] = capcut_metadata
                    RemediationStore(_supabase_store.client).mark_generated(
                        version_id=str(version["id"]),
                        asset_key=asset_key,
                        asset_sha256=asset_hash,
                        asset_size_bytes=asset_size,
                        content_type=(
                            "text/plain"
                            if media_type == "text"
                            else mimetypes.guess_type(output_path)[0]
                        ),
                        generation_metadata=generation_metadata,
                    )
                    remix_result_data["remediation_status"] = "pending_recheck"
                    remix_result_data["s3_remix_url"] = generate_presigned_url(asset_key, 300)
                    remix_result_data["capcut_draft"] = (
                        {key: value for key, value in capcut_metadata.items() if key != "key"}
                        if capcut_metadata
                        else {"available": False}
                    )
                    logger.info("[Remix] Private remediation uploaded task_id=%s", task_id)
                finally:
                    # Generated files are transient; only the private S3 key is retained.
                    if output_path and os.path.exists(output_path):
                        os.remove(output_path)
                    if package and os.path.exists(str(package.get("archive_path") or "")):
                        os.remove(str(package["archive_path"]))
                yield emit({"type": "node_status", "node": "upload_remediated_asset", "status": "completed", "description": "Remediated media uploaded"})
            else:
                raise RuntimeError("Remediation did not produce a private asset")

            duration_ms = int((_time.time() - start_t) * 1000)
            yield emit({"type": "node_status", "node": "generate_remediation", "status": "completed", "description": "Remediation generated; compliance recheck is pending", "duration_ms": duration_ms})
            remix_result_data["version_id"] = str(version["id"])
            remix_result_data["verification_status"] = "pending_recheck"

            yield emit({"type": "remix_result", "data": remix_result_data})

        except Exception:
            logger.exception("[Remix] Error for task_id=%s", task_id)
            try:
                RemediationStore(_supabase_store.client).mark_generation_failed(
                    version_id=str(version["id"]), error_code="REMEDIATION_GENERATION_FAILED",
                )
            except Exception:
                logger.exception("[Remix] Failed to record remediation failure task_id=%s", task_id)
            yield emit({
                "type": "error",
                "code": "REMEDIATION_GENERATION_FAILED",
                "message": "Remediation could not be completed. Please try again.",
            })

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/api/compliance/{task_id}/remediation-versions/{version_id}/capcut-package")
async def get_capcut_editing_package(
    task_id: str,
    version_id: str,
    principal: Principal = Depends(get_current_principal),
):
    """Authorize a single remediation-version editing package download."""
    if not _supabase_store:
        raise HTTPException(status_code=503, detail={"code": "DATASTORE_UNAVAILABLE", "message": "Service temporarily unavailable"})
    authorized = get_authorized_compliance_check(
        _supabase_store, task_id, principal, write=False, fields="task_id, project_id",
    )
    try:
        response = (
            _supabase_store.client.table("remediation_versions")
            .select("id, task_id, generation_metadata")
            .eq("id", version_id)
            .eq("task_id", authorized.record["task_id"])
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if not rows:
            raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "Resource not found"})
        draft = (rows[0].get("generation_metadata") or {}).get("capcut_draft") or {}
        key = draft.get("key") if isinstance(draft, dict) else None
        filename = draft.get("file_name") if isinstance(draft, dict) else None
        if not isinstance(key, str) or not key.startswith("private/") or not isinstance(filename, str):
            raise HTTPException(status_code=404, detail={"code": "CAPCUT_PACKAGE_UNAVAILABLE", "message": "No editable package is available for this version"})
        return {
            "download_url": generate_presigned_url(key, 300, attachment_filename=filename),
            "file_name": filename,
            "expires_in_seconds": 300,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("[Remix] CapCut package lookup failed task_id=%s version_id=%s", task_id, version_id)
        raise HTTPException(status_code=503, detail={"code": "CAPCUT_PACKAGE_UNAVAILABLE", "message": "Editing package is temporarily unavailable"})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEXT REMIX
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _remix_text(violations, result_json, market, platform, ethnicity, age_group) -> dict:
    """Rewrite ad text to fix compliance violations."""
    from jusads_compliance.remix_tools import rewrite_text

    text_input = result_json.get("text_input", "") or result_json.get("explanation", "")
    rewrite_result = rewrite_text.invoke({
        "text": text_input,
        "violations": violations,
        "market": market,
        "platform": platform,
        "ethnicity": ethnicity,
        "age_group": age_group,
    })
    return {
        "type": "text_rewrite",
        "original_text": text_input,
        "rewritten_text": rewrite_result.get("rewritten_text", ""),
        "changes_made": rewrite_result.get("changes_made", []),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AUDIO REMIX
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _audio_violation_timeline(result_json: dict, indicators: list) -> list[dict]:
    """Return only valid audio ranges, normalised for ``remix_audio``.

    Compliance results have evolved to use both ``start/end`` and
    ``start_seconds/end_seconds``. Older checks may also have a non-empty
    timeline with no usable timings, so never pass that data through blindly.
    """
    candidates = [
        *(result_json.get("violations_timeline") or []),
        *((result_json.get("audio_annotations") or {}).get("violations") or []),
    ]
    normalised: list[dict] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        try:
            start = float(item.get("start_seconds", item.get("start")))
            end = float(item.get("end_seconds", item.get("end")))
        except (TypeError, ValueError):
            continue
        if end > start:
            normalised.append({**item, "start": start, "end": end})
    if normalised:
        return normalised

    # High-risk indicators can contain ranges such as "[00:03-00:45] ...".
    timestamp = re.compile(r"\[\s*(?:(\d+):)?(\d+(?:\.\d+)?)\s*[-–]\s*(?:(\d+):)?(\d+(?:\.\d+)?)\s*\]")
    for indicator in indicators:
        match = timestamp.search(indicator) if isinstance(indicator, str) else None
        if not match:
            continue
        start = int(match.group(1) or 0) * 60 + float(match.group(2))
        end = int(match.group(3) or 0) * 60 + float(match.group(4))
        if end > start:
            normalised.append({"start": start, "end": end, "description": indicator})
    if normalised:
        return normalised

    # A timestamped transcript permits an intentional full-audio replacement
    # when the analyser identified a spoken violation but omitted a timeline.
    transcript = result_json.get("transcript") or {}
    segments = transcript.get("segments", []) if isinstance(transcript, dict) else []
    ranges = []
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        try:
            start = float(segment.get("start_seconds", segment.get("start")))
            end = float(segment.get("end_seconds", segment.get("end")))
        except (TypeError, ValueError):
            continue
        if end > start:
            ranges.append((start, end))
    if ranges:
        return [{
            "start": min(start for start, _ in ranges),
            "end": max(end for _, end in ranges),
            "description": "Full-audio replacement based on the timestamped transcript.",
            "timing_source": "transcript_fallback",
        }]
    return []


def _remix_audio(check, violations, suggestion, result_json, market, platform, ethnicity, age_group) -> dict:
    """Rewrite transcript + generate replacement TTS audio."""
    from jusads_compliance.remix_tools import rewrite_text, remix_audio

    transcript = result_json.get("transcript") or {}
    transcript_text = transcript.get("transcript", "") if isinstance(transcript, dict) else ""
    language_compliance = result_json.get("language_compliance") or {}
    required_language = language_compliance.get("required_language", "") if isinstance(language_compliance, dict) else ""
    localization_plan = result_json.get("localization_plan", "")
    logger.info(
        "[Remix] Audio context task=%s market=%s ethnicity=%s platform=%s required_language=%s",
        check.get("task_id"), market, ethnicity, platform, required_language or "source language",
    )

    rewrite_result = rewrite_text.invoke({
        "text": transcript_text or suggestion,
        "violations": violations,
        "market": market,
        "platform": platform,
        "ethnicity": ethnicity,
        "age_group": age_group,
        "required_language": required_language,
        "localization_plan": localization_plan,
    })
    rewritten_text = rewrite_result.get("rewritten_text", "")
    if rewrite_result.get("script_valid") is False:
        return {
            "type": "audio_remix",
            "error": (
                f"The rewrite did not satisfy the required output language "
                f"({rewrite_result.get('target_language', required_language)}). No audio was generated."
            ),
            "target_language": rewrite_result.get("target_language", required_language),
        }

    violations_timeline = _audio_violation_timeline(result_json, violations)
    if not violations_timeline:
        return {
            "type": "audio_remix",
            "error": "No valid timestamps were returned for the audio violations or transcript.",
        }
    audio_result = remix_audio.invoke({
        "audio_path": check.get("s3_upload_key", ""),
        "violations": violations_timeline,
        "replacement_text": rewritten_text,
        "market": market,
        "ethnicity": ethnicity,
    })

    remix_data: dict = {
        "type": "audio_remix",
        "rewritten_text": rewritten_text,
        "target_language": rewrite_result.get("target_language", required_language),
    }
    if "error" not in audio_result:
        remix_data["audio_output_path"] = audio_result.get("output_path")
        remix_data["voice_id"] = audio_result.get("voice_id")
        remix_data["duration_seconds"] = audio_result.get("duration_seconds")
    else:
        remix_data["error"] = audio_result.get("error")

    return remix_data


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# VIDEO REMIX
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _remix_video(
    check: dict, task_id: str, result_json: dict,
    market: str, platform: str, ethnicity: str, age_group: str,
) -> dict:
    """Adapt the concrete video remediation agent to the legacy SSE contract."""
    from jusads_compliance.remix_agent.video import remediate_video
    from jusads_compliance.remix_agent.localization import plan_localization

    def json_safe(value):
        """CapCut returns path-like helper objects; SSE/JSON needs primitives."""
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict):
            return {str(key): json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [json_safe(item) for item in value]
        if isinstance(value, os.PathLike):
            return os.fspath(value)
        return str(value)

    source_url = check.get("s3_upload_key") or ""
    if not source_url:
        return {"type": "video_remix", "error": "The original video is unavailable."}

    language_compliance = result_json.get("language_compliance") or {}
    localization = plan_localization(
        market=market,
        ethnicity=ethnicity,
        age_group=age_group,
        platform=platform,
        required_language=language_compliance.get("required_language", "") if isinstance(language_compliance, dict) else "",
        localization_plan=result_json.get("localization_plan", ""),
    )
    result = remediate_video({
        "task_id": task_id,
        "source_media_url": source_url,
        "remediation_plan": {
            "violations_timeline": result_json.get("violations_timeline") or [],
            "localization_plan": result_json.get("localization_plan", ""),
            "localization": localization,
        },
    })
    if result.get("error"):
        return {"type": "video_remix", "error": result["error"]}
    return {
        "type": "video_remix",
        "video_output_path": result.get("output_path"),
        "strategy": result.get("strategy"),
        "violation_segments": result.get("violation_segments", []),
        "capcut_draft": json_safe(result.get("capcut_draft", {})),
        "omni_edit_status": result.get("omni_edit_status"),
        "omni_interaction_ids": result.get("omni_interaction_ids", []),
        "verification_status": result.get("verification_status", "pending_compliance_recheck"),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# IMAGE REMIX (async generator — yields SSE strings + final dict)
# Three-outcome triage: COMPLIANT / EDIT / CANNOT_FIX
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Valid values for input validation
_VALID_PLATFORMS = {"tiktok", "meta", "instagram", "general"}
_VALID_MARKETS = {"malaysia", "singapore"}


async def _remix_image_stream(check, task_id, violations, suggestion, result_json, market, platform, ethnicity, age_group):
    """Three-outcome image remix with triage → plan → edit flow.

    Yields SSE strings for progress and a final dict for the remix result.

    Outcomes:
      - COMPLIANT: image passes compliance, no edit needed
      - CANNOT_FIX: product/concept is the violation, return guidance
      - EDIT: plan edit via AIDesigner, execute via Imagen 3.0 inpainting
    """
    from jusads_compliance.triage import triage_decide
    from jusads_compliance.ai_designer import plan_edit
    from shared.models import TriageOutcome

    def emit(event: dict) -> str:
        return f"data: {json.dumps(event)}\n\n"

    try:
        # -- Input validation ----------------------------------------------
        risk_percentage = result_json.get("risk_percentage", 0)
        if not isinstance(risk_percentage, int):
            try:
                risk_percentage = int(risk_percentage)
            except (ValueError, TypeError):
                risk_percentage = 0
        if risk_percentage < 0 or risk_percentage > 100:
            yield emit({"type": "error", "message": f"Invalid risk_percentage: {risk_percentage}. Must be 0-100."})
            return

        if platform not in _VALID_PLATFORMS:
            yield emit({"type": "error", "message": f"Invalid platform: {platform}. Must be one of {sorted(_VALID_PLATFORMS)}."})
            return

        if market not in _VALID_MARKETS:
            yield emit({"type": "error", "message": f"Invalid market: {market}. Must be one of {sorted(_VALID_MARKETS)}."})
            return

        # -- Step 1: Triage (pure logic, no AI calls) ----------------------
        localization_plan = result_json.get("localization_plan", "")
        from jusads_compliance.remix_agent.localization import plan_localization
        language_compliance = result_json.get("language_compliance") or {}
        localization = plan_localization(
            market=market,
            ethnicity=ethnicity,
            age_group=age_group,
            platform=platform,
            required_language=language_compliance.get("required_language", "") if isinstance(language_compliance, dict) else "",
            localization_plan=localization_plan,
        )
        localization_plan = (
            f"{localization_plan}\nRequired generated copy language: {localization['output_language']}. "
            f"Required script: {localization['required_script']}. Tone: {localization['tone']}."
        )
        segmentation = result_json.get("segmentation")
        localization_assessment = result_json.get("localization_assessment") or {}
        localization_priority = (
            localization_assessment.get("priority", "")
            if isinstance(localization_assessment, dict)
            else ""
        )
        cultural_fit_score = result_json.get("cultural_fit_score")
        try:
            localization_needs_adaptation = localization_priority in {"moderate", "high"} or int(cultural_fit_score) < 70
        except (TypeError, ValueError):
            localization_needs_adaptation = localization_priority in {"moderate", "high"}

        triage = triage_decide(
            risk_percentage=risk_percentage,
            violations=violations,
            segmentation=segmentation,
            localization_plan=localization_plan,
            platform=platform,
            market=market,
            confidence=result_json.get("overall_confidence", "high"),
            localization_needs_adaptation=localization_needs_adaptation,
        )

        logger.info("[Remix] Triage: %s — %s", triage["outcome"], triage["reasoning"])

        # -- COMPLIANT path ------------------------------------------------
        if triage["outcome"] == TriageOutcome.COMPLIANT:
            yield emit({"type": "compliant", "message": "Image passes compliance — no fix needed"})
            yield {"type": "compliant", "message": "No remix needed"}
            return

        # -- CANNOT_FIX path -----------------------------------------------
        if triage["outcome"] == TriageOutcome.CANNOT_FIX:
            yield emit({
                "type": "cannot_fix",
                "guidance": triage["guidance"],
                "reasoning": triage["reasoning"],
                "redirect_to_frontend": True,
                "violations": violations,
            })
            yield {
                "type": "cannot_fix",
                "guidance": triage["guidance"],
                "redirect_to_frontend": True,
                "violations": violations,
                "reasoning": triage["reasoning"],
            }
            return

        # -- EDIT path -----------------------------------------------------

        # Step 2: AI Designer plans the edit
        yield emit({"type": "node_status", "node": "plan_edit", "status": "running",
                    "description": "Planning edit strategy..."})

        edit_plan = await plan_edit(
            violations=violations,
            localization_plan=localization_plan,
            platform=platform,
            market=market,
            ethnicity=ethnicity,
            age_group=age_group,
            segmentation=segmentation,
        )

        yield emit({"type": "node_status", "node": "plan_edit", "status": "completed",
                    "description": f"Mode: {edit_plan['mode']}"})

        # Step 3: Execute edit via edit_image tool
        yield emit({"type": "node_status", "node": "edit_image", "status": "running",
                    "description": "Editing image with AI..."})

        from jusads_compliance.remix_tools import edit_image

        edit_result = edit_image.invoke({
            "project_id": str(check.get("project_id", "default")),
            "task_id": task_id,
            "violations": violations,
            "market": market,
            "platform": platform,
            "ethnicity": ethnicity,
            "age_group": age_group,
            "localization_plan": localization_plan,
            "feedback": edit_plan.get("inpaint_prompt", ""),
        })

        if "error" not in edit_result:
            output_path = edit_result.get("output_path", "")
            quality_score = edit_result.get("quality_score", 0)

            # The route owns publishing/persistence so every media type enters
            # the same private, versioned remediation state machine.  Do not
            # reuse an agent-provided URL: it may be public and it cannot prove
            # that a durable private asset was recorded.
            if not output_path or not os.path.isfile(output_path):
                yield {
                    "type": "edit_failed",
                    "fallback_guidance": "The edited image could not be persisted safely.",
                    "error": "Image remediation did not produce a local output file.",
                }
                return

            # Step 4: Lightweight bias check (non-blocking)
            bias_check = None
            if output_path:
                try:
                    from jusads_compliance.remix_tools import check_edit_bias
                    # Get original image path for comparison
                    original_url = check.get("s3_upload_key", "")
                    if original_url:
                        import urllib.request
                        import tempfile
                        original_path = os.path.join(tempfile.gettempdir(), f"bias_orig_{task_id}.png")
                        urllib.request.urlretrieve(original_url, original_path)
                        bias_check = check_edit_bias(original_path, output_path, violations)
                except Exception as e:
                    logger.warning("[Remix] Bias check failed (non-blocking): %s", e)

            yield emit({"type": "node_status", "node": "edit_image", "status": "completed",
                        "description": f"Edit complete — quality: {quality_score}/100"})

            # Build the final result — never include S3 keys or local paths
            image_edit_event = {
                "type": "image_edit",
                # Consumed by remix_compliance before the terminal SSE event;
                # never expose a filesystem path or S3 key to the browser.
                "image_output_path": output_path,
                "quality_score": quality_score,
                "edit_mode": edit_result.get("edit_mode", ""),
                "localization_verified": edit_result.get("localization_verified", True),
                "required_language": edit_result.get("required_language", ""),
                "localized_copy_actions": edit_result.get("localized_copy_actions", []),
            }
            if bias_check:
                image_edit_event["bias_check"] = {
                    "passed": bias_check.get("passed", True),
                    "issues": bias_check.get("issues", []),
                }

            yield image_edit_event

        else:
            # All edit attempts failed
            yield emit({"type": "node_status", "node": "edit_image", "status": "failed",
                        "description": "Edit failed after all attempts"})

            yield {
                "type": "edit_failed",
                "fallback_guidance": triage["guidance"] or "Consider manual editing or recreating the image",
                "error": edit_result.get("error", "Unknown error"),
            }

    except Exception as e:
        logger.error("[Remix] Unhandled error for %s: %s", task_id, e, exc_info=True)
        yield emit({"type": "error", "message": "An unexpected error occurred during image remix. Please try again."})
