# Implementation and validation runbook

## Backend pattern

```python
async def route(project_id: str, principal: Principal = Depends(get_current_principal)):
    require_project_access(store, project_id, principal, write=False)
```

Use `write=True` for mutations. For asset/ad/task IDs, resolve the resource to its project first; do not accept a separate claimed project ID as proof of access. Use `HTTPException` or controlled `JSONResponse` errors with a documented `code` and safe `message`.

For files, request models must not contain identity fields used for authorization. Build the S3 object prefix from an opaque verified Cognito subject and a verified project ID. Confirm an S3 key belongs to the authorized asset/project before signing a download.

## Frontend pattern

- Put API paths and authenticated transport in `src/services/<domain>Service.ts`.
- Put request/response interfaces in `src/models/<domain>.ts`.
- Components call a service function or a feature hook; they do not use `API_BASE`, `authenticatedFetch`, or `fetch` for an internal API.
- External presigned-S3 `PUT` is allowed inside `mediaService`, never inside a component.
- Standardize error parsing via `getApiError` and show a user-safe message.

## Safe validation matrix

| Test | Expected result |
|---|---|
| Public health/readiness without token | `200` |
| Protected route without token | `401` |
| Protected safe read with valid token | `200` or controlled empty result |
| Invalid project ID with valid token | `404`, never `500` |
| Frontend build | passes |
| Paid, mutating, upload, publish, delete, external refresh endpoint | do not invoke in audit |

## Environment limitation

`backend/.venv/pyvenv.cfg` references a Windows Store Python alias that is not usable from this environment. Do not destroy or recreate the environment without the owner approving a real Python installation. Until repaired, backend pytest is blocked; run syntax checks and frontend build, but do not call the backend test suite “passed.”
