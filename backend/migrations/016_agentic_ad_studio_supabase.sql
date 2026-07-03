-- ═══════════════════════════════════════════════════════════════════════════════
-- JusAds — Full Schema + Agentic Ad Studio (Consolidated, Single-File Setup)
--
-- Run this ONE file in the Supabase SQL Editor to build the entire database
-- from scratch, including the Agentic Ad Studio additions:
--   • chat_messages table (dedicated conversation persistence)
--   • generated_ads compliance columns (folded inline + ALTER for existing DBs)
--   • platform_rules seed for launch platforms (TikTok / Instagram / Shopee)
--
-- Safe to re-run: uses IF NOT EXISTS / ADD COLUMN IF NOT EXISTS /
-- ON CONFLICT DO NOTHING. Wrapped in a single transaction.
--
-- Table order respects foreign key dependencies.
-- ═══════════════════════════════════════════════════════════════════════════════

BEGIN;

-- ─── 1. users ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.users (
    email text NOT NULL,
    is_onboarded boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT users_pkey PRIMARY KEY (email)
);


-- ─── 1a. projects ────────────────────────────────────────────────────────────
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


-- ─── 1c. business_profiles ───────────────────────────────────────────────────
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


-- ─── 9. target_personas ──────────────────────────────────────────────────────
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


-- ─── 11. generated_ads (with Agentic Ad Studio compliance columns inline) ─────
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
    -- Agentic Ad Studio compliance tracking (Req 8.2, 8.4, 8.5, 11.2)
    compliance_status text NOT NULL DEFAULT 'non-final'
        CHECK (compliance_status IN ('final-compliant', 'final-non-compliant', 'non-final')),
    compliance_result jsonb,
    compliance_check_id text,
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

-- For databases where generated_ads already exists WITHOUT the compliance
-- columns, add them idempotently (no-op on fresh creates above).
ALTER TABLE public.generated_ads
    ADD COLUMN IF NOT EXISTS compliance_status text
        NOT NULL DEFAULT 'non-final'
        CHECK (compliance_status IN ('final-compliant', 'final-non-compliant', 'non-final')),
    ADD COLUMN IF NOT EXISTS compliance_result jsonb,
    ADD COLUMN IF NOT EXISTS compliance_check_id text;

CREATE INDEX IF NOT EXISTS idx_generated_ads_project
    ON public.generated_ads(project_id);

CREATE INDEX IF NOT EXISTS idx_generated_ads_task
    ON public.generated_ads(task_id);

CREATE INDEX IF NOT EXISTS idx_generated_ads_parent
    ON public.generated_ads(parent_ad_id);

CREATE INDEX IF NOT EXISTS idx_generated_ads_compliance_status
    ON public.generated_ads(compliance_status);


-- ─── 12. remediation_logs ────────────────────────────────────────────────────
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


-- ─── 13. chat_messages (Agentic Ad Studio — dedicated conversation store) ─────
-- One row per chat turn scoped to (project, task). Replaces storing history
-- inside tasks.pipeline_state JSON. The (project_id, task_id, created_at) index
-- supports the "last 20 ordered by timestamp" conversational-memory read.
CREATE TABLE IF NOT EXISTS public.chat_messages (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL,
    task_id uuid NOT NULL,
    role text NOT NULL CHECK (role IN ('user', 'assistant')),
    content text NOT NULL CHECK (char_length(content) <= 10000),
    attachments jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chat_messages_pkey PRIMARY KEY (id),
    CONSTRAINT chat_messages_project_fkey FOREIGN KEY (project_id)
        REFERENCES public.projects(id) ON DELETE CASCADE,
    CONSTRAINT chat_messages_task_fkey FOREIGN KEY (task_id)
        REFERENCES public.tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_project_task_created
    ON public.chat_messages(project_id, task_id, created_at);


-- ─── 14. Seed platform_rules for launch platforms (Req 7.2) ───────────────────
-- 12 rows: (TikTok, Instagram, Shopee) × (text, image, audio, video).
INSERT INTO public.platform_rules (platform, media_type, aspect_ratio, max_duration_seconds, max_file_size_mb, additional_rules)
VALUES
 -- Instagram (default platform)
 ('instagram', 'image', '1:1',  NULL, 30,   '{"max_dimension":1080}'),
 ('instagram', 'video', '9:16', 90,   100,  '{"max_dimension":1080}'),
 ('instagram', 'audio', '1:1',  90,   100,  '{"max_dimension":0}'),
 ('instagram', 'text',  '1:1',  NULL, NULL, '{"max_caption_chars":2200}'),
 -- TikTok
 ('tiktok',    'image', '9:16', NULL, 30,   '{"max_dimension":1080}'),
 ('tiktok',    'video', '9:16', 180,  100,  '{"max_dimension":1080}'),
 ('tiktok',    'audio', '9:16', 180,  100,  '{"max_dimension":0}'),
 ('tiktok',    'text',  '9:16', NULL, NULL, '{"max_caption_chars":2200}'),
 -- Shopee
 ('shopee',    'image', '1:1',  NULL, 30,   '{"max_dimension":1024}'),
 ('shopee',    'video', '1:1',  60,   100,  '{"max_dimension":1280}'),
 ('shopee',    'audio', '1:1',  60,   100,  '{"max_dimension":0}'),
 ('shopee',    'text',  '1:1',  NULL, NULL, '{"max_caption_chars":3000}')
ON CONFLICT (platform, media_type, aspect_ratio) DO NOTHING;

COMMIT;


-- ═══════════════════════════════════════════════════════════════════════════════
-- Verification (optional) — run after the script to confirm.
-- ═══════════════════════════════════════════════════════════════════════════════
-- SELECT count(*) AS platform_rule_rows FROM public.platform_rules;            -- expect >= 12
-- SELECT to_regclass('public.chat_messages') AS chat_messages_exists;          -- expect not null
-- SELECT column_name FROM information_schema.columns
--   WHERE table_name = 'generated_ads'
--     AND column_name IN ('compliance_status','compliance_result','compliance_check_id');
