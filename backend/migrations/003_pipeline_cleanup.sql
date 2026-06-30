-- Migration: Add pipeline_progress and platform_rules tables
-- Supports: Supabase-backed progress tracking and platform format rules
-- Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6

-- ═══════════════════════════════════════════════════════════════════════════════
-- pipeline_progress: Tracks step-by-step progress for each compliance check
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE pipeline_progress (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    check_id TEXT NOT NULL REFERENCES compliance_checks(check_id),
    step_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'error')),
    message TEXT CHECK (char_length(message) <= 1000),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_pipeline_progress_check_id ON pipeline_progress(check_id);

-- Auto-update updated_at on row modification
CREATE OR REPLACE FUNCTION update_pipeline_progress_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_pipeline_progress_updated_at
    BEFORE UPDATE ON pipeline_progress
    FOR EACH ROW
    EXECUTE FUNCTION update_pipeline_progress_updated_at();

-- ═══════════════════════════════════════════════════════════════════════════════
-- platform_rules: Platform-specific media format requirements
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE platform_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform TEXT NOT NULL,
    media_type TEXT NOT NULL CHECK (media_type IN ('text', 'image', 'audio', 'video')),
    aspect_ratio TEXT NOT NULL,
    max_duration_seconds INTEGER,
    max_file_size_mb INTEGER,
    additional_rules JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (platform, media_type, aspect_ratio)
);
