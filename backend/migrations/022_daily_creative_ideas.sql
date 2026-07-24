-- One market-wide creative recommendation per local calendar day.

CREATE TABLE IF NOT EXISTS public.daily_creative_ideas (
    idea_date date NOT NULL,
    market text NOT NULL DEFAULT 'malaysia',
    payload jsonb NOT NULL,
    generated_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (idea_date, market)
);

CREATE INDEX IF NOT EXISTS idx_daily_creative_ideas_expiry
    ON public.daily_creative_ideas (expires_at);
