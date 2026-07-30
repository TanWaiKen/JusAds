-- Add the new column
ALTER TABLE public.creative_trend_signals ADD COLUMN IF NOT EXISTS evidence_urls jsonb NOT NULL DEFAULT '[]';

-- Merge existing data
UPDATE public.creative_trend_signals s
SET evidence_urls = (
    SELECT jsonb_agg(url) FROM public.creative_trend_sources WHERE signal_id = s.id
)
WHERE EXISTS (SELECT 1 FROM public.creative_trend_sources WHERE signal_id = s.id);

-- Drop unused and merged tables
DROP TABLE IF EXISTS public.creative_trend_sources CASCADE;
DROP TABLE IF EXISTS public.tavily_usage_log CASCADE;
-- Do not drop remediation_versions, compliance_evaluations, or
-- remediation_recheck_jobs.  They are the immutable evidence that a generated
-- correction was rechecked.  Removing them would turn a verified-compliance
-- claim into an unprovable assertion and would discard historical audit data.
DROP TABLE IF EXISTS public.private_media_url_audit CASCADE;
DROP TABLE IF EXISTS public.pipeline_progress CASCADE;
DROP TABLE IF EXISTS public.storyboard_scenes CASCADE;
DROP TABLE IF EXISTS public.post_statistics_cache CASCADE;
DROP TABLE IF EXISTS public.remediation_logs CASCADE;
