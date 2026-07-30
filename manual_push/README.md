# Manual operator tools and datasets

Everything in this directory is explicitly operator-run. It is deliberately
outside `backend/` and `cloud/`, so a deployment does not carry historical CSV
backups, seed data, or destructive admin scripts.

| Folder | Purpose | Safe to run automatically? |
| --- | --- | --- |
| `predicthq/` | Supported PredictHQ event refresh and CSV backup | Yes, after `--dry-run` |
| `events/` | Legacy event imports and CSV-to-Supabase utilities | No; inspect input and target first |
| `trends/` | Manual Google-search trend refresh | No; writes a scoped cache |
| `seed/` | Regulatory rules, personas, and platform-rule seed assets | No; writes Supabase tables |
| `ml/` | Synthetic ML triage proof-of-concept evaluation | Yes; reads local fixture only |
| `admin/` | Administrative scripts | No; `clean_schema.py` is quarantined and must not be used |
| `data/` | Local CSV/JSONL backups and Qdrant source data | Never deployed |

`data/nano-banana-pro-prompts-20260701.csv` is intentionally preserved. It is
the manually maintained source corpus for Qdrant prompt ingestion, not a
frontend cache. Run the ingestion entry point from `backend/`:

```powershell
cd backend
python -m jusads_generation.prompt_search.ingest
```

Do not use `admin/clean_schema.py`: it is a legacy local edit script and its
table list is stale. It remains only as an audit artifact, not an approved
migration path.

## PredictHQ event refresh

`predicthq/refresh_events.py` follows every accessible PredictHQ page, writes a
CSV backup, and upserts only rows whose stable PredictHQ event ID matches.
Curated/manual calendar rows are never overwritten. If the API returns
`overflow: true`, the script reports that the free-tier subscription has capped
the result set.

1. Ensure `backend/.env` contains `PREDICTHQ_API_KEY`, `SUPABASE_URL`, and a
   server-only `SUPABASE_KEY` (or `SUPABASE_SERVICE_ROLE_KEY`). Never put these
   values in `frontend/.env`.
2. Preview before writing:

   ```powershell
   python manual_push/predicthq/refresh_events.py --dry-run
   ```

3. Apply the import:

   ```powershell
   python manual_push/predicthq/refresh_events.py --replace-backups
   ```

Optional flags: `--days 120`, `--markets MY,SG,TH,ID,VN,PH`, and `--page-size 100`.

After a successful write, the script removes only `source='predicthq'` events
that ended more than 90 days ago. It never deletes manually curated calendar
rows. Adjust the policy with `--retention-days`.

The importer reports the fetched count and any subscription overflow. An empty
result is reported as `0 fetched`; it is never described as a successful
recommendation refresh. `sync_predicthq_events.mjs` is deprecated because it
reads only the first result page; do not use it for imports.
