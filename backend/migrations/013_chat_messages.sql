-- ═══════════════════════════════════════════════════════════════════════════════
-- Migration 013: chat_messages table
--
-- Dedicated persistence for the Agentic Ad Studio conversation, replacing the
-- prior approach of storing chat history inside tasks.pipeline_state JSON.
--
-- Each row is one chat turn (user or assistant) scoped to a (project, task).
-- The (project_id, task_id, created_at) index supports the "last 20 ordered by
-- timestamp" conversational-memory read.
--
-- Run in Supabase SQL Editor or via: psql $DATABASE_URL -f 013_chat_messages.sql
-- ═══════════════════════════════════════════════════════════════════════════════

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
