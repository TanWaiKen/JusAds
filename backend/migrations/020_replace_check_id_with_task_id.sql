-- ═══════════════════════════════════════════════════════════════════════════════
-- Migration 020: Replace check_id with task_id in compliance_checks & violations
--
-- Rationale:
--   compliance_checks had two identifiers (id uuid PK + check_id text UNIQUE).
--   This was redundant. Additionally, tasks.reference_id was used to link tasks
--   to compliance_checks by storing the check_id value.
--
-- Changes:
--   1. compliance_checks: drop id (uuid), drop check_id (text)
--      → add task_id (uuid PK, FK → tasks.id)
--   2. violations: rename check_id → task_id (uuid FK → compliance_checks.task_id)
--   3. pipeline_progress: rename check_id → task_id
--   4. remediation_logs: rename check_id → task_id
--   5. storyboard_scenes: rename check_id → task_id
--   6. generated_ads: rename compliance_check_id → compliance_task_id
--   7. tasks: drop reference_id column (no longer needed)
--
-- Run in Supabase SQL Editor or via: psql $DATABASE_URL -f 020_replace_check_id_with_task_id.sql
-- ═══════════════════════════════════════════════════════════════════════════════

-- WARNING: This is a DESTRUCTIVE migration. Back up your data before running.
-- This migration assumes compliance_checks rows have a corresponding task with
-- reference_id = check_id. If orphan rows exist, they will be lost.

BEGIN;

-- Step 1: Add task_id column to compliance_checks (nullable for now)
ALTER TABLE public.compliance_checks
    ADD COLUMN task_id uuid;

-- Step 2: Populate task_id by joining tasks.reference_id = compliance_checks.check_id
UPDATE public.compliance_checks cc
SET task_id = t.id
FROM public.tasks t
WHERE t.reference_id = cc.check_id
  AND t.type = 'compliance';

-- Step 3: Remove rows that have no corresponding task (orphans)
DELETE FROM public.compliance_checks WHERE task_id IS NULL;

-- Step 4: Drop old constraints and columns from compliance_checks
ALTER TABLE public.compliance_checks DROP CONSTRAINT IF EXISTS compliance_checks_pkey;
ALTER TABLE public.compliance_checks DROP COLUMN IF EXISTS id;
ALTER TABLE public.compliance_checks DROP COLUMN IF EXISTS check_id;

-- Step 5: Make task_id the primary key
ALTER TABLE public.compliance_checks
    ALTER COLUMN task_id SET NOT NULL,
    ADD CONSTRAINT compliance_checks_pkey PRIMARY KEY (task_id),
    ADD CONSTRAINT compliance_checks_task_id_fkey FOREIGN KEY (task_id)
        REFERENCES public.tasks(id) ON DELETE CASCADE;

-- Step 6: Violations — rename check_id → task_id, change type to uuid
-- First add the new column, populate from compliance_checks, then drop old
ALTER TABLE public.violations ADD COLUMN task_id uuid;

UPDATE public.violations v
SET task_id = cc.task_id
FROM public.compliance_checks cc
WHERE cc.task_id IS NOT NULL
  AND v.check_id = (
      SELECT t.reference_id FROM public.tasks t WHERE t.id = cc.task_id
  );

-- For any violations that couldn't be mapped, try direct tasks lookup
UPDATE public.violations v
SET task_id = t.id
FROM public.tasks t
WHERE v.task_id IS NULL
  AND t.reference_id = v.check_id;

DELETE FROM public.violations WHERE task_id IS NULL;

ALTER TABLE public.violations DROP CONSTRAINT IF EXISTS violations_check_id_fkey;
ALTER TABLE public.violations DROP COLUMN check_id;
ALTER TABLE public.violations ALTER COLUMN task_id SET NOT NULL;
ALTER TABLE public.violations
    ADD CONSTRAINT violations_task_id_fkey FOREIGN KEY (task_id)
        REFERENCES public.compliance_checks(task_id) ON DELETE CASCADE;

-- Step 7: pipeline_progress — rename check_id → task_id
ALTER TABLE public.pipeline_progress ADD COLUMN task_id uuid;
UPDATE public.pipeline_progress pp
SET task_id = t.id
FROM public.tasks t
WHERE t.reference_id = pp.check_id;
DELETE FROM public.pipeline_progress WHERE task_id IS NULL;
ALTER TABLE public.pipeline_progress DROP COLUMN check_id;
ALTER TABLE public.pipeline_progress ALTER COLUMN task_id SET NOT NULL;
DROP INDEX IF EXISTS idx_pipeline_progress_check_id;
CREATE INDEX idx_pipeline_progress_task_id ON public.pipeline_progress(task_id);

-- Step 8: remediation_logs — rename check_id → task_id
ALTER TABLE public.remediation_logs ADD COLUMN task_id uuid;
UPDATE public.remediation_logs rl
SET task_id = t.id
FROM public.tasks t
WHERE t.reference_id = rl.check_id;
DELETE FROM public.remediation_logs WHERE task_id IS NULL;
ALTER TABLE public.remediation_logs DROP CONSTRAINT IF EXISTS remediation_logs_check_id_fkey;
ALTER TABLE public.remediation_logs DROP COLUMN check_id;
ALTER TABLE public.remediation_logs ALTER COLUMN task_id SET NOT NULL;
ALTER TABLE public.remediation_logs
    ADD CONSTRAINT remediation_logs_task_id_fkey FOREIGN KEY (task_id)
        REFERENCES public.compliance_checks(task_id) ON DELETE CASCADE;
DROP INDEX IF EXISTS idx_remediation_logs_check;
CREATE INDEX idx_remediation_logs_task ON public.remediation_logs(task_id);

-- Step 9: storyboard_scenes — rename check_id → task_id (nullable)
ALTER TABLE public.storyboard_scenes ADD COLUMN task_id uuid;
UPDATE public.storyboard_scenes ss
SET task_id = t.id
FROM public.tasks t
WHERE t.reference_id = ss.check_id;
ALTER TABLE public.storyboard_scenes DROP COLUMN IF EXISTS check_id;
DROP INDEX IF EXISTS idx_storyboard_scenes_check;
CREATE INDEX idx_storyboard_scenes_task ON public.storyboard_scenes(task_id);

-- Step 10: generated_ads — rename compliance_check_id → compliance_task_id
ALTER TABLE public.generated_ads RENAME COLUMN compliance_check_id TO compliance_task_id;

-- Step 11: Drop reference_id from tasks (no longer needed)
ALTER TABLE public.tasks DROP COLUMN IF EXISTS reference_id;

COMMIT;
