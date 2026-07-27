# Future learning layer (planning only)

This directory contains specifications, not production training code. The
current text triage proof of concept is a synthetic-data demonstration only:
it is disabled by default, advisory-only, and has no authority over rules,
primary LLM assessments, remediation, rechecks, publishing, or compliance
status.

## Existing presentation data and authentication

Do not delete, reset, truncate, or overwrite existing Supabase presentation
data. In particular, do not add an unauthenticated or "fake account" login
bypass to expose historical records.

The supported compatibility approach is a one-time, admin-reviewed backfill:

1. The legacy owner signs in through Cognito with the same email address.
2. The backend accepts that identity only after verifying its ID token,
   issuer/client, and `email_verified=true` claim.
3. An administrator reviews the exact legacy `owner_email` records and maps
   them to the verified Cognito subject in a transactional migration/audit log.
4. Normal ownership checks then grant the mapped subject access. The migration
   does not change historical results or media, and cannot map arbitrary email
   claims without verification.

Remote integration tests must use a separately provisioned account/project and
uniquely prefixed test IDs. Before cleanup, enumerate and confirm the precise
rows and media keys created by that test; delete only those test-owned records.
Read-only inspection is preferred for existing presentation records.

See the focused specifications in this directory before proposing a production
learning system.
