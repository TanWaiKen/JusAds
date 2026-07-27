# Evaluation protocol

Evaluate only on a held-out, approved, representative dataset. Split by source
and time to prevent leakage; keep a final untouched test set. Report results by
policy category, language, market, media type, and confidence band.

Minimum reported measures:

- precision, recall, F1, and false-negative rate (especially for risky content);
- calibration (reliability curve, Brier score, and threshold behaviour);
- abstention/escalation rate and human-review agreement;
- drift: input distribution, outcome/label, and calibration drift over time;
- median/p95 latency, availability, token/compute cost, and operational error rate;
- comparison to the existing authoritative workflow, including all regressions.

Do not infer production quality from the six-row synthetic POC fixture. A model
that looks accurate overall but has unacceptable false negatives in a required
slice fails the evaluation.
