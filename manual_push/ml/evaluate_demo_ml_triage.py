"""Evaluate the synthetic advisory triage fixture; never use production data."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from jusads_compliance.ml_triage_advisory import classify_text


def main() -> None:
    dataset = PROJECT_ROOT / "manual_push" / "data" / "demo_ml_triage_dataset.jsonl"
    rows = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line]
    correct = sum(classify_text(row["text"]).label == row["label"] for row in rows)
    print(json.dumps({
        "dataset": "synthetic demo fixture only",
        "rows": len(rows),
        "demo_fixture_accuracy": round(correct / len(rows), 4) if rows else None,
        "warning": "Not production accuracy; do not use for compliance decisions.",
    }))


if __name__ == "__main__":
    main()
