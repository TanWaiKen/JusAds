-- ═══════════════════════════════════════════════════════════════════════════════
-- Migration 005: Add business_profiles table
-- 
-- Mandatory onboarding for compliance/generation. Stores what the user's
-- company does so the AI has product context for smart compliance checking.
--
-- Run in Supabase SQL Editor on existing databases.
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.business_profiles (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    owner_email text NOT NULL UNIQUE,
    company_name text NOT NULL,
    product_category text NOT NULL,
    product_description text,
    target_platforms text[] NOT NULL DEFAULT '{}',
    target_markets text[] NOT NULL DEFAULT '{}',
    logo_s3_key text,
    onboarding_complete boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT business_profiles_pkey PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_business_profiles_email
    ON public.business_profiles(owner_email);
