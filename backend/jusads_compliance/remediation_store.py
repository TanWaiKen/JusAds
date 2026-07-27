"""Durable, versioned remediation persistence.

The remediation asset lifecycle is deliberately separate from the original
compliance check.  Producing an edited asset is not proof of compliance: every
version must pass through ``pending_recheck`` and receive an immutable
evaluation before it can become ``verified_compliant``.

All mutating methods call database RPCs supplied by migration 026.  Keeping the
transaction boundaries in Postgres makes retries and concurrent requests safe,
while this small wrapper remains straightforward to mock in unit tests.
"""

from __future__ import annotations

from enum import Enum
import re
from typing import Any, Mapping


class InvalidRemediationTransition(ValueError):
    """Raised when code attempts to skip a required lifecycle state."""


class RemediationStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    PENDING_RECHECK = "pending_recheck"
    RECHECKING = "rechecking"
    VERIFIED_COMPLIANT = "verified_compliant"
    VERIFIED_NON_COMPLIANT = "verified_non_compliant"
    GENERATION_FAILED = "generation_failed"
    RECHECK_ERROR = "recheck_error"
    CANCELLED = "cancelled"


TERMINAL_REMEDIATION_STATUSES = frozenset(
    {
        RemediationStatus.VERIFIED_COMPLIANT,
        RemediationStatus.VERIFIED_NON_COMPLIANT,
        RemediationStatus.GENERATION_FAILED,
        RemediationStatus.RECHECK_ERROR,
        RemediationStatus.CANCELLED,
    }
)

_ALLOWED_TRANSITIONS: Mapping[RemediationStatus, frozenset[RemediationStatus]] = {
    RemediationStatus.QUEUED: frozenset(
        {
            RemediationStatus.PROCESSING,
            RemediationStatus.GENERATION_FAILED,
            RemediationStatus.CANCELLED,
        }
    ),
    RemediationStatus.PROCESSING: frozenset(
        {
            RemediationStatus.PENDING_RECHECK,
            RemediationStatus.GENERATION_FAILED,
            RemediationStatus.CANCELLED,
        }
    ),
    RemediationStatus.PENDING_RECHECK: frozenset(
        {RemediationStatus.RECHECKING, RemediationStatus.CANCELLED}
    ),
    RemediationStatus.RECHECKING: frozenset(
        {
            RemediationStatus.VERIFIED_COMPLIANT,
            RemediationStatus.VERIFIED_NON_COMPLIANT,
            RemediationStatus.RECHECK_ERROR,
            RemediationStatus.CANCELLED,
        }
    ),
    **{status: frozenset() for status in TERMINAL_REMEDIATION_STATUSES},
}


def validate_transition(current: str | RemediationStatus, target: str | RemediationStatus) -> None:
    """Validate one authoritative remediation state transition."""

    try:
        current_status = RemediationStatus(current)
        target_status = RemediationStatus(target)
    except ValueError as exc:
        raise InvalidRemediationTransition(f"Unknown remediation state: {exc}") from exc
    if target_status not in _ALLOWED_TRANSITIONS[current_status]:
        raise InvalidRemediationTransition(
            f"Invalid remediation transition: {current_status.value} -> {target_status.value}"
        )


def status_from_evaluation(evaluation_status: str, verdict: str | None = None) -> RemediationStatus:
    """Map a terminal evaluation record to the only legal version outcome."""

    normalized_status = (evaluation_status or "").strip().lower()
    normalized_verdict = (verdict or "").strip().lower().replace("-", "_")
    if normalized_status == "error":
        return RemediationStatus.RECHECK_ERROR
    if normalized_status == "passed" and normalized_verdict in {
        "accepted",
        "compliant",
        "pass",
        "verified_compliant",
    }:
        return RemediationStatus.VERIFIED_COMPLIANT
    if normalized_status in {"passed", "failed"}:
        return RemediationStatus.VERIFIED_NON_COMPLIANT
    raise ValueError(f"Evaluation is not terminal: {evaluation_status!r}")


def _one(data: Any) -> dict[str, Any]:
    if isinstance(data, list):
        if not data:
            raise RuntimeError("Persistence operation returned no record")
        data = data[0]
    if not isinstance(data, dict):
        raise RuntimeError("Persistence operation returned an invalid record")
    return data


