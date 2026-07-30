# JusAds trend domain

This package is the home for non-HTTP trend intelligence logic:

- `daily_idea.py` — date-stable creative ideas from saved trend and event data.
- `creative_signals.py` — evidence-backed creative-pattern research and storage.
- `youtube_hook_cache.py` — company-context YouTube hook-reference query,
  serialization, and cache-fingerprint helpers.
- `youtube_hook_references.py` — authenticated-user scoped YouTube retrieval
  and Supabase cache service.

`routes/trends.py` deliberately remains a thin FastAPI transport adapter. It
owns request/response validation and authentication; trend research, cache, and
analysis rules belong in this package. New trend features must be added here
rather than to generation or compliance modules.

The trend data model is: `trends_cache`, `creative_trend_signals` (including
its `evidence_urls` JSON field), `daily_creative_ideas`, and
`youtube_hook_reference_cache`. These records are creative inspiration only;
they are not compliance decisions or proof that a public video is a paid ad.
