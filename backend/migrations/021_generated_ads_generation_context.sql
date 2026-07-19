-- ═══════════════════════════════════════════════════════════════════════════
-- Migration 021: generated-ad audience, provenance and asset-role context
--
-- Run once against an existing database AFTER migrations 016–020.
-- This is forward-only and preserves all existing generated_ads rows.
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

-- Keep references, intermediate artifacts and user-facing outputs distinct.
ALTER TABLE public.generated_ads
    ADD COLUMN IF NOT EXISTS asset_role text NOT NULL DEFAULT 'output',
    ADD COLUMN IF NOT EXISTS generation_mode text NOT NULL DEFAULT 'advanced',
    ADD COLUMN IF NOT EXISTS version_number integer NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS market text,
    ADD COLUMN IF NOT EXISTS ethnicity text,
    ADD COLUMN IF NOT EXISTS age_group text,
    ADD COLUMN IF NOT EXISTS target_language text,
    ADD COLUMN IF NOT EXISTS generation_context jsonb NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS brand_snapshot jsonb NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS localization_snapshot jsonb NOT NULL DEFAULT '{}';

-- The CapCut columns may already exist from 020_research_intelligence_layer.
ALTER TABLE public.generated_ads
    ADD COLUMN IF NOT EXISTS s3_draft_key text,
    ADD COLUMN IF NOT EXISTS s3_rendered_key text;

-- Preserve the meaning of previously stored reference assets.
UPDATE public.generated_ads
SET asset_role = 'reference'
WHERE COALESCE(metadata ->> 'is_reference', 'false') = 'true';

-- Constraints are added separately so this migration remains idempotent.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'generated_ads_asset_role_check'
    ) THEN
        ALTER TABLE public.generated_ads
            ADD CONSTRAINT generated_ads_asset_role_check
            CHECK (asset_role IN ('output', 'reference', 'intermediate'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'generated_ads_version_number_check'
    ) THEN
        ALTER TABLE public.generated_ads
            ADD CONSTRAINT generated_ads_version_number_check
            CHECK (version_number > 0);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_generated_ads_project_role_created
    ON public.generated_ads(project_id, asset_role, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_generated_ads_task_created
    ON public.generated_ads(task_id, created_at DESC)
    WHERE task_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_generated_ads_audience
    ON public.generated_ads(market, ethnicity, age_group)
    WHERE asset_role = 'output';

COMMIT;
