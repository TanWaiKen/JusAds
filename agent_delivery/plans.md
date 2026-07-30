# Delivery plan and status board

| Priority | Work item | Evidence required | Status |
|---|---|---|---|
| P0 | Secure every files route | JWT, server-derived identity, project/asset ownership check, anonymous `401` | Code complete; authenticated safe-read still required |
| P0 | Secure task generation routes | JWT + `require_project_access`; read/write scope tested | Code complete; authenticated safe-read still required |
| P0 | Secure trends, signals, assets, and recommendations | No client-controlled identity; anonymous `401` | Verified 2026-07-30 |
| P0 | Remove raw backend error leakage | Stable error payloads and server-side logging | Implemented; syntax verification pending valid project interpreter |
| P1 | Remove nonexistent task-upload caller | Chatbot and Inspector use the authorised signed-upload media service; no task-upload caller remains | Implemented; build verified 2026-07-30 |
| P1 | Make project errors controlled | Invalid IDs return 404/403, never 500 | Invalid/inaccessible 404 observed; authorized safe-read pending fresh token |
| P1 | Swagger contract parity | Mounted routes, auth, request schemas, and responses match implementation | Security verified; response-schema review pending |
| P2 | Create domain model files | Eight requested domain models now exist | Implemented; build verified 2026-07-30 |
| P2 | Create/migrate domain services | No page/component owns internal transport | Implemented; frontend build verified 2026-07-30 |
| P2 | Deprecate duplicate routes safely | Callers migrated before aliases/removal | Implemented: trailing-slash Trends/Statistics aliases removed |
| Verify | Frontend production build | `npm.cmd run build` | Passed on 2026-07-30 |
| Verify | Backend focused tests | pytest evidence | Blocked: invalid `.venv` base Python |

## Required execution order

1. Map endpoint, caller, request model, data store, and authorization boundary.
2. Patch backend authorization and stable error handling.
3. Migrate the frontend caller to its domain service/model.
4. Verify anonymous rejection and authenticated safe read behaviour.
5. Run frontend build; update `documentation.md` with actual evidence.
6. Only then move to the next domain.
