# Trends page simplification harness

Date: 2026-07-30

## Task status

| Cycle | Check | Result | Evidence |
|---:|---|---|---|
| 1 | Task and complexity audit | Pass | The page coordinated five API calls, had long static status text, and hard-truncated moments/sources. |
| 2 | Dedicated service | Pass | Added `frontend/src/services/trendsDashboardService.ts`; `trends.tsx` no longer imports raw API operations or calls `fetch` directly. |
| 2 | Text reduction | Pass | Replaced the YouTube/Reels sentence with a compact reference-count badge; removed non-actionable Campaign Planner explanatory copy. |
| 2 | Pagination | Pass | Moments: 4 per page. Sources: 8 per page. Both use accessible Previous/Next controls and reset when relevant filters change. |
| 3 | Type and lint validation | Pass | `eslint` passed for `trends.tsx`, `trendsDashboardService.ts`, and `trendsApi.ts`; `tsc --noEmit -p frontend/tsconfig.json` passed. |
| 3 | Production build | Pass with warning | Vite build succeeded. The bundle still has an existing large-chunk warning: main JS is about 1.05 MB uncompressed / 309 KB gzip. |
| 3 | Authenticated browser test | Pass | In Content ideas, moments changed from `1–4 of 177` to `5–8 of 177`; sources changed from `1–8 of 23` to `9–16 of 23`; the compact YouTube/Reels reference badge rendered. |
| 3 | Static review | Pass | No raw API calls remain in `trends.tsx`; no unused request orchestration was left in the page; `git diff --check` passed. |
| 3 | Remote engineering-skill installation | Blocked by environment | The supplied skill-installer helper cannot import its bundled `github_utils` module in this runtime. Existing `validation-loop` and local code-review standards were used instead. |

## Product judgement

The page now has a clearer hierarchy: **moments**, **ad ideas**, **campaign brief**, then **source material**. It still contains rich recommendation text when the user needs it; that is product content, not UI noise. If further simplification is needed, the next candidate is making the Campaign Planner execution checklist collapsible on small screens—not deleting the recommendation evidence.
