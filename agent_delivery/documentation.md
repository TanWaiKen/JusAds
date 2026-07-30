# Live audit and implementation log

## Baseline audit — 2026-07-30

### Verified working with an authenticated local session

- Health/readiness, profile/onboarding, projects, statistics, hook tags, trends, events, signals, Zernio connection, and user assets returned `200`.
- The combined research UI had previously refreshed generic TikTok/Instagram research and cached YouTube/Reels hook references successfully.
- Frontend production build passes after removal of two unused Easy Generation TypeScript declarations.

### Verified security failures before remediation

- `GET /api/trends`, `/api/trends/events`, `/api/trends/signals`, `/api/user-assets`, and `/api/prompt-recommendations` returned `200` without a bearer token.
- `GET /api/projects/{invalid}/easy-results` returned `500`, not a controlled authorization/not-found response.
- File signing routes trusted client-supplied identity/project values.
- Several task generation routes had neither JWT dependency nor project authorization.
- Swagger listed 61 method/path entries, including duplicate slash aliases and routes whose security metadata did not match the intended product policy.

### Frontend architecture findings

Existing services are useful but inconsistent: `complianceApi`, `generationApi`, `taskApi`, `trendsApi`, `fileService`, `hookSearchApi`, and `statisticsApi` exist. Direct internal calls still appear in Profile, Assets, Easy Generation, prompt-search components, ChatbotPanel, InspectorPanel, and OutputGallery. ChatbotPanel and InspectorPanel reference an unimplemented task-upload route.

## Current implementation state

Only mark an item “verified” after its anonymous rejection, authenticated safe read, and frontend build are observed. Source edits alone are **not** proof.

| Area | Current state | Verification state |
|---|---|---|
| Generation chat | JWT/project write check added | Needs regression test |
| Generated ad retrieval | JWT/project read check added | Needs regression test |
| Easy results | JWT/project read check added | Needs invalid-ID test |
| All other P0/P1/P2 items | Not yet complete | Pending |
| Frontend build | Passed | Verified |
| Backend pytest | Cannot start because `.venv` base interpreter is invalid | Externally blocked |

## Verified regression â€” 2026-07-30

Anonymous requests to `GET /api/trends`, `GET /api/trends/signals`, `GET /api/user-assets`, `GET /api/prompt-recommendations`, and `GET /api/search-prompt` each returned `401`. This verifies the bearer dependency for that P0 group; authenticated safe-read regression remains part of final verification.

## Verified backend hardening — 2026-07-30

- `POST /api/files/download-url` now requires bearer authentication, verified project-read access, a `project_id`, and an S3 key within that project/user's allowed prefix. The route no longer signs arbitrary client-supplied keys.
- `POST /api/files/upload-url` and `POST /api/files/upload-complete` derive object scope from the verified Cognito subject. They no longer accept a `username`, and completion rejects a key outside the caller's project/reference prefix.
- `POST /api/projects/{project_id}/tasks/{task_id}/execute-video-plan`, `GET .../generated-ads`, `GET .../easy-results`, `GET .../chat-history`, and `POST .../ads/{ad_id}/publish` now require bearer authentication and project access. Publish verifies that the ad belongs to the requested task before changing state.
- `POST /api/generation/autofill` now requires bearer authentication, preventing anonymous AI-cost abuse.
- Generation SSE errors, generated-ad retrieval, Easy Results, publishing, assets, and distribution return stable user-safe messages rather than raw exception strings.
- Anonymous validation returned `401` for generated ads, Easy Results, chat history, scoped download signing, autofill, execute-video-plan, publish, all file upload/download signing routes, and asset download signing. OpenAPI documents bearer security for execute-video-plan, generated ads, Easy Results, chat history, publish, scoped download signing, and autofill.

Not yet verified: an authenticated permitted project read and an authenticated invalid-project `404`. Those require a valid bearer token and must not invoke generation, S3 upload, or publishing.

## Frontend integration update — 2026-07-30

- Added the requested domain boundaries under `frontend/src/models` and `frontend/src/services`: account, project, generation, compliance, trends, distribution, media, and analytics.
- Profile uses `accountService`; prompt search and recommendations use authenticated `mediaService`; Home and New Project use `projectService`; Easy Generation uses `generationService` for autofill and the signed file service for references.
- Removed the nonexistent `/api/projects/{projectId}/tasks/{taskId}/upload` browser calls. ChatbotPanel and InspectorPanel now upload through `mediaService`, which delegates to the authorized signed-URL flow.
- Removed the client `username` field from the shared upload service request. The backend is now the source of identity.
- The low-level signed-download helper now requires `projectId` and sends it with the S3 key; it has no current UI caller, so no unauthorised download request can be made by the frontend.
- `npm.cmd run build` passed after this migration. The large bundle warning (about 1.04 MB JavaScript) is a P2 optimisation concern, not a failure.

The frontend migration is **not** complete until remaining direct authenticated calls in DashboardShell, Onboarding, Sidebar, Project Overview, Compliance, and Output Gallery are moved behind their matching services.

## Do not misrepresent

This folder is a delivery control document, not proof that the full remediation is complete. The project is not ready for final release until every plan row has evidence and the backend test environment is restored.

## Project sharing enhancement â€” 2026-07-30

- Added owner-only `GET /api/projects/{project_id}/members` and `DELETE /api/projects/{project_id}/members/{member_email}` endpoints beside the existing share endpoint.
- The Share dialog now lists invited members and allows the owner to revoke access. Ownership remains on the project record and is not removable through this member-management route.
- Frontend production build and `projects.py` syntax validation passed after the change.
