# Langhub security, API contract, and frontend architecture hardening

## Purpose

This delivery is the authoritative implementation brief for completing the P0–P2 remediation discovered during the 30 July 2026 API audit. It is deliberately specific: the project must become safe to demonstrate, understandable to maintain, and testable without relying on undocumented behaviour.

## Scope

### P0 — tenant security and ownership

Every user-facing route must require a Cognito bearer token unless it is one of the three operational probes: `/health`, `/api/health`, or `/api/ready`.

- Derive the caller from `Principal = Depends(get_current_principal)`.
- For every `project_id`, use `require_project_access(store, project_id, principal)` before reading. Use `write=True` before creating, changing, publishing, distributing, generating, or deleting.
- Do not use body/query `owner_email`, `user_email`, or `username` to make an authorization decision. Derive identity from `principal.email`.
- For a task, compliance check, ad, asset, or remediation version, resolve its authoritative project and validate access before returning data or changing state.
- Never return raw exceptions to the browser. Log internal detail; return stable user-safe error codes/messages.

The priority routes are: all `/api/files/*` signed URL routes; generation chat, history, plan execution, generated ads, Easy results, and publish routes; trends/signals/research; assets; prompt recommendations; and all project-scoped reads/writes.

### P1 — broken and misleading product behaviour

- Remove or replace frontend calls to the nonexistent task-upload route `/api/projects/{projectId}/tasks/{taskId}/upload`. Use the authorized files service instead.
- Invalid/inaccessible project IDs must produce the intentional 404 response from authorization, not a 500 error.
- Swagger must show bearer security for protected routes and document meaningful error responses.
- Preserve the manual-only PredictHQ endpoint as a documented `410 Gone`; do not re-enable paid live sync from the UI.

### P2 — maintainable frontend integration

The frontend must use domain boundaries rather than direct `fetch()` inside pages/components.

```text
src/
  services/  accountService projectService generationService complianceService
             trendsService distributionService mediaService analyticsService
  models/    account project generation compliance trends distribution media analytics
  features/  trends generation compliance distribution
```

This does **not** mean one service/model per endpoint. A service owns one business domain; its matching model owns that domain's request/response types. Existing `*Api.ts` modules may remain as temporary compatibility exports while callers migrate.

## Non-negotiable constraints

- Do not push, commit, delete user data, delete migrations/manual backups/manual-push scripts, or alter Supabase data during this work.
- Do not run paid AI, PredictHQ, YouTube, Zernio publishing, upload, delete, or distribution actions as tests.
- Do not save or print bearer tokens, API keys, `.env` contents, or presigned URLs.
- Preserve unrelated dirty-worktree changes.

## Definition of done

1. Anonymous requests to every protected route return `401`.
2. Authenticated user can access their own project, but a synthetic/invalid project ID returns controlled `404` rather than data or `500`.
3. All P0 sources derive identity server-side and enforce project scope.
4. No component/page constructs an internal API URL, adds auth headers, or parses backend transport errors directly.
5. `npm.cmd run build` passes.
6. Focused backend tests pass once the valid Python interpreter is restored; until then, report this as an external environment blocker, not as a passing test.
7. Swagger and this delivery log accurately distinguish implemented, verified, and pending work.
