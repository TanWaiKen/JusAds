# Manual Trigger Scripts

Scripts in this folder require **manual execution** — they are NOT automated.
Run them from the `backend/` directory when you need to refresh data.

## Scripts

| Script | Purpose | When to Run |
|--------|---------|-------------|
| `refresh_trends.py` | Scrape TikTok/IG/YouTube/FB Ads via Apify | Weekly, or when trends data is stale |
| `refresh_events.py` | Update cultural_events from PredictHQ/Google Calendar | Monthly, or before new quarter |
| `seed_test_trends.py` | Insert mock trending data for development/testing | Once for dev setup |

## Usage

```bash
cd backend
.venv/Scripts/python scripts/manual/refresh_trends.py
.venv/Scripts/python scripts/manual/refresh_events.py
.venv/Scripts/python scripts/manual/seed_test_trends.py
```

## Requirements

- `APIFY_API_TOKEN` in `.env` for `refresh_trends.py`
- `SUPABASE_URL` + `SUPABASE_KEY` in `.env` for all scripts
- (Optional) `PREDICTHQ_API_KEY` in `.env` for `refresh_events.py`
