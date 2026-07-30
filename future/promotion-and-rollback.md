# Model promotion and rollback criteria

Promotion requires written approval from product, compliance/policy, security,
and data governance owners. The approval must specify intended scope, metrics,
thresholds, human escalation, monitoring owner, release version, and rollback
owner.

Before promotion, the candidate must meet pre-registered thresholds for
precision, recall, false-negative rate, calibration, latency, cost, privacy,
and relevant subgroup slices without degrading the authoritative workflow.
Launch with a feature flag, bounded cohort, versioned output, and shadow or
advisory mode first. A model cannot make a final compliance decision unless a
separate policy decision authorises that change.

Immediately roll back to the authoritative workflow if there is an unsafe
false-negative pattern, material calibration/drift breach, security/privacy
incident, outage, unexplained metric regression, or monitoring gap. Preserve
the model version, inputs allowed by retention policy, outputs, and incident
record for audit; do not silently rewrite historical decisions.
