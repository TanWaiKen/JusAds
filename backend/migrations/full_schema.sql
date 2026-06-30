-- ═══════════════════════════════════════════════════════════════════════════════
-- JusAds Full Database Schema
-- 
-- Single-file migration: run this once in Supabase SQL Editor to create
-- the entire database from scratch. Safe to re-run (uses IF NOT EXISTS).
--
-- Table order respects foreign key dependencies:
--   1. projects (no FK)
--   1b. project_members (FK → projects)
--   2. compliance_checks (FK → projects)
--   3. violations (FK → compliance_checks)
--   4. tasks (FK → projects)
--   5. ad_policy_rules (no FK)
--   6. personas (no FK)
--   7. pipeline_progress (FK → compliance_checks)
--   8. platform_rules (no FK)
--   9. target_personas (no FK)
--   10. storyboard_scenes (FK → projects)
--   11. generated_ads (FK → projects, tasks, self-referencing)
--   12. remediation_logs (FK → compliance_checks)
-- ═══════════════════════════════════════════════════════════════════════════════


-- ─── 1. projects ─────────────────────────────────────────────────────────────
-- Container for tasks. No task_type here — tasks carry their own type.
-- owner_email is the creator; shared access via project_members table.

CREATE TABLE IF NOT EXISTS public.projects (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    owner_email text NOT NULL,
    name text NOT NULL CHECK (char_length(name) <= 255),
    description text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT projects_pkey PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_projects_owner
    ON public.projects(owner_email);


-- ─── 1b. project_members ─────────────────────────────────────────────────────
-- Grants access to other users. The owner always has full access implicitly.

CREATE TABLE IF NOT EXISTS public.project_members (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL,
    email text NOT NULL,
    role text NOT NULL DEFAULT 'viewer' CHECK (role IN ('viewer', 'editor', 'admin')),
    invited_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT project_members_pkey PRIMARY KEY (id),
    CONSTRAINT project_members_project_fkey FOREIGN KEY (project_id)
        REFERENCES public.projects(id) ON DELETE CASCADE,
    CONSTRAINT project_members_unique UNIQUE (project_id, email)
);

CREATE INDEX IF NOT EXISTS idx_project_members_email
    ON public.project_members(email);


-- ─── 2. compliance_checks ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.compliance_checks (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    check_id text NOT NULL UNIQUE,
    user_email text NOT NULL,
    project_id uuid NOT NULL,
    media_type text NOT NULL CHECK (media_type IN ('text', 'image', 'audio', 'video')),
    market text NOT NULL,
    ethnicity text NOT NULL,
    age_group text NOT NULL,
    platform text NOT NULL DEFAULT 'general',
    risk_percentage numeric CHECK (risk_percentage >= 0 AND risk_percentage <= 100),
    status text NOT NULL CHECK (status IN ('pending', 'checked', 'verified', 'edit_pending', 'remediated', 'remix_failed', 'pass', 'critical_regen', 'remediate')),
    result_json jsonb,
    s3_upload_key text,
    s3_segmented_key text,
    s3_remix_key text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT compliance_checks_pkey PRIMARY KEY (id),
    CONSTRAINT compliance_checks_project_id_fkey FOREIGN KEY (project_id)
        REFERENCES public.projects(id) ON DELETE CASCADE
);


-- ─── 3. violations ───────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.violations (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    check_id text NOT NULL,
    violation_index integer NOT NULL,
    type text NOT NULL,
    severity text NOT NULL,
    description text CHECK (char_length(description) <= 2000),
    start_time numeric,
    end_time numeric,
    clip_s3_key text,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT violations_pkey PRIMARY KEY (id),
    CONSTRAINT violations_check_id_fkey FOREIGN KEY (check_id)
        REFERENCES public.compliance_checks(check_id) ON DELETE CASCADE
);


-- ─── 4. tasks ────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.tasks (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL,
    type text NOT NULL CHECK (type IN ('compliance', 'generation')),
    status text NOT NULL,
    summary text,
    reference_id text,
    pipeline_state jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT tasks_pkey PRIMARY KEY (id),
    CONSTRAINT tasks_project_id_fkey FOREIGN KEY (project_id)
        REFERENCES public.projects(id) ON DELETE CASCADE
);


-- ─── 5. ad_policy_rules ──────────────────────────────────────────────────────
-- Replaces Qdrant vector DB. Stores raw regulatory text from CSV dataset.

CREATE TABLE IF NOT EXISTS public.ad_policy_rules (
    id text PRIMARY KEY,
    source text NOT NULL,
    regulator text NOT NULL,
    framework text NOT NULL,
    category text NOT NULL,
    rule_title text NOT NULL,
    rule_text text NOT NULL,
    applies_to text NOT NULL,
    enforcement text NOT NULL,
    effective_date date NOT NULL,
    last_updated date NOT NULL,
    tags text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ad_policy_rules_source
    ON public.ad_policy_rules(source);

CREATE INDEX IF NOT EXISTS idx_ad_policy_rules_regulator
    ON public.ad_policy_rules(regulator);

CREATE INDEX IF NOT EXISTS idx_ad_policy_rules_category
    ON public.ad_policy_rules(category);

CREATE INDEX IF NOT EXISTS idx_ad_policy_rules_effective_date
    ON public.ad_policy_rules(effective_date);


-- ─── 6. personas ─────────────────────────────────────────────────────────────
-- Full persona JSONB blobs from malaysia_personas.json / singapore_personas.json

CREATE TABLE IF NOT EXISTS public.personas (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    market text NOT NULL,
    ethnicity text NOT NULL,
    age_group text NOT NULL,
    persona_data jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(market, ethnicity, age_group)
);

CREATE INDEX IF NOT EXISTS idx_personas_market
    ON public.personas(market);

CREATE INDEX IF NOT EXISTS idx_personas_ethnicity
    ON public.personas(ethnicity);

CREATE INDEX IF NOT EXISTS idx_personas_market_ethnicity
    ON public.personas(market, ethnicity);


-- ─── 7. pipeline_progress ────────────────────────────────────────────────────
-- Frontend polls this instead of WebSocket. Each pipeline node writes here.

CREATE TABLE IF NOT EXISTS public.pipeline_progress (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    check_id text NOT NULL,
    step_name text NOT NULL,
    status text NOT NULL CHECK (status IN ('running', 'completed', 'error')),
    message text CHECK (char_length(message) <= 1000),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pipeline_progress_pkey PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_pipeline_progress_check_id
    ON public.pipeline_progress(check_id);

-- Auto-update updated_at trigger
CREATE OR REPLACE FUNCTION update_pipeline_progress_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_pipeline_progress_updated_at ON public.pipeline_progress;
CREATE TRIGGER trg_pipeline_progress_updated_at
    BEFORE UPDATE ON public.pipeline_progress
    FOR EACH ROW
    EXECUTE FUNCTION update_pipeline_progress_updated_at();


-- ─── 8. platform_rules ───────────────────────────────────────────────────────
-- Platform-specific format requirements (aspect ratio, duration, file size).

CREATE TABLE IF NOT EXISTS public.platform_rules (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    platform text NOT NULL,
    media_type text NOT NULL CHECK (media_type IN ('text', 'image', 'audio', 'video')),
    aspect_ratio text NOT NULL,
    max_duration_seconds integer,
    max_file_size_mb integer,
    additional_rules jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT platform_rules_pkey PRIMARY KEY (id),
    CONSTRAINT platform_rules_unique UNIQUE (platform, media_type, aspect_ratio)
);


-- ─── 9. target_personas ─────────────────────────────────────────────────────
-- Structured persona constraints for Judges Agent bias checks.

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


-- ─── 10. storyboard_scenes ───────────────────────────────────────────────────
-- Per-cut tracking for multi-scene video generation. Resume on timeout.

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


-- ─── 11. generated_ads ────────────────────────────────────────────────────────
-- Stores outputs from the ads generation pipeline. One row per generated asset.
-- A single campaign post (e.g. Instagram) links multiple assets: a video/image
-- plus its caption text, plus optional voiceover audio.

CREATE TABLE IF NOT EXISTS public.generated_ads (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL,
    task_id uuid,
    media_type text NOT NULL CHECK (media_type IN ('text', 'image', 'audio', 'video')),
    platform text NOT NULL,
    caption text,
    prompt_used text,
    s3_media_key text,
    parent_ad_id uuid,
    status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'generating', 'completed', 'failed', 'published')),
    metadata jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT generated_ads_pkey PRIMARY KEY (id),
    CONSTRAINT generated_ads_project_id_fkey FOREIGN KEY (project_id)
        REFERENCES public.projects(id) ON DELETE CASCADE,
    CONSTRAINT generated_ads_task_id_fkey FOREIGN KEY (task_id)
        REFERENCES public.tasks(id) ON DELETE SET NULL,
    CONSTRAINT generated_ads_parent_fkey FOREIGN KEY (parent_ad_id)
        REFERENCES public.generated_ads(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_generated_ads_project
    ON public.generated_ads(project_id);

CREATE INDEX IF NOT EXISTS idx_generated_ads_task
    ON public.generated_ads(task_id);

CREATE INDEX IF NOT EXISTS idx_generated_ads_parent
    ON public.generated_ads(parent_ad_id);


-- ─── 12. remediation_logs ────────────────────────────────────────────────────
-- Audit trail for each remediation attempt. Enables rollback.

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
