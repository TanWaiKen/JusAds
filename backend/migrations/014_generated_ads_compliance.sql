-- ═══════════════════════════════════════════════════════════════════════════════
-- Migration 014: Add compliance tracking columns to generated_ads
--
-- Each generated ad must pass through the compliance bridge before it can be
-- marked final. These columns let compliance status be queried and badge-rendered
-- per output (Req 11.2), so a typed, indexable column is preferable to a nested
-- JSON key. The richer pipeline output stays in compliance_result (jsonb) and
-- compliance_check_id links back to a compliance_checks row.
--
-- Requirements: 8.2, 8.4, 8.5, 11.2
--
-- Run in Supabase SQL Editor on existing databases.
-- ═══════════════════════════════════════════════════════════════════════════════

ALTER TABLE public.generated_ads
    ADD COLUMN IF NOT EXISTS compliance_status text
        NOT NULL DEFAULT 'non-final'
        CHECK (compliance_status IN ('final-compliant', 'final-non-compliant', 'non-final')),
    ADD COLUMN IF NOT EXISTS compliance_result jsonb,
    ADD COLUMN IF NOT EXISTS compliance_check_id text;

CREATE INDEX IF NOT EXISTS idx_generated_ads_compliance_status
    ON public.generated_ads(compliance_status);
