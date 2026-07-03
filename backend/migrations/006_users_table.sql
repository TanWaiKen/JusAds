-- ═══════════════════════════════════════════════════════════════════════════════
-- Migration 006: Users table (minimal — email as PK + is_onboarded flag)
-- 
-- All other user info (name, avatar) comes from Cognito via useAuth.
-- This table only tracks: does this email exist + have they onboarded.
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.users (
    email text NOT NULL,
    is_onboarded boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT users_pkey PRIMARY KEY (email)
);
