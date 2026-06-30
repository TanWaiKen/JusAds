-- ═══════════════════════════════════════════════════════════════════════════════
-- Migration 004: Domain-Specific Tables
-- 
-- Adds 4 tables required by the NIMBUS pipeline:
--   1. regulatory_rules   — Cultural & legal rules (3R, Halal, Online Safety)
--   2. target_personas    — Persona constraints for bias validation
--   3. storyboard_scenes  — Per-cut tracking for multi-scene video generation
--   4. remediation_logs   — Audit trail for each remediation attempt
--
-- Run in Supabase SQL Editor or via: psql $DATABASE_URL -f 004_domain_tables.sql
-- ═══════════════════════════════════════════════════════════════════════════════


-- ─── 1. regulatory_rules ─────────────────────────────────────────────────────
-- The Main Brain agent queries this for country-specific cultural/legal rules
-- that go beyond technical platform specs (which live in platform_rules).

CREATE TABLE IF NOT EXISTS public.regulatory_rules (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    country_code text NOT NULL,
    category text NOT NULL,
    rule_name text NOT NULL,
    rule_description text NOT NULL CHECK (char_length(rule_description) <= 2000),
    severity_default text NOT NULL CHECK (severity_default IN ('low', 'medium', 'high', 'critical')),
    additional_context jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT regulatory_rules_pkey PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_regulatory_rules_country
    ON public.regulatory_rules(country_code);

CREATE INDEX IF NOT EXISTS idx_regulatory_rules_category
    ON public.regulatory_rules(category);

CREATE INDEX IF NOT EXISTS idx_regulatory_rules_country_category
    ON public.regulatory_rules(country_code, category);


-- ─── 2. target_personas ──────────────────────────────────────────────────────
-- Structured persona constraints used by the Judges Agent to flag bias
-- and by the Main Brain to evaluate cultural fit.

CREATE TABLE IF NOT EXISTS public.target_personas (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    country_code text NOT NULL,
    ethnicity text NOT NULL,
    age_group text NOT NULL,
    cultural_sensitivities text[] NOT NULL,
    preferred_languages text[] NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT target_personas_pkey PRIMARY KEY (id),
    CONSTRAINT target_personas_unique UNIQUE (country_code, ethnicity, age_group)
);

CREATE INDEX IF NOT EXISTS idx_target_personas_country
    ON public.target_personas(country_code);

CREATE INDEX IF NOT EXISTS idx_target_personas_country_ethnicity
    ON public.target_personas(country_code, ethnicity);


-- ─── 3. storyboard_scenes ────────────────────────────────────────────────────
-- Tracks individual 3-5 second cuts in a multi-scene video generation or
-- remediation task. Enables resume-from-last-completed-scene on timeout.

CREATE TABLE IF NOT EXISTS public.storyboard_scenes (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL,
    check_id text,
    scene_index integer NOT NULL,
    timestamp_start numeric NOT NULL,
    timestamp_end numeric NOT NULL,
    visual_prompt text NOT NULL,
    audio_script text,
    s3_anchor_image_key text,
    s3_raw_video_key text,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'generating', 'completed', 'failed')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT storyboard_scenes_pkey PRIMARY KEY (id),
    CONSTRAINT storyboard_scenes_project_id_fkey FOREIGN KEY (project_id)
        REFERENCES public.projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_storyboard_scenes_project
    ON public.storyboard_scenes(project_id);

CREATE INDEX IF NOT EXISTS idx_storyboard_scenes_check
    ON public.storyboard_scenes(check_id);


-- ─── 4. remediation_logs ─────────────────────────────────────────────────────
-- Version-control audit trail for each remediation attempt. Enables rollback
-- and debugging which strategy was applied to which asset.

CREATE TABLE IF NOT EXISTS public.remediation_logs (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    check_id text NOT NULL,
    agent_strategy text NOT NULL,
    modified_media_type text NOT NULL CHECK (modified_media_type IN ('text', 'image', 'audio', 'video')),
    previous_s3_key text,
    remediated_s3_key text,
    quality_score integer CHECK (quality_score >= 0 AND quality_score <= 100),
    attempt_number integer NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT remediation_logs_pkey PRIMARY KEY (id),
    CONSTRAINT remediation_logs_check_id_fkey FOREIGN KEY (check_id)
        REFERENCES public.compliance_checks(check_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_remediation_logs_check
    ON public.remediation_logs(check_id);
