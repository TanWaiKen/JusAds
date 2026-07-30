# Database schema review — 2026-07-26

## Final ERD ownership path

```text
users (email)
  └─ projects (owner_email)
       ├─ project_members
       ├─ tasks
       │   ├─ compliance_checks
       │   │   ├─ violations
       │   │   └─ remediation_versions
       │   │        ├─ compliance_evaluations
       │   │        └─ remediation_recheck_jobs
       │   ├─ chat_messages
       │   └─ generated_ads
       ├─ storyboard_scenes
       └─ brand_voices
```

`owner_email` remains for compatibility with the verified Cognito identity
layer. It must not be accepted from an API client as an authorization decision.

## Media-key contract

All media columns with an `s3` / `asset` / `clip` key now store only an object
key, never a URL. The relevant fields are in `business_profiles`,
`compliance_checks`, `violations`, `storyboard_scenes`, `generated_ads`,
`brand_voices`, and `remediation_versions`. The backend creates authorized,
short-lived URLs at response time.

`027_private_media_key_canonicalization.sql` normalizes legacy URLs and adds
database constraints. It detects the columns present in the target deployment,
so deployments where the storyboard fields are absent from `generated_ads` do
not fail.

## Retired from new installations

- `remediation_logs`: superseded by immutable `remediation_versions` plus
  append-only `compliance_evaluations`. No current application reads or writes
  it.
- `post_statistics_cache`: no current repository consumer. It is excluded from
  the bootstrap schema, not dropped from existing installations.
- `brand_voices.sample_url`: superseded by `sample_s3_key`; retain the existing
  column only until all historical rows and clients have moved.

## Deliberately not dropped automatically

Removing a populated production table/column is irreversible and cannot be
validated from source code alone. Archive and verify row counts before any
destructive cleanup. The safe order is: stop writes, export/archive, run the
private-media audit view, confirm zero application reads for a release cycle,
then issue a separately approved `DROP` migration.

## Live database validation — 2026-07-26

Read-only validation of the configured Supabase project found:

| Table | Rows | Repository evidence | Decision |
| --- | ---: | --- | --- |
| `remediation_logs` | 0 | No active read/write path; superseded by the immutable remediation state machine. | **Removal candidate** after approved archive/export and release-cycle verification. |
| `post_statistics_cache` | 0 | No active runtime consumer; already excluded from `full_schema.sql`. | **Removal candidate** after approved archive/export. |
| `tavily_usage_log` | 402 | Actively written by `shared/tavily_guard.py` for search-cost monitoring. | **Keep**; add a retention/archive policy rather than dropping it. |
| `violations` | 0 | Active create/read code remains in `shared/supabase_client.py`. | **Keep**; zero rows are not proof of retirement. |
| Remediation recheck tables | 0 | Current lifecycle tables for future/next remediation runs. | **Keep**. |
| `youtube_hook_reference_cache` | 0 | New authenticated 24-hour YouTube-reference cache. | **Keep**; it has not been invoked yet. |

No drop or truncate action was executed. Existing presentation data remains
unchanged. The separate Supabase security advisor also reports older public
tables with RLS disabled; do not enable RLS in bulk without matching policies,
because that would disrupt the existing application.

## Remaining design debt to schedule

1. Replace email ownership keys with an immutable Cognito `subject` foreign-key
   model. Email can change and is personal data; the subject is the stable key.
2. Move `users.zernio_api_key` to a secrets manager or application encryption
   envelope. It is actively used, so it was not removed.
3. Resolve historical migration-number collisions (`020_*` and `021_*`). The
   bootstrap file is now the source of truth for new environments; existing
   migration history should be reconciled before creating more numbered files.
