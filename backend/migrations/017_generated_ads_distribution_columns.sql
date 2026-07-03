-- ═══════════════════════════════════════════════════════════════════════════════
-- Migration 017: Add compliance + distribution columns to generated_ads
--
-- Safe to re-run (uses IF NOT EXISTS via ADD COLUMN IF NOT EXISTS).
-- Run this in Supabase SQL Editor on your existing database.
-- ═══════════════════════════════════════════════════════════════════════════════

-- Compliance columns (written by compliance_bridge after generation)
ALTER TABLE public.generated_ads
ADD COLUMN IF NOT EXISTS compliance_status text,
ADD COLUMN IF NOT EXISTS compliance_result jsonb,
ADD COLUMN IF NOT EXISTS compliance_check_id text;

-- Distribution columns (written after Zernio push)
ALTER TABLE public.generated_ads
ADD COLUMN IF NOT EXISTS distributed_at timestamptz,
ADD COLUMN IF NOT EXISTS distribution_platform text,
ADD COLUMN IF NOT EXISTS distribution_post_id text;
