from __future__ import annotations

from dataclasses import dataclass

import pytest

from jusads_compliance.remediation_store import (
    InvalidRemediationTransition,
    RemediationStatus,
    RemediationStore,
    status_from_evaluation,
    validate_transition,
)


@dataclass
class _Response:
    data: object


class _Rpc:
    def __init__(self, response):
        self.response = response

    def execute(self):
        return _Response(self.response)


class _Client:
    def __init__(self):
        self.calls = []
        self.responses = {}

    def rpc(self, name, params):
        self.calls.append((name, params))
        return _Rpc(self.responses.get(name, {"id": "record-1"}))


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("queued", "processing"),
        ("processing", "pending_recheck"),
        ("pending_recheck", "rechecking"),
        ("rechecking", "verified_compliant"),
        ("rechecking", "verified_non_compliant"),
        ("rechecking", "recheck_error"),
    ],
)
def test_valid_authoritative_transitions(current, target):
    validate_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("processing", "verified_compliant"),
        ("pending_recheck", "verified_compliant"),
        ("verified_non_compliant", "verified_compliant"),
        ("generation_failed", "pending_recheck"),
    ],
)
def test_compliance_cannot_be_promoted_without_recheck(current, target):
    with pytest.raises(InvalidRemediationTransition):
        validate_transition(current, target)


def test_failed_or_error_recheck_never_maps_to_compliant():
    assert status_from_evaluation("failed", "accepted") is RemediationStatus.VERIFIED_NON_COMPLIANT
    assert status_from_evaluation("passed", "rejected") is RemediationStatus.VERIFIED_NON_COMPLIANT
    assert status_from_evaluation("error", None) is RemediationStatus.RECHECK_ERROR


def test_only_passing_compliant_verdict_maps_to_verified_compliant():
    assert status_from_evaluation("passed", "accepted") is RemediationStatus.VERIFIED_COMPLIANT
    assert status_from_evaluation("passed", "compliant") is RemediationStatus.VERIFIED_COMPLIANT


def test_store_begin_uses_idempotent_transaction_rpc():
    client = _Client()
    client.responses["begin_remediation_version"] = [{"id": "version-1", "status": "processing"}]
    store = RemediationStore(client)

    record = store.begin_version(
        task_id="task-1",
        idempotency_key="request-123",
        media_type="image",
        source_asset_key="uploads/sub-1/task-1/source.png",
        created_by_subject="sub-1",
    )

    assert record["id"] == "version-1"
    name, params = client.calls[0]
    assert name == "begin_remediation_version"
    assert params["p_idempotency_key"] == "request-123"
    assert params["p_created_by_subject"] == "sub-1"


def test_generated_asset_is_private_and_enqueues_recheck_via_rpc():
    client = _Client()
    store = RemediationStore(client)
    record = store.mark_generated(
        version_id="version-1",
        asset_key="remediations/sub-1/task-1/v1/output.png",
        asset_sha256="a" * 64,
        asset_size_bytes=42,
        content_type="image/png",
    )
    assert record["id"] == "record-1"
    name, params = client.calls[0]
    assert name == "finalize_remediation_version"
    assert params["p_asset_key"].startswith("remediations/")
    assert "url" not in params["p_asset_key"]


@pytest.mark.parametrize("bad_key", ["https://bucket.example/output.png", ""])
def test_generated_asset_rejects_url_or_empty_key(bad_key):
    with pytest.raises(ValueError):
        RemediationStore(_Client()).mark_generated(
            version_id="version-1",
            asset_key=bad_key,
            asset_sha256="a" * 64,
            asset_size_bytes=42,
        )


def test_generated_asset_rejects_non_hex_digest():
    with pytest.raises(ValueError):
        RemediationStore(_Client()).mark_generated(
            version_id="version-1",
            asset_key="private/remixed/sub/task/output.png",
            asset_sha256="z" * 64,
            asset_size_bytes=42,
        )


def test_evaluation_rpc_receives_server_checked_target_status():
    client = _Client()
    store = RemediationStore(client)
    store.record_evaluation(
        version_id="version-1",
        idempotency_key="eval-1",
        evaluation_status="failed",
        verdict="rejected",
        result={"risk_percentage": 90},
        policy_version="policy-2026-07",
        rule_version="rules-sha",
        risk_percentage=90,
    )
    name, params = client.calls[0]
    assert name == "record_remediation_evaluation"
    assert params["p_target_version_status"] == "verified_non_compliant"
    assert params["p_policy_version"] == "policy-2026-07"
