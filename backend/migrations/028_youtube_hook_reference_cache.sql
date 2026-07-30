-- Cached public YouTube hook references. Results are scoped to the verified
-- account email, market, and a hash of the saved business-profile context.
-- The backend is the only writer/reader; no direct Data API access is needed.

CREATE TABLE IF NOT EXISTS public.youtube_hook_reference_cache (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_email text NOT NULL,
    market text NOT NULL DEFAULT 'malaysia',
    profile_fingerprint char(64) NOT NULL,
    query_text text NOT NULL,
    results jsonb NOT NULL DEFAULT '[]'::jsonb,
    fetched_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT youtube_hook_reference_cache_scope_unique
        UNIQUE (owner_email, market, profile_fingerprint),
    CONSTRAINT youtube_hook_reference_cache_results_array
        CHECK (jsonb_typeof(results) = 'array')
);

CREATE INDEX IF NOT EXISTS idx_youtube_hook_reference_cache_expiry
    ON public.youtube_hook_reference_cache(owner_email, market, expires_at DESC);

ALTER TABLE public.youtube_hook_reference_cache ENABLE ROW LEVEL SECURITY;
