# Labelled feedback schema

The future feedback store should be separate from operational compliance
records. It must reference a minimised, access-controlled snapshot rather than
copying raw customer media by default.

Required fields:

| Field | Purpose |
| --- | --- |
| `feedback_id` | Immutable identifier. |
| `subject_reference` | Pseudonymous content reference with access scope. |
| `policy_version`, `rule_id` | Policy context at time of review. |
| `model_version`, `prediction`, `score` | Versioned advisory output. |
| `label`, `label_confidence` | Human-reviewed outcome and certainty. |
| `reviewer_role`, `reviewed_at` | Auditability without exposing reviewer identity broadly. |
| `market`, `language`, `media_type` | Evaluation slices. |
| `rationale_code` | Controlled explanation taxonomy. |
| `disposition` | accepted, corrected, abstained, or escalated. |
| `consent/data_lineage`, `retention_until` | Governance controls. |

Labels require double review or adjudication for high-impact categories. Store
append-only revisions; never overwrite the original label or prediction.
