from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from jusads_compliance import remediation_recheck_worker as worker


@dataclass
class _Response:
    data: object


class _Rpc:
    def __init__(self, client, name, params):
        self.client = client
        self.name = name
        self.params = params

    def execute(self):
        self.client.calls.append((self.name, self.params))
        return _Response({"id": "evaluation-1"})


class _CheckQuery:
    def __init__(self, check):
        self.check = check

    def select(self, _fields): return self
    def eq(self, _field, _value): return self
    def limit(self, _limit): return self
    def execute(self): return _Response([self.check])


class _Client:
    def __init__(self):
        self.calls = []

    def rpc(self, name, params):
        return _Rpc(self, name, params)

    def table(self, _name):
        return _CheckQuery({
            "task_id": "task-1", "media_type": "text", "market": "malaysia",
            "platform": "instagram", "ethnicity": "all", "age_group": "all_ages",
        })


class _S3:
    def download_file(self, _bucket, _key, filename):
        Path(filename).write_text("A compliant rewritten advertisement", encoding="utf-8")


def _job():
    return {
        "id": "job-1", "attempt_count": 1,
        "version": {
            "id": "version-1", "task_id": "task-1", "media_type": "text",
            "asset_key": "private/remixed/user/project/task/remediated.txt",
            "policy_version": "policy-1", "rule_version": "rules-1",
        },
    }


def test_recheck_worker_records_actual_terminal_pipeline_result(monkeypatch):
    client = _Client()
    monkeypatch.setattr(worker, "_run_pipeline", lambda *_args: {
        "status": "pass",
        "result": {"compliance_verdict": "accepted", "risk_percentage": 12},
    })

    status = worker.process_job(_job(), client=client, s3_client=_S3())

    assert status == "verified_compliant"
    assert [call[0] for call in client.calls] == [
        "start_remediation_recheck", "record_remediation_evaluation",
    ]
    params = client.calls[-1][1]
    assert params["p_evaluation_status"] == "passed"
    assert params["p_verdict"] == "accepted"
    assert params["p_result_json"]["risk_percentage"] == 12


def test_recheck_worker_records_error_instead_of_promoting_on_pipeline_failure(monkeypatch):
    client = _Client()
    monkeypatch.setattr(worker, "_run_pipeline", lambda *_args: (_ for _ in ()).throw(RuntimeError("model unavailable")))

    status = worker.process_job(_job(), client=client, s3_client=_S3())

    assert status == "recheck_error"
    params = client.calls[-1][1]
    assert params["p_evaluation_status"] == "error"
    assert params["p_target_version_status"] == "recheck_error"
