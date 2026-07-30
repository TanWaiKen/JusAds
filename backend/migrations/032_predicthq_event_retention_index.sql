-- Supports operator retention of imported PredictHQ events. Manual/curated
-- rows are intentionally excluded from the retention workflow.
CREATE INDEX IF NOT EXISTS idx_cultural_events_source_end_date
    ON public.cultural_events(source, end_date);
