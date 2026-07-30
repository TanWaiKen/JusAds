# PredictHQ dry run and Campaign Planner validation

Date: 2026-07-30

This is a reproducible operator record, not a mock result. The run used the configured server-side PredictHQ credential and the developer test account. No credentials are recorded here.

## 1. Read-only PredictHQ dry run

Command run from the repository root:

```powershell
& 'C:\Program Files\PostgreSQL\18\pgAdmin 4\python\python.exe' manual_push\predicthq\refresh_events.py --dry-run --days 120
```

Result:

| Market | Events fetched | Pages | API count | Subscription overflow |
|---|---:|---:|---:|---|
| Malaysia | 327 | 7 | 327 | No |
| Singapore | 492 | 10 | 492 | No |
| Thailand | 322 | 7 | 322 | No |
| Indonesia | 294 | 6 | 294 | No |
| Vietnam | 132 | 3 | 132 | No |
| Philippines | 269 | 6 | 269 | No |
| **Total** | **1,836** | **39** | **1,836** | **No** |

CSV export created: `manual_push/backups/predicthq/predicthq_events_20260729T170415Z.csv`.

The dry-run output explicitly confirmed: **“Dry run: Supabase unchanged.”** It therefore verifies pagination, current API access, and expected volume without consuming database write operations.

## 2. Browser validation: authenticated Campaign Planner

1. Opened `http://localhost:5173/`.
2. Signed in using the supplied developer test account.
3. Navigated to **Content ideas** (`/dashboard/trends`).
4. Waited for saved research to load.

Observed live UI results:

- The page showed **23 saved ideas**.
- The event feed reported: **PredictHQ last refreshed 30 Jul · 175 imported events in this view.**
- The **YouTube/Reels hook references** message was present: “Using saved YouTube/Reels hook references for your company context.”
- YouTube hook-reference cards were visible in **Sources**, each linked to its original YouTube video.
- The Campaign Planner showed a market-specific recommendation, timing rationale, objective, format, opening hook, execution checklist, source-link count, and **Use in campaign** button.
- The Upcoming moments panel showed the verified Malaysia calendar entries first (Maulidur Rasul and National Day), each with the **Verified official calendar** label and a source link to the Malaysia Government Calendar.

## 3. Data correction applied before this validation

- Removed **342** unverified `manual` cultural-event rows, including the incorrect “Hari Raya Aidilfitri Festive Bazars” date range.
- Added **25** records from government or official-calendar sources for Malaysia, Singapore, Thailand, Indonesia, Vietnam, and the Philippines.
- Each new official-calendar record stores its source URL in `source_payload` and is labelled **Verified official calendar** in the UI when shown.

## 4. Limitations to remember

- PredictHQ provides operational event discovery for a rolling 120-day window; it is not a legal public-holiday authority.
- Official-calendar records are intentionally a small verified layer, not an attempt to model every local festival or state/province holiday.
- Moon-sighting and government-declared holidays can change. Re-verify time-sensitive religious or special holidays before publishing a campaign.