class RemediationStore:
    """Transaction-backed remediation version repository."""

    def __init__(self, client: Any):
        if client is None:
            raise ValueError("A database client is required")
        self.client = client

    def begin_version(
        self,
        *,
        task_id: str,
        idempotency_key: str,
        media_type: str,
        source_asset_key: str | None,
        created_by_subject: str,
        parent_version_id: str | None = None,
        agent_strategy: str = "",
        policy_version: str = "",
        rule_version: str = "",
        model_provider: str = "",
        model_name: str = "",
        model_version: str = "",
        prompt_template_version: str = "",
        prompt_inputs: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create or return one processing version for an idempotency key."""

        if not idempotency_key.strip():
            raise ValueError("idempotency_key is required")
        response = self.client.rpc(
            "begin_remediation_version",
            {
                "p_task_id": task_id,
                "p_idempotency_key": idempotency_key,
                "p_media_type": media_type,
                "p_source_asset_key": source_asset_key,
                "p_created_by_subject": created_by_subject,
                "p_parent_version_id": parent_version_id,
                "p_agent_strategy": agent_strategy,
                "p_policy_version": policy_version,
                "p_rule_version": rule_version,
                "p_model_provider": model_provider,
                "p_model_name": model_name,
                "p_model_version": model_version,
                "p_prompt_template_version": prompt_template_version,
                "p_prompt_inputs": dict(prompt_inputs or {}),
            },
        ).execute()
        return _one(response.data)

    def mark_generated(
        self,
        *,
        version_id: str,
        asset_key: str,
        asset_sha256: str,
        asset_size_bytes: int,
        content_type: str | None = None,
        generation_metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Atomically publish metadata and enqueue the mandatory recheck."""

        if not asset_key or "://" in asset_key:
            raise ValueError("asset_key must be a private object key, not a URL")
        if not re.fullmatch(r"[0-9a-fA-F]{64}", asset_sha256 or ""):
            raise ValueError("asset_sha256 must be a hexadecimal SHA-256 digest")
        response = self.client.rpc(
            "finalize_remediation_version",
            {
                "p_version_id": version_id,
                "p_asset_key": asset_key,
                "p_asset_sha256": asset_sha256.lower(),
                "p_asset_size_bytes": asset_size_bytes,
                "p_content_type": content_type,
                "p_generation_metadata": dict(generation_metadata or {}),
            },
        ).execute()
        return _one(response.data)

    def mark_recheck_started(self, *, version_id: str) -> dict[str, Any]:
        response = self.client.rpc(
            "start_remediation_recheck", {"p_version_id": version_id}
        ).execute()
        return _one(response.data)

    def record_evaluation(
        self,
        *,
        version_id: str,
        idempotency_key: str,
        evaluation_status: str,
        verdict: str | None,
        result: Mapping[str, Any] | None,
        policy_version: str,
        rule_version: str,
        model_provider: str = "",
        model_name: str = "",
        model_version: str = "",
        risk_percentage: float | None = None,
        error_code: str | None = None,
    ) -> dict[str, Any]:
        """Append a terminal recheck and atomically update the version state."""

        target = status_from_evaluation(evaluation_status, verdict)
        response = self.client.rpc(
            "record_remediation_evaluation",
            {
                "p_version_id": version_id,
                "p_idempotency_key": idempotency_key,
                "p_evaluation_status": evaluation_status,
                "p_verdict": verdict,
                "p_result_json": dict(result or {}),
                "p_policy_version": policy_version,
                "p_rule_version": rule_version,
                "p_model_provider": model_provider,
                "p_model_name": model_name,
                "p_model_version": model_version,
                "p_risk_percentage": risk_percentage,
                "p_error_code": error_code,
                "p_target_version_status": target.value,
            },
        ).execute()
        return _one(response.data)

    def mark_generation_failed(self, *, version_id: str, error_code: str) -> dict[str, Any]:
        response = self.client.rpc(
            "fail_remediation_version",
            {"p_version_id": version_id, "p_error_code": error_code},
        ).execute()
        return _one(response.data)
