-- Evidence-backed creative trend signals, separate from raw source-post discovery.

CREATE TABLE IF NOT EXISTS public.creative_trend_signals (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_type text NOT NULL CHECK (signal_type IN (
        'sound', 'music', 'dance_or_challenge', 'hook', 'meme_or_phrase',
        'format_or_template', 'visual_style', 'creator_behavior',
        'hashtag_or_topic', 'seasonal_or_cultural_moment'
    )),
    title text NOT NULL,
    summary text NOT NULL,
    why_trending text,
    how_it_works text,
    suggested_adaptation text NOT NULL,
    do_not_do text,
    target_platforms text[] NOT NULL DEFAULT '{}',
    market text NOT NULL DEFAULT 'malaysia',
    owner_email text,
    audience text,
    language text,
    momentum text NOT NULL DEFAULT 'unknown' CHECK (momentum IN ('rising', 'peaking', 'stable', 'declining', 'unknown')),
    confidence text NOT NULL DEFAULT 'low' CHECK (confidence IN ('low', 'medium', 'high')),
    detected_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_creative_trend_signals_scope
    ON public.creative_trend_signals(market, owner_email, detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_creative_trend_signals_type
    ON public.creative_trend_signals(signal_type);

CREATE TABLE IF NOT EXISTS public.creative_trend_sources (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id uuid NOT NULL REFERENCES public.creative_trend_signals(id) ON DELETE CASCADE,
    url text NOT NULL,
    source_title text,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT creative_trend_sources_signal_url_unique UNIQUE(signal_id, url)
);

CREATE INDEX IF NOT EXISTS idx_creative_trend_sources_signal
    ON public.creative_trend_sources(signal_id);
