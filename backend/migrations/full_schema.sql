-- ═══════════════════════════════════════════════════════════════════════════════
-- JusAds Full Database Schema
-- 
-- Single-file migration: run this once in Supabase SQL Editor to create
-- the entire database from scratch. Safe to re-run (uses IF NOT EXISTS).
--
-- Table order respects foreign key dependencies:
--   1. users (no FK)
--   1a. projects (no FK)
--   1b. project_members (FK → projects)
--   1c. business_profiles (no FK — linked by owner_email)
--   2. tasks (FK → projects)
--   3. compliance_checks (PK = task_id FK → tasks)
--   4. violations (FK → compliance_checks.task_id)
--   5. ad_policy_rules (no FK)
--   6. personas (no FK)
--   8. platform_rules (no FK)
--   9. chat_messages (FK → tasks)
--   10. storyboard_scenes (FK → projects, optional task_id)
--   11. generated_ads (FK → projects, tasks, self-referencing)
--   12. brand_voices (FK → projects)
--   13. remediation_versions / compliance_evaluations (FK → compliance_checks)
--
-- Legacy remediation_logs and post_statistics_cache are intentionally omitted:
-- neither is used by the application. Keep existing production rows until the
-- archival migration is approved; do not re-create either table on new installs.
-- ═══════════════════════════════════════════════════════════════════════════════


-- ─── 1. projects ─────────────────────────────────────────────────────────────
-- Container for tasks. No task_type here — tasks carry their own type.
-- owner_email is the creator; shared access via project_members table.

CREATE TABLE IF NOT EXISTS public.users (
    email text NOT NULL,
    is_onboarded boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    zernio_api_key text,
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


-- ─── 1c. business_profiles ───────────────────────────────────────────────────
-- Mandatory onboarding: what the user's company does, product category,
-- target platforms, and markets. Passed to AI for context-aware compliance.

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
    CONSTRAINT business_profiles_pkey PRIMARY KEY (id),
    CONSTRAINT business_profiles_private_key_values CHECK (COALESCE(logo_s3_key, '') !~* '^https?://')
);

CREATE INDEX IF NOT EXISTS idx_business_profiles_email
    ON public.business_profiles(owner_email);


-- ─── 2. tasks ─────────────────────────────────────────────────────────────────
-- Must be created before compliance_checks since compliance_checks.task_id → tasks.id

CREATE TABLE IF NOT EXISTS public.tasks (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL,
    type text NOT NULL CHECK (type IN ('compliance', 'generation')),
    status text NOT NULL,
    summary text,
    pipeline_state jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT tasks_pkey PRIMARY KEY (id),
    CONSTRAINT tasks_project_id_fkey FOREIGN KEY (project_id)
        REFERENCES public.projects(id) ON DELETE CASCADE
);


-- ─── 3. compliance_checks ────────────────────────────────────────────────────
-- One-to-one extension of a compliance task. task_id is both PK and FK.

CREATE TABLE IF NOT EXISTS public.compliance_checks (
    task_id uuid NOT NULL,
    project_id uuid NOT NULL,
    media_type text NOT NULL CHECK (media_type IN ('text', 'image', 'audio', 'video')),
    market text NOT NULL,
    ethnicity text NOT NULL,
    age_group text NOT NULL,
    platform text NOT NULL DEFAULT 'general',
    risk_percentage numeric CHECK (risk_percentage >= 0 AND risk_percentage <= 100),
    status text NOT NULL CHECK (status IN (
        'pending', 'checked', 'verified', 'edit_pending', 'remix_failed',
        'pass', 'critical_regen', 'remediate', 'queued', 'processing',
        'pending_recheck', 'rechecking', 'verified_compliant',
        'verified_non_compliant', 'generation_failed', 'recheck_error',
        'cancelled'
    )),
    result_json jsonb,
    s3_upload_key text,
    s3_segmented_key text,
    s3_remix_key text,
    remediation_metadata jsonb,
    current_remediation_version_id uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT compliance_checks_pkey PRIMARY KEY (task_id),
    CONSTRAINT compliance_checks_task_id_fkey FOREIGN KEY (task_id)
        REFERENCES public.tasks(id) ON DELETE CASCADE,
    CONSTRAINT compliance_checks_project_id_fkey FOREIGN KEY (project_id)
        REFERENCES public.projects(id) ON DELETE CASCADE,
    CONSTRAINT compliance_checks_private_key_values CHECK (
        COALESCE(s3_upload_key, '') !~* '^https?://'
        AND COALESCE(s3_segmented_key, '') !~* '^https?://'
        AND COALESCE(s3_remix_key, '') !~* '^https?://'
    )
);


