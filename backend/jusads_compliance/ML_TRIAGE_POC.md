# Text risk triage ML proof of concept

This is a disabled-by-default, text-only advisory experiment. It uses a small
synthetic fixture and transparent weighted terms; it does **not** train on user
data, call an external model, or make a compliance/legal decision.

When `ML_TRIAGE_ADVISORY_ENABLED=true`, text compliance results include
`ml_triage_advisory`. The rules engine, primary LLM assessment, remediation
state machine, and automatic recheck remain authoritative. The advisory cannot
pass, fail, block, route, or publish any asset.

Run the fixture evaluation from `backend`:

```powershell
python manual_push/ml/evaluate_demo_ml_triage.py
```

Any printed metric is only accuracy on the six synthetic examples, not
production accuracy, legal accuracy, policy coverage, calibration, fairness, or
performance on customer content. Before a real learning layer, use approved
label governance, privacy review, representative evaluation, monitoring, and a
human-reviewed rollback plan.
