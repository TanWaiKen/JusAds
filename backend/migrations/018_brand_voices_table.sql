-- Migration 018: Brand Voices table for persistent voice cloning
-- Part of: Intelligent Remediation Engine (Phase R1/R2)

CREATE TABLE IF NOT EXISTS public.brand_voices (
    id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    project_id      uuid NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    voice_id        text NOT NULL,          -- ElevenLabs voice_id
    voice_name      text NOT NULL,          -- Human-readable name
    description     text,                   -- Voice characteristics
    sample_url      text,                   -- S3 URL of original sample
    status          text NOT NULL DEFAULT 'active',  -- active | deleted
    created_at      timestamptz DEFAULT now(),
    updated_at      timestamptz DEFAULT now(),
    UNIQUE(project_id)                      -- One voice per project
);

-- Index for quick lookup by project
CREATE INDEX IF NOT EXISTS idx_brand_voices_project_id ON public.brand_voices(project_id);

-- Add remediation_metadata column to compliance_checks for tracking tool routing decisions
ALTER TABLE public.compliance_checks
ADD COLUMN IF NOT EXISTS remediation_metadata jsonb;

COMMENT ON TABLE public.brand_voices IS 'Persistent ElevenLabs voice clones for brand-consistent audio remediation';
COMMENT ON COLUMN public.brand_voices.voice_id IS 'ElevenLabs cloned voice ID — reused across all future ads for this project';
COMMENT ON COLUMN public.compliance_checks.remediation_metadata IS 'AI Tool Router decision + execution results (severity, tools applied, confidence)';
