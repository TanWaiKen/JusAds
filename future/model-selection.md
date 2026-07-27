# Model-selection guideline

Use the simplest model that meets a pre-registered evaluation target. A future
model may assist prioritisation or reviewer workflows, but must not replace the
authoritative rules, primary LLM assessment, human escalation, or remediation
recheck workflow without an explicit approved product and policy change.

Candidate order:

1. Transparent rule or linear baseline for a narrow, stable text signal.
2. Calibrated classifier with versioned features and explainability when it
   materially improves validated recall/precision.
3. Larger language or multimodal model only when the measured improvement
   justifies privacy, latency, cost, and auditability tradeoffs.

Every candidate needs a versioned input contract, documented intended use,
known failure modes, data lineage, language/market coverage, fallback
behaviour, and a deterministic way to disable it. The synthetic keyword POC is
not a candidate for production selection.
