-- ═══════════════════════════════════════════════════════════════════════════════
-- Migration 015: Seed platform_rules for launch platforms
--
-- Seeds one row per (platform, media_type) for the three launch platforms
-- (TikTok, Instagram, Shopee) across the four media types (text, image,
-- audio, video) — 12 rows total. Each row carries an aspect ratio, max
-- duration, max file size, and additional_rules.max_dimension. Text rows
-- carry a caption-length convention instead of duration/dimension limits.
--
-- The platform_rules.py resolution layer reads a single rule per
-- (platform, media_type); missing combinations cause MissingRuleError (Req 7.7).
--
-- Idempotent: ON CONFLICT on the (platform, media_type, aspect_ratio) unique
-- constraint does nothing, so re-running this migration is safe.
--
-- Requirements: 7.2
-- Run in Supabase SQL Editor or via: psql $DATABASE_URL -f 015_seed_platform_rules.sql
-- ═══════════════════════════════════════════════════════════════════════════════

-- Guard: ensure the table exists (defined in 003_pipeline_cleanup.sql / full_schema.sql).
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


-- ─── Seed: launch platform format rules ──────────────────────────────────────
INSERT INTO public.platform_rules (platform, media_type, aspect_ratio, max_duration_seconds, max_file_size_mb, additional_rules)
VALUES
 -- Instagram (default platform — Req 7.5)
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
