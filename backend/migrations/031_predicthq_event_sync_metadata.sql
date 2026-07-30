-- Preserve curated calendar rows while making imported PredictHQ events
-- idempotent, inspectable, and safe to refresh.
ALTER TABLE public.cultural_events
    ADD COLUMN IF NOT EXISTS source text NOT NULL DEFAULT 'manual',
    ADD COLUMN IF NOT EXISTS source_event_id text,
    ADD COLUMN IF NOT EXISTS source_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS source_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS last_synced_at timestamptz;

ALTER TABLE public.cultural_events
    ADD CONSTRAINT cultural_events_source_event_unique
    UNIQUE (source, source_event_id);

CREATE INDEX IF NOT EXISTS idx_cultural_events_source_sync
    ON public.cultural_events(source, last_synced_at DESC);
