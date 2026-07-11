-- Migration 019: Schema cleanup
-- 1. Remove target_personas table (redundant — personas table covers this)
-- 2. Remove user_email from compliance_checks (use project ownership instead)
-- 3. Add chat_messages table (already exists in production, adding to schema)
-- 4. Add remediation_metadata to compliance_checks

-- Drop target_personas (data merged into personas table)
DROP TABLE IF EXISTS public.target_personas;

-- Remove user_email from compliance_checks (nullable first, then drop)
ALTER TABLE public.compliance_checks
DROP COLUMN IF EXISTS user_email;

-- Add remediation_metadata column
ALTER TABLE public.compliance_checks
ADD COLUMN IF NOT EXISTS remediation_metadata jsonb;

-- Create chat_messages table if not exists
CREATE TABLE IF NOT EXISTS public.chat_messages (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL,
    task_id uuid NOT NULL,
    role text NOT NULL CHECK (role IN ('user', 'assistant')),
    content text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chat_messages_pkey PRIMARY KEY (id),
    CONSTRAINT chat_messages_task_fkey FOREIGN KEY (task_id)
        REFERENCES public.tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_task
    ON public.chat_messages(project_id, task_id);

CREATE INDEX IF NOT EXISTS idx_chat_messages_created
    ON public.chat_messages(task_id, created_at);

COMMENT ON TABLE public.chat_messages IS 'Chat conversation turns between user and AI generation agent per task';
