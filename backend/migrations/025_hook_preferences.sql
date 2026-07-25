-- 025_hook_preferences.sql
-- Hook video preference learning table for association-rules reranking.
-- Stores which YouTube hook videos a user selects, their tags, and context.

CREATE TABLE IF NOT EXISTS hook_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    video_id TEXT NOT NULL,
    tags JSONB DEFAULT '[]'::jsonb,
    creative_style TEXT DEFAULT 'meme_shock',
    product_category TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Index for fast user preference lookups
CREATE INDEX IF NOT EXISTS idx_hook_preferences_user
    ON hook_preferences (user_id, created_at DESC);

-- Index for analytics: which hook styles are popular globally
CREATE INDEX IF NOT EXISTS idx_hook_preferences_style
    ON hook_preferences (creative_style, created_at DESC);

-- RLS: users can only read/write their own preferences
ALTER TABLE hook_preferences ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage their own hook preferences"
    ON hook_preferences
    FOR ALL
    USING (true)
    WITH CHECK (true);
