-- ═══════════════════════════════════════════════════════════════════════════════
-- Migration 020: Research & Intelligence Layer
--
-- Adds tables for:
--   - trends_cache: Apify-scraped trending content from social platforms
--   - cultural_events: Known cultural/national/global events per market
--   - post_statistics_cache: Cached Zernio post performance metrics
--   - tavily_usage_log: Cost monitoring for Tavily compliance searches
--
-- Also ALTERs generated_ads for CapCut dual output columns.
-- ═══════════════════════════════════════════════════════════════════════════════


-- ─── 1. trends_cache ─────────────────────────────────────────────────────────
-- Stores scraped trending content from Apify actors (weekly refresh).

CREATE TABLE IF NOT EXISTS public.trends_cache (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    platform text NOT NULL CHECK (platform IN ('tiktok', 'instagram', 'youtube', 'facebook_ads')),
    content_type text NOT NULL,
    title text NOT NULL,
    url text NOT NULL,
    engagement_metrics jsonb NOT NULL DEFAULT '{}',
    hashtags text[] DEFAULT '{}',
    categories text[] DEFAULT '{}',
    cultural_event_tag text,
    market text NOT NULL DEFAULT 'malaysia',
    owner_email text,
    scraped_at timestamptz NOT NULL DEFAULT now(),
    scrape_batch_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT trends_cache_pkey PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_trends_cache_platform
    ON public.trends_cache(platform);

CREATE INDEX IF NOT EXISTS idx_trends_cache_market
    ON public.trends_cache(market);

CREATE INDEX IF NOT EXISTS idx_trends_cache_scraped_at
    ON public.trends_cache(scraped_at DESC);

CREATE INDEX IF NOT EXISTS idx_trends_cache_event
    ON public.trends_cache(cultural_event_tag)
    WHERE cultural_event_tag IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_trends_cache_batch
    ON public.trends_cache(scrape_batch_id);


-- ─── 2. cultural_events ──────────────────────────────────────────────────────
-- Reference list of known cultural, religious, and global events per market.

CREATE TABLE IF NOT EXISTS public.cultural_events (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    name text NOT NULL,
    market text NOT NULL,
    start_date date NOT NULL,
    end_date date NOT NULL,
    event_type text NOT NULL CHECK (event_type IN ('religious', 'festive', 'sports', 'national', 'global')),
    tags text[] DEFAULT '{}',
    impact_score integer CHECK (impact_score >= 0 AND impact_score <= 100),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT cultural_events_pkey PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_cultural_events_market_date
    ON public.cultural_events(market, start_date);

CREATE INDEX IF NOT EXISTS idx_cultural_events_type
    ON public.cultural_events(event_type);


-- ─── 3. post_statistics_cache ────────────────────────────────────────────────
-- Cached Zernio post performance metrics for the statistics page.

CREATE TABLE IF NOT EXISTS public.post_statistics_cache (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    generated_ad_id uuid NOT NULL,
    platform text NOT NULL,
    post_external_id text NOT NULL,
    impressions integer DEFAULT 0,
    clicks integer DEFAULT 0,
    engagement_rate numeric DEFAULT 0,
    reach integer DEFAULT 0,
    conversions integer DEFAULT 0,
    raw_metrics jsonb,
    fetched_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT post_statistics_cache_pkey PRIMARY KEY (id),
    CONSTRAINT post_stats_ad_fkey FOREIGN KEY (generated_ad_id)
        REFERENCES public.generated_ads(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_post_stats_ad
    ON public.post_statistics_cache(generated_ad_id);

CREATE INDEX IF NOT EXISTS idx_post_stats_fetched
    ON public.post_statistics_cache(fetched_at DESC);

CREATE INDEX IF NOT EXISTS idx_post_stats_platform
    ON public.post_statistics_cache(platform);


-- ─── 4. tavily_usage_log ─────────────────────────────────────────────────────
-- Audit log for Tavily API invocations (cost monitoring).

CREATE TABLE IF NOT EXISTS public.tavily_usage_log (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    task_id uuid NOT NULL,
    query text NOT NULL,
    results_count integer DEFAULT 0,
    search_depth text NOT NULL DEFAULT 'advanced',
    invoked_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT tavily_usage_log_pkey PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_tavily_usage_task
    ON public.tavily_usage_log(task_id);

CREATE INDEX IF NOT EXISTS idx_tavily_usage_time
    ON public.tavily_usage_log(invoked_at DESC);


-- ─── 5. ALTER generated_ads — CapCut dual output columns ─────────────────────

ALTER TABLE public.generated_ads
    ADD COLUMN IF NOT EXISTS s3_draft_key text,
    ADD COLUMN IF NOT EXISTS s3_rendered_key text;


-- ─── 6. ALTER brand_voices — support global catalog + custom clones ──────────

ALTER TABLE public.brand_voices
    ALTER COLUMN project_id DROP NOT NULL;

ALTER TABLE public.brand_voices
    ADD COLUMN IF NOT EXISTS market text,
    ADD COLUMN IF NOT EXISTS ethnicity text,
    ADD COLUMN IF NOT EXISTS gender text DEFAULT 'female',
    ADD COLUMN IF NOT EXISTS language_code text DEFAULT 'ms',
    ADD COLUMN IF NOT EXISTS is_custom_clone boolean NOT NULL DEFAULT false;

-- Drop the old unique constraint (one voice per project) to allow multiple globals
ALTER TABLE public.brand_voices
    DROP CONSTRAINT IF EXISTS brand_voices_unique_project;

-- Index for global voice catalog lookups
CREATE INDEX IF NOT EXISTS idx_brand_voices_global
    ON public.brand_voices(market, ethnicity, gender)
    WHERE project_id IS NULL AND status = 'active';


-- ─── 6. Seed cultural_events with Malaysian & global events ──────────────────
-- 2026 dates (current year). For dynamic event updates, integrate PredictHQ API
-- or Google Calendar API to refresh this table automatically.
-- CSV backup: backend/data/cultural_events_2026.csv

INSERT INTO public.cultural_events (name, market, start_date, end_date, event_type, tags, impact_score)
VALUES
    -- Malaysia — Religious & Festive (2026)
    ('Thaipusam', 'malaysia', '2026-01-14', '2026-01-14', 'religious', ARRAY['hindu', 'indian', 'devotion'], 72),
    ('Chinese New Year', 'malaysia', '2026-02-17', '2026-02-18', 'festive', ARRAY['cny', 'family', 'reunion', 'prosperity', 'chinese'], 94),
    ('Ramadan', 'malaysia', '2026-02-18', '2026-03-19', 'religious', ARRAY['islamic', 'fasting', 'malay', 'ramadan'], 91),
    ('Nuzul Al-Quran', 'malaysia', '2026-03-05', '2026-03-05', 'religious', ARRAY['islamic', 'quran', 'malay'], 68),
    ('Hari Raya Aidilfitri', 'malaysia', '2026-03-20', '2026-03-21', 'festive', ARRAY['raya', 'malay', 'eid', 'celebration', 'family'], 96),
    ('Labour Day', 'malaysia', '2026-05-01', '2026-05-01', 'national', ARRAY['holiday', 'workers'], 45),
    ('Wesak Day', 'malaysia', '2026-05-01', '2026-05-01', 'religious', ARRAY['buddhist', 'chinese'], 58),
    ('Hari Raya Haji', 'malaysia', '2026-05-27', '2026-05-28', 'religious', ARRAY['islamic', 'malay', 'sacrifice'], 78),
    ('Merdeka Day', 'malaysia', '2026-08-31', '2026-08-31', 'national', ARRAY['independence', 'patriotic', 'malaysia'], 88),
    ('Malaysia Day', 'malaysia', '2026-09-16', '2026-09-16', 'national', ARRAY['patriotic', 'unity', 'malaysia'], 82),
    ('Deepavali', 'malaysia', '2026-11-08', '2026-11-08', 'festive', ARRAY['indian', 'hindu', 'lights', 'celebration'], 80),
    ('Christmas', 'malaysia', '2026-12-25', '2026-12-25', 'festive', ARRAY['christian', 'family', 'gifts', 'celebration'], 75),

    -- Singapore (2026)
    ('Chinese New Year', 'singapore', '2026-02-17', '2026-02-18', 'festive', ARRAY['cny', 'family', 'chinese', 'prosperity'], 92),
    ('Hari Raya Aidilfitri', 'singapore', '2026-03-20', '2026-03-21', 'festive', ARRAY['raya', 'malay', 'eid'], 85),
    ('National Day', 'singapore', '2026-08-09', '2026-08-09', 'national', ARRAY['patriotic', 'singapore', 'ndp'], 90),
    ('Deepavali', 'singapore', '2026-11-08', '2026-11-08', 'festive', ARRAY['indian', 'hindu', 'lights'], 78),
    ('Christmas', 'singapore', '2026-12-25', '2026-12-25', 'festive', ARRAY['christian', 'family', 'orchard'], 80),

    -- Global events (2026)
    ('FIFA World Cup 2026', 'malaysia', '2026-06-11', '2026-07-19', 'sports', ARRAY['football', 'soccer', 'fifa', 'global', 'world cup'], 95),
    ('FIFA World Cup 2026', 'singapore', '2026-06-11', '2026-07-19', 'sports', ARRAY['football', 'soccer', 'fifa', 'global', 'world cup'], 90),
    ('Year-End Sales (11.11)', 'malaysia', '2026-11-11', '2026-11-11', 'global', ARRAY['shopping', 'ecommerce', 'sale', 'shopee'], 85),
    ('Year-End Sales (12.12)', 'malaysia', '2026-12-12', '2026-12-12', 'global', ARRAY['shopping', 'ecommerce', 'sale', 'shopee'], 83),
    ('Black Friday', 'malaysia', '2026-11-27', '2026-11-27', 'global', ARRAY['shopping', 'sale', 'deals'], 60),
    ('Year-End Sales (11.11)', 'singapore', '2026-11-11', '2026-11-11', 'global', ARRAY['shopping', 'ecommerce', 'sale'], 87),
    ('Year-End Sales (12.12)', 'singapore', '2026-12-12', '2026-12-12', 'global', ARRAY['shopping', 'ecommerce', 'sale'], 85)
ON CONFLICT DO NOTHING;


-- ─── 8. Seed global voice catalog (ElevenLabs pre-configured voices) ─────────
-- These are available to all users (project_id IS NULL).
-- voice_id values are ElevenLabs public/shared voice IDs.

INSERT INTO public.brand_voices (project_id, voice_id, voice_name, description, market, ethnicity, gender, language_code, is_custom_clone, status)
VALUES
    -- Malay voices
    (NULL, 'qAJVXEQ6QgjOQ25KuoU8', 'Aisyah', 'Young Malay female voice — warm, friendly, conversational', 'malaysia', 'malay', 'female', 'ms', false, 'active'),
    (NULL, 'pNInz6obpgDQGcFmaJgB', 'Hafiz', 'Malay male voice — confident, professional', 'malaysia', 'malay', 'male', 'ms', false, 'active'),
    -- Chinese voices
    (NULL, 'EXAVITQu4vr4xnSDxMaL', 'Mei Lin', 'Chinese Malaysian female — clear, modern', 'malaysia', 'chinese', 'female', 'zh', false, 'active'),
    (NULL, '21m00Tcm4TlvDq8ikWAM', 'Wei Ming', 'Chinese Malaysian male — professional, neutral', 'malaysia', 'chinese', 'male', 'zh', false, 'active'),
    -- Indian voices
    (NULL, 'AZnzlk1XvdvUeBnXmlld', 'Priya', 'Indian Malaysian female — warm, expressive', 'malaysia', 'indian', 'female', 'ta', false, 'active'),
    (NULL, 'IKne3meq5aSn9XLyUdCD', 'Arjun', 'Indian Malaysian male — clear, authoritative', 'malaysia', 'indian', 'male', 'ta', false, 'active'),
    -- English (Singapore / universal)
    (NULL, 'ThT5KcBeYPX3keUQqHPh', 'Sarah', 'English female — neutral, professional', 'singapore', 'all', 'female', 'en', false, 'active'),
    (NULL, 'VR6AewLTigWG4xSOukaG', 'Daniel', 'English male — warm, trustworthy', 'singapore', 'all', 'male', 'en', false, 'active')
ON CONFLICT DO NOTHING;
