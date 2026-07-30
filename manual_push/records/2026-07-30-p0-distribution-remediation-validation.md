# P0 distribution and remediation validation

Date: 2026-07-30

| Priority | Item | Result | Evidence |
| --- | --- | --- | --- |
| P0 | Distribution project authorization | Verified existing | `require_project_access` is mandatory before a generated ad can be distributed; focused authorization tests pass. |
| P0 | User-scoped Zernio connection | Implemented | Profile key endpoints now derive the owner from a verified Cognito principal; no client email parameter remains. |
| P0 | Platform-account mapping | Verified existing | Campaign results fetches `/api/distribution/accounts` with an ID token and sends selected `{ platform, account_id }` destinations. |
| P0 | Mandatory remediation recheck | Implemented | `remediation_recheck_worker` claims a durable job, downloads the private asset, runs the real compliance graph, and appends an immutable evaluation. |
| P0 | Concurrent worker safety | Applied | Supabase migration `remediation_recheck_worker_claim` uses `FOR UPDATE SKIP LOCKED`; live empty-queue dry run returned `0` claimed jobs. |
| P0 | Direct Supabase exposure | Applied | RLS enabled and anon/authenticated grants revoked on all previously flagged public application tables. |

## Automated checks

- `33 passed` — remediation state machine, recheck worker, and Cognito/project authorization tests.
- `tsc --noEmit -p frontend/tsconfig.json` — passed.
- `eslint frontend/src/pages/trends.tsx` — passed.
- `vite build` — passed; it retains the existing large-chunk warning (1.05 MB JS, 309 KB gzip).

## Remaining operational requirement

The API starts the recheck loop by default. Set `REMEDIATION_RECHECK_WORKER_ENABLED=false` only when a separately deployed worker process is responsible for it.

## Explicit security limitation to address next

The Zernio API key is now owner-scoped and inaccessible through PostgREST, but the backend currently stores it as plaintext. Before production use, add envelope encryption backed by a managed KMS or secret manager; do not derive an encryption key from the Supabase key.