-- ─── 4. violations ───────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.violations (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    task_id uuid NOT NULL,
    violation_index integer NOT NULL,
    type text NOT NULL,
    severity text NOT NULL,
    description text CHECK (char_length(description) <= 2000),
    start_time numeric,
    end_time numeric,
    clip_s3_key text,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT violations_pkey PRIMARY KEY (id),
    CONSTRAINT violations_task_id_fkey FOREIGN KEY (task_id)
        REFERENCES public.compliance_checks(task_id) ON DELETE CASCADE,
    CONSTRAINT violations_private_key_values CHECK (COALESCE(clip_s3_key, '') !~* '^https?://')
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
    evidence_urls jsonb NOT NULL DEFAULT '[]',
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


-- ─── 7. platform_rules ───────────────────────────────────────────────────────
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


-- ─── 9. chat_messages ─────────────────────────────────────────────────────
-- Stores chat conversation turns between user and AI generation agent.

CREATE TABLE IF NOT EXISTS public.chat_messages (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL,
    task_id uuid NOT NULL,
    role text NOT NULL CHECK (role IN ('user', 'assistant')),
    content text NOT NULL,
    attachments jsonb NOT NULL DEFAULT '[]',
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chat_messages_pkey PRIMARY KEY (id),
    CONSTRAINT chat_messages_task_fkey FOREIGN KEY (task_id)
        REFERENCES public.tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_task
    ON public.chat_messages(project_id, task_id);

CREATE INDEX IF NOT EXISTS idx_chat_messages_created
    ON public.chat_messages(task_id, created_at);


-- ─── 10. storyboard_scenes ───────────────────────────────────────────────────
-- Per-cut tracking for multi-scene video generation. Resume on timeout.

CREATE INDEX IF NOT EXISTS idx_storyboard_scenes_project
    ON public.storyboard_scenes(project_id);

CREATE INDEX IF NOT EXISTS idx_storyboard_scenes_task
    ON public.storyboard_scenes(task_id);


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
    -- Output classification and version lineage. References must not be mixed
    -- into the generated-output gallery.
    asset_role text NOT NULL DEFAULT 'output'
        CHECK (asset_role IN ('output', 'reference', 'intermediate')),
    generation_mode text NOT NULL DEFAULT 'advanced',
    version_number integer NOT NULL DEFAULT 1 CHECK (version_number > 0),
    -- Explicit, queryable audience context. `market` is the target country /
    -- market (for example `malaysia`); do not add a duplicate nationality field.
    market text,
    ethnicity text,
    age_group text,
    target_language text,
    -- Immutable snapshots let a regenerated/versioned asset be reproduced with
    -- the exact persona, localisation rules and company brand theme used then.
    generation_context jsonb NOT NULL DEFAULT '{}',
    brand_snapshot jsonb NOT NULL DEFAULT '{}',
    localization_snapshot jsonb NOT NULL DEFAULT '{}',
    -- Free-form operational details only (provider response, dimensions, etc.).
    metadata jsonb NOT NULL DEFAULT '{}',
    -- Compliance (written by compliance_bridge after generation)
    compliance_status text,
    compliance_result jsonb,
    compliance_task_id uuid,
    -- Distribution (written after Zernio push)
    distributed_at timestamptz,
    distribution_platform text,
    distribution_post_id text,
    -- CapCut and rendered deliverables for video workflows.
    s3_draft_key text,
    s3_rendered_key text,
    --
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT generated_ads_pkey PRIMARY KEY (id),
    CONSTRAINT generated_ads_project_id_fkey FOREIGN KEY (project_id)
        REFERENCES public.projects(id) ON DELETE CASCADE,
    CONSTRAINT generated_ads_task_id_fkey FOREIGN KEY (task_id)
        REFERENCES public.tasks(id) ON DELETE SET NULL,
    CONSTRAINT generated_ads_parent_fkey FOREIGN KEY (parent_ad_id)
        REFERENCES public.generated_ads(id) ON DELETE SET NULL,
    CONSTRAINT generated_ads_private_key_values CHECK (
        COALESCE(s3_media_key, '') !~* '^https?://'
        AND COALESCE(s3_draft_key, '') !~* '^https?://'
        AND COALESCE(s3_rendered_key, '') !~* '^https?://'
    )
);

CREATE INDEX IF NOT EXISTS idx_generated_ads_project
    ON public.generated_ads(project_id);

CREATE INDEX IF NOT EXISTS idx_generated_ads_task
    ON public.generated_ads(task_id);

CREATE INDEX IF NOT EXISTS idx_generated_ads_parent
    ON public.generated_ads(parent_ad_id);


-- ─── 12. remediation_logs ────────────────────────────────────────────────────
-- ─── 13. brand_voices ────────────────────────────────────────────────────────
-- Voice catalog + custom clones for brand-consistent audio.
-- Global voices (project_id IS NULL) are available to all users.
-- Custom clones (project_id set) are project-specific and cleaned up on delete.

CREATE TABLE IF NOT EXISTS public.brand_voices (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    project_id uuid,
    voice_id text NOT NULL,
    voice_name text NOT NULL,
    description text,
    -- Private object key only; the API issues authorized short-lived URLs.
    sample_s3_key text CHECK (COALESCE(sample_s3_key, '') !~* '^https?://'),
    market text,
    ethnicity text,
    gender text DEFAULT 'female',
    language_code text DEFAULT 'ms',
    is_custom_clone boolean NOT NULL DEFAULT false,
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'deleted')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT brand_voices_pkey PRIMARY KEY (id),
    CONSTRAINT brand_voices_project_fkey FOREIGN KEY (project_id)
        REFERENCES public.projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_brand_voices_project
    ON public.brand_voices(project_id);

CREATE INDEX IF NOT EXISTS idx_brand_voices_global
    ON public.brand_voices(market, ethnicity, gender)
    WHERE project_id IS NULL AND status = 'active';


-- ═══════════════════════════════════════════════════════════════════════════════
-- Migration 020: Research & Intelligence Layer
-- ═══════════════════════════════════════════════════════════════════════════════


-- ─── 14. trends_cache ────────────────────────────────────────────────────────
-- Stores scraped trending content from Apify actors (weekly refresh).

CREATE TABLE IF NOT EXISTS public.trends_cache (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    platform text NOT NULL CHECK (platform IN ('tiktok', 'instagram', 'youtube', 'facebook_ads')),
    content_type text NOT NULL,
    title text NOT NULL,
    evidence_urls jsonb NOT NULL DEFAULT '[]',
    url text NOT NULL,
    engagement_metrics jsonb NOT NULL DEFAULT '{}',
    hashtags text[] DEFAULT '{}',
    categories text[] DEFAULT '{}',
    cultural_event_tag text,
    market text NOT NULL DEFAULT 'malaysia',
    scraped_at timestamptz NOT NULL DEFAULT now(),
    scrape_batch_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    owner_email text,
    CONSTRAINT trends_cache_pkey PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_trends_cache_platform
    ON public.trends_cache(platform);
CREATE INDEX IF NOT EXISTS idx_trends_cache_market
    ON public.trends_cache(market);
CREATE INDEX IF NOT EXISTS idx_trends_cache_scraped_at
    ON public.trends_cache(scraped_at DESC);
CREATE INDEX IF NOT EXISTS idx_trends_cache_event
    ON public.trends_cache(cultural_event_tag)
    WHERE cultural_event_tag IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_trends_cache_batch
    ON public.trends_cache(scrape_batch_id);

-- ─── 14b. youtube_hook_reference_cache ─────────────────────────────────────
-- Company-context YouTube Shorts references.  Backend-only cache; public
-- results are advisory creative inspiration, never an ad/compliance verdict.
CREATE TABLE IF NOT EXISTS public.youtube_hook_reference_cache (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_email text NOT NULL,
    market text NOT NULL DEFAULT 'malaysia',
    profile_fingerprint char(64) NOT NULL,
    query_text text NOT NULL,
    results jsonb NOT NULL DEFAULT '[]'::jsonb,
    fetched_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT youtube_hook_reference_cache_scope_unique UNIQUE (owner_email, market, profile_fingerprint),
    CONSTRAINT youtube_hook_reference_cache_results_array CHECK (jsonb_typeof(results) = 'array')
);
CREATE INDEX IF NOT EXISTS idx_youtube_hook_reference_cache_expiry
    ON public.youtube_hook_reference_cache(owner_email, market, expires_at DESC);
ALTER TABLE public.youtube_hook_reference_cache ENABLE ROW LEVEL SECURITY;


-- ─── 15. cultural_events ─────────────────────────────────────────────────────
-- Reference list of known cultural, religious, and global events per market.

CREATE TABLE IF NOT EXISTS public.cultural_events (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    name text NOT NULL,
    market text NOT NULL,
    start_date date NOT NULL,
    end_date date NOT NULL,
    event_type text NOT NULL CHECK (event_type IN ('religious', 'festive', 'sports', 'national', 'global')),
    tags text[] DEFAULT '{}',
    impact_score integer CHECK (impact_score >= 0 AND impact_score <= 100),
    source text NOT NULL DEFAULT 'manual',
    source_event_id text,
    source_updated_at timestamptz,
    source_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    last_synced_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT cultural_events_pkey PRIMARY KEY (id),
    CONSTRAINT cultural_events_source_event_unique UNIQUE (source, source_event_id)
);

CREATE INDEX IF NOT EXISTS idx_cultural_events_market_date
    ON public.cultural_events(market, start_date);
CREATE INDEX IF NOT EXISTS idx_cultural_events_type
    ON public.cultural_events(event_type);
CREATE INDEX IF NOT EXISTS idx_cultural_events_source_sync
    ON public.cultural_events(source, last_synced_at DESC);
CREATE INDEX IF NOT EXISTS idx_cultural_events_source_end_date
    ON public.cultural_events(source, end_date);


-- ─── 16. post_statistics_cache ───────────────────────────────────────────────
-- ─── 17. tavily_usage_log ────────────────────────────────────────────────────
-- Audit log for Tavily API invocations (cost monitoring).

CREATE INDEX IF NOT EXISTS idx_tavily_usage_task
    ON public.tavily_usage_log(task_id);
CREATE INDEX IF NOT EXISTS idx_tavily_usage_time
    ON public.tavily_usage_log(invoked_at DESC);


-- Daily trend intelligence. These tables are actively queried by the director
-- and daily-idea services; they are not optional cache decorations.
CREATE TABLE IF NOT EXISTS public.creative_trend_signals (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_type text NOT NULL CHECK (signal_type IN ('sound', 'music', 'dance_or_challenge', 'hook', 'meme_or_phrase', 'format_or_template', 'visual_style', 'creator_behavior', 'hashtag_or_topic', 'seasonal_or_cultural_moment')),
    title text NOT NULL,
    evidence_urls jsonb NOT NULL DEFAULT '[]',
    summary text NOT NULL,
    why_trending text,
    how_it_works text,
    suggested_adaptation text NOT NULL,
    do_not_do text,
    target_platforms text[] NOT NULL DEFAULT '{}',
    market text NOT NULL DEFAULT 'malaysia',
    owner_email text,
    audience text,
    language text,
    momentum text NOT NULL DEFAULT 'unknown' CHECK (momentum IN ('rising', 'peaking', 'stable', 'declining', 'unknown')),
    confidence text NOT NULL DEFAULT 'low' CHECK (confidence IN ('low', 'medium', 'high')),
    detected_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.daily_creative_ideas (
    idea_date date NOT NULL,
    market text NOT NULL DEFAULT 'malaysia',
    payload jsonb NOT NULL,
    generated_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (idea_date, market)
);

CREATE TABLE IF NOT EXISTS public.hook_preferences (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id text NOT NULL,
    video_id text NOT NULL,
    tags jsonb NOT NULL DEFAULT '[]',
    creative_style text NOT NULL DEFAULT 'meme_shock',
    product_category text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT hook_preferences_user_video_unique UNIQUE (user_id, video_id)
);


-- Immutable remediation state machine. A generated edit remains pending until
-- one of its append-only evaluations passes; it is never "compliant by edit".
CREATE TABLE IF NOT EXISTS public.remediation_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id uuid NOT NULL REFERENCES public.compliance_checks(task_id) ON DELETE CASCADE,
    version_number integer NOT NULL CHECK (version_number > 0),
    parent_version_id uuid REFERENCES public.remediation_versions(id),
    idempotency_key text NOT NULL CHECK (char_length(idempotency_key) BETWEEN 1 AND 200),
    status text NOT NULL CHECK (status IN ('queued', 'processing', 'pending_recheck', 'rechecking', 'verified_compliant', 'verified_non_compliant', 'generation_failed', 'recheck_error', 'cancelled')),
    media_type text NOT NULL CHECK (media_type IN ('text', 'image', 'audio', 'video')),
    source_asset_key text CHECK (source_asset_key IS NULL OR source_asset_key !~* '^https?://'),
    asset_key text CHECK (asset_key IS NULL OR asset_key !~* '^https?://'),
    asset_sha256 text CHECK (asset_sha256 IS NULL OR asset_sha256 ~ '^[0-9a-f]{64}$'),
    asset_size_bytes bigint CHECK (asset_size_bytes IS NULL OR asset_size_bytes >= 0),
    content_type text,
    agent_strategy text NOT NULL DEFAULT '',
    policy_version text NOT NULL DEFAULT '',
    rule_version text NOT NULL DEFAULT '',
    model_provider text NOT NULL DEFAULT '',
    model_name text NOT NULL DEFAULT '',
    model_version text NOT NULL DEFAULT '',
    prompt_template_version text NOT NULL DEFAULT '',
    prompt_inputs jsonb NOT NULL DEFAULT '{}',
    generation_metadata jsonb NOT NULL DEFAULT '{}',
    created_by_subject text NOT NULL,
    failure_code text,
    created_at timestamptz NOT NULL DEFAULT now(),
    generation_started_at timestamptz NOT NULL DEFAULT now(),
    generated_at timestamptz,
    recheck_started_at timestamptz,
    recheck_completed_at timestamptz,
    verified_at timestamptz,
    CONSTRAINT remediation_versions_task_number_unique UNIQUE (task_id, version_number),
    CONSTRAINT remediation_versions_idempotency_unique UNIQUE (task_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_remediation_versions_task_created ON public.remediation_versions(task_id, created_at DESC);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'compliance_checks_current_remediation_version_id_fkey'
          AND conrelid = 'public.compliance_checks'::regclass
    ) THEN
        ALTER TABLE public.compliance_checks
            ADD CONSTRAINT compliance_checks_current_remediation_version_id_fkey
            FOREIGN KEY (current_remediation_version_id) REFERENCES public.remediation_versions(id);
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS public.compliance_evaluations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    remediation_version_id uuid NOT NULL REFERENCES public.remediation_versions(id) ON DELETE CASCADE,
    attempt_number integer NOT NULL CHECK (attempt_number > 0),
    idempotency_key text NOT NULL CHECK (char_length(idempotency_key) BETWEEN 1 AND 200),
    status text NOT NULL CHECK (status IN ('passed', 'failed', 'error')),
    verdict text,
    risk_percentage numeric CHECK (risk_percentage IS NULL OR (risk_percentage >= 0 AND risk_percentage <= 100)),
    result_json jsonb NOT NULL DEFAULT '{}',
    policy_version text NOT NULL,
    rule_version text NOT NULL,
    model_provider text NOT NULL DEFAULT '',
    model_name text NOT NULL DEFAULT '',
    model_version text NOT NULL DEFAULT '',
    error_code text,
    started_at timestamptz NOT NULL,
    completed_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT compliance_evaluations_attempt_unique UNIQUE (remediation_version_id, attempt_number),
    CONSTRAINT compliance_evaluations_idempotency_unique UNIQUE (remediation_version_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_compliance_evaluations_version_created ON public.compliance_evaluations(remediation_version_id, created_at DESC);

CREATE TABLE IF NOT EXISTS public.remediation_recheck_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    remediation_version_id uuid NOT NULL UNIQUE REFERENCES public.remediation_versions(id) ON DELETE CASCADE,
    status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
    attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    available_at timestamptz NOT NULL DEFAULT now(),
    claimed_at timestamptz,
    completed_at timestamptz,
    last_error_code text,
    created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.remediation_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.compliance_evaluations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.remediation_recheck_jobs ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.remediation_versions, public.compliance_evaluations, public.remediation_recheck_jobs FROM PUBLIC, anon, authenticated;
GRANT ALL ON TABLE public.remediation_versions, public.compliance_evaluations, public.remediation_recheck_jobs TO service_role;

-- Operational audit view for accidental URL persistence. It has no client-role
-- access; production URLs must always be presigned after backend authorization.
CREATE OR REPLACE VIEW public.private_media_url_audit
WITH (security_invoker = true) AS
SELECT 'compliance_checks.s3_upload_key'::text AS field_name, task_id::text AS record_id, s3_upload_key::text AS value
FROM public.compliance_checks WHERE s3_upload_key ~* '^https?://'
UNION ALL
SELECT 'compliance_checks.s3_segmented_key', task_id::text, s3_segmented_key::text
FROM public.compliance_checks WHERE s3_segmented_key ~* '^https?://'
UNION ALL
SELECT 'compliance_checks.s3_remix_key', task_id::text, s3_remix_key::text
FROM public.compliance_checks WHERE s3_remix_key ~* '^https?://'
UNION ALL
SELECT 'storyboard_scenes.s3_anchor_image_key', id::text, s3_anchor_image_key::text
FROM public.storyboard_scenes WHERE s3_anchor_image_key ~* '^https?://'
UNION ALL
SELECT 'storyboard_scenes.s3_raw_video_key', id::text, s3_raw_video_key::text
FROM public.storyboard_scenes WHERE s3_raw_video_key ~* '^https?://'
UNION ALL
SELECT 'generated_ads.s3_media_key', id::text, s3_media_key::text
FROM public.generated_ads WHERE s3_media_key ~* '^https?://'
UNION ALL
SELECT 'brand_voices.sample_s3_key', id::text, sample_s3_key::text
FROM public.brand_voices WHERE sample_s3_key ~* '^https?://';
REVOKE ALL ON TABLE public.private_media_url_audit FROM PUBLIC, anon, authenticated;
GRANT SELECT ON TABLE public.private_media_url_audit TO service_role;


-- ─── ALTER generated_ads — CapCut dual output columns ────────────────────────

