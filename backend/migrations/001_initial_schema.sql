-- ============================================================================
-- JusAds Complete Database Schema
-- Description: All tables for the JusAds compliance & creative workspace platform
-- Tables: projects, compliance_checks, violations, tasks
-- Last updated: 2025-06 — removed media_type constraint from projects,
--               added s3_segmented_key to compliance_checks,
--               tasks.reference_id is TEXT (not UUID) to match check_id format
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- Table: projects
-- A project groups related tasks (compliance checks and generation runs).
-- media_type is intentionally unconstrained — one project can contain tasks
-- of any type. The project name and creation date are the primary identifiers.
-- ============================================================================
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT NOT NULL,
    name TEXT NOT NULL CHECK (char_length(name) <= 255),
    media_type TEXT NOT NULL,  -- No constraint — can be any value (compliance, generation, mixed, etc.)
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================================
-- Table: compliance_checks
-- Stores one record per compliance analysis run.
-- media_type here is the actual uploaded asset type (text/image/audio/video).
-- risk_band and confidence are stored for fast querying without parsing result_json.
-- s3_upload_key, s3_segmented_key, s3_remix_key are now public S3 URLs (not keys).
-- ============================================================================
CREATE TABLE IF NOT EXISTS compliance_checks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    check_id TEXT UNIQUE NOT NULL,           -- 8-char hex identifier used in WebSocket routing
    user_id TEXT NOT NULL,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    media_type TEXT NOT NULL CHECK (media_type IN ('text', 'image', 'audio', 'video')),
    market TEXT NOT NULL,
    ethnicity TEXT NOT NULL,
    age_group TEXT NOT NULL,
    risk_percentage NUMERIC CHECK (risk_percentage >= 0 AND risk_percentage <= 100),
    risk_band TEXT,                          -- Low / Moderate / High / Critical
    confidence NUMERIC CHECK (confidence >= 0 AND confidence <= 100),
    status TEXT NOT NULL CHECK (status IN ('pending', 'checked', 'verified', 'edit_pending', 'remediated', 'remix_failed')),
    result_json JSONB,                       -- Full compliance result payload from the AI pipeline
    s3_upload_key TEXT,                      -- Public S3 URL for the original uploaded asset
    s3_segmented_key TEXT,                   -- Public S3 URL for the segmented violation overlay image
    s3_remix_key TEXT,                       -- Public S3 URL for the remixed/remediated asset
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_compliance_checks_created_at ON compliance_checks(created_at);
CREATE INDEX IF NOT EXISTS idx_compliance_checks_check_id ON compliance_checks(check_id);
CREATE INDEX IF NOT EXISTS idx_compliance_checks_user_id ON compliance_checks(user_id);
CREATE INDEX IF NOT EXISTS idx_compliance_checks_project_id ON compliance_checks(project_id);

-- ============================================================================
-- Table: violations
-- Individual violations detected within a compliance check.
-- Available only for video media type (clips extracted from timeline).
-- check_id references compliance_checks.check_id (TEXT foreign key).
-- ============================================================================
CREATE TABLE IF NOT EXISTS violations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    check_id TEXT NOT NULL REFERENCES compliance_checks(check_id) ON DELETE CASCADE,
    violation_index INTEGER NOT NULL,
    type TEXT NOT NULL,                      -- visual / audio / text
    severity TEXT NOT NULL,                  -- error / warning / info
    description TEXT CHECK (char_length(description) <= 2000),
    start_time NUMERIC,                      -- seconds (video/audio only)
    end_time NUMERIC,                        -- seconds (video/audio only)
    clip_s3_key TEXT,                        -- S3 URL for extracted video clip
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (check_id, violation_index)
);

-- ============================================================================
-- Table: tasks
-- Unified task history per project.
-- Compliance tasks: reference_id = compliance_checks.check_id (TEXT)
-- Generation tasks: pipeline_state = canvas graph JSON
-- pipeline_state for compliance tasks also stores the workflow step state:
--   { compliance_step, compliance_result, compliance_status, compliance_remix }
--   where compliance_status is one of: checked, reviewed, remixed, compared
-- ============================================================================
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN ('compliance', 'generation')),
    status TEXT NOT NULL,                    -- checked / reviewed / remixed / compared / saved
    summary TEXT,
    reference_id TEXT,                       -- compliance_checks.check_id for compliance tasks
    pipeline_state JSONB,                    -- canvas graph for generation; workflow state for compliance
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tasks_project_id ON tasks (project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks (created_at);
CREATE INDEX IF NOT EXISTS idx_tasks_project_created ON tasks (project_id, created_at DESC);
