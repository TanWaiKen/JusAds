"""Durable worker for mandatory remediation compliance rechecks.

An edited asset is never proof of compliance.  This worker atomically claims a
queued recheck job, downloads the private remediated asset, runs the production
compliance graph, and records the terminal evaluation through the append-only
state-machine RPC.

Run as a separate process in production::

    python -m jusads_compliance.remediation_recheck_worker
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import tempfile
import time
from typing import Any

from config import S3_BUCKET_NAME
from shared.config import MODEL_TEXT
from shared.models import Compliance_State
from jusads_compliance.remediation_store import RemediationStore

logger = logging.getLogger(__name__)

WORKER_POLL_SECONDS = 15
DEFAULT_BATCH_SIZE = 2


def _one(data: Any, message: str) -> dict[str, Any]:
    if isinstance(data, list):
        data = data[0] if data else None
    if not isinstance(data, dict):
        raise RuntimeError(message)
    return data


def _claim_jobs(client: Any, limit: int) -> list[dict[str, Any]]:
    response = client.rpc("claim_remediation_recheck_jobs", {"p_limit": limit}).execute()
    return [row for row in (response.data or []) if isinstance(row, dict)]


def _load_check(client: Any, task_id: str) -> dict[str, Any]:
    response = (
        client.table("compliance_checks")
        .select("task_id, media_type, market, platform, ethnicity, age_group")
        .eq("task_id", task_id)
        .limit(1)
        .execute()
    )
    return _one(response.data, "Compliance check for remediation version was not found")


def _download_asset(s3_client: Any, asset_key: str) -> str:
    suffix = Path(asset_key).suffix or ".bin"
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    handle.close()
    try:
        s3_client.download_file(S3_BUCKET_NAME, asset_key, handle.name)
        return handle.name
    except Exception:
        try:
            os.unlink(handle.name)
        except FileNotFoundError:
            pass
        raise


def _run_pipeline(check: dict[str, Any], version: dict[str, Any], asset_path: str, attempt: int) -> dict[str, Any]:
    """Run the real graph without overwriting the original check's live result."""
    from jusads_compliance.compliance_pipeline import compliance_pipeline

    media_type = str(check.get("media_type") or version.get("media_type") or "")
    if media_type not in {"text", "image", "audio", "video"}:
        raise RuntimeError("Unsupported remediation media type")
    text_input = ""
    input_path = asset_path
    if media_type == "text":
        text_input = Path(asset_path).read_text(encoding="utf-8")
        input_path = ""
    state: Compliance_State = {
        "session_id": f"recheck-{version['id']}-{attempt}",
        "task_id": str(check["task_id"]),
        "media_type": media_type,
        "input_path": input_path,
        "text_input": text_input,
        "market": str(check.get("market") or "malaysia"),
        "platform": str(check.get("platform") or "general"),
        "ethnicity": str(check.get("ethnicity") or "all"),
        "age_group": str(check.get("age_group") or "all_ages"),
        "iteration": 0,
        "result": {},
        "status": "pending",
        "user_prompt_context": "",
        "remediated_path": "",
        "remix_iteration": 0,
        # The immutable compliance_evaluations row below is authoritative for
        # this run; do not let the normal graph overwrite the original check.
        "persist_result": False,
    }
    final: dict[str, Any] = {}
    config = {"configurable": {"thread_id": f"recheck:{version['id']}:{attempt}"}}
    for event in compliance_pipeline.stream(state, config=config, stream_mode="updates"):
        for output in event.values():
            if isinstance(output, dict):
                final.update(output)
    return final


def _record_error(store: RemediationStore, version: dict[str, Any], attempt: int, code: str) -> None:
    store.record_evaluation(
        version_id=str(version["id"]),
        idempotency_key=f"recheck:{version['id']}:{attempt}",
        evaluation_status="error",
        verdict=None,
        result={},
        policy_version=str(version.get("policy_version") or "unknown"),
        rule_version=str(version.get("rule_version") or "unknown"),
        model_provider="google",
        model_name=MODEL_TEXT,
        error_code=code,
    )


def _default_clients() -> tuple[Any, Any]:
    """Delay cloud-client construction so this module remains unit-testable."""
    from shared.clients import s3, supabase

    return supabase, s3


def process_job(job: dict[str, Any], *, client: Any | None = None, s3_client: Any | None = None) -> str:
    """Process one claimed job and return its terminal remediation status."""
    if client is None or s3_client is None:
        default_client, default_s3_client = _default_clients()
        client = client or default_client
        s3_client = s3_client or default_s3_client
    version = _one(job.get("version"), "Claimed recheck job has no remediation version")
    version_id = str(version["id"])
    attempt = int(job.get("attempt_count") or 1)
    store = RemediationStore(client)
    asset_path = ""
    try:
        store.mark_recheck_started(version_id=version_id)
        check = _load_check(client, str(version["task_id"]))
        asset_key = str(version.get("asset_key") or "")
        if not asset_key or "://" in asset_key:
            raise RuntimeError("Remediation asset key is missing or is not private")
        asset_path = _download_asset(s3_client, asset_key)
        final = _run_pipeline(check, version, asset_path, attempt)
        result = final.get("result") if isinstance(final.get("result"), dict) else {}
        verdict = result.get("compliance_verdict") if isinstance(result.get("compliance_verdict"), str) else None
        status = str(final.get("status") or "").lower()
        if status not in {"pass", "remediate", "critical_regen"} or not verdict:
            raise RuntimeError("Compliance recheck did not produce a terminal verdict")
        evaluation_status = "passed" if status == "pass" else "failed"
        store.record_evaluation(
            version_id=version_id,
            idempotency_key=f"recheck:{version_id}:{attempt}",
            evaluation_status=evaluation_status,
            verdict=verdict,
            result=result,
            policy_version=str(version.get("policy_version") or "unknown"),
            rule_version=str(version.get("rule_version") or "unknown"),
            model_provider="google",
            model_name=MODEL_TEXT,
            risk_percentage=float(result["risk_percentage"]) if isinstance(result.get("risk_percentage"), (int, float)) else None,
        )
        return "verified_compliant" if evaluation_status == "passed" and verdict == "accepted" else "verified_non_compliant"
    except Exception:
        logger.exception("[RemediationRecheck] Failed version_id=%s attempt=%s", version_id, attempt)
        try:
            _record_error(store, version, attempt, "RECHECK_EXECUTION_FAILED")
        except Exception:
            logger.exception("[RemediationRecheck] Could not persist failure version_id=%s", version_id)
        return "recheck_error"
    finally:
        if asset_path:
            try:
                os.unlink(asset_path)
            except FileNotFoundError:
                pass


def run_once(*, client: Any | None = None, s3_client: Any | None = None, limit: int = DEFAULT_BATCH_SIZE) -> list[str]:
    """Claim and process a bounded batch; safe for a cron or worker loop."""
    if client is None or s3_client is None:
        default_client, default_s3_client = _default_clients()
        client = client or default_client
        s3_client = s3_client or default_s3_client
    jobs = _claim_jobs(client, max(1, min(limit, 10)))
    return [process_job(job, client=client, s3_client=s3_client) for job in jobs]


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info("[RemediationRecheck] Worker started")
    while True:
        outcomes = run_once()
        if outcomes:
            logger.info("[RemediationRecheck] Completed %s", outcomes)
        time.sleep(WORKER_POLL_SECONDS)


if __name__ == "__main__":
    main()
