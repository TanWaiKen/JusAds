-- Migration: Add ON DELETE CASCADE to all project-related foreign keys.
-- When a project is deleted, all tasks, compliance_checks, and violations
-- are automatically removed by Postgres.

-- 1. violations → compliance_checks (delete violations when check is deleted)
ALTER TABLE public.violations
  DROP CONSTRAINT violations_check_id_fkey,
  ADD CONSTRAINT violations_check_id_fkey
    FOREIGN KEY (check_id) REFERENCES public.compliance_checks(check_id)
    ON DELETE CASCADE;

-- 2. compliance_checks → projects (delete checks when project is deleted)
ALTER TABLE public.compliance_checks
  DROP CONSTRAINT compliance_checks_project_id_fkey,
  ADD CONSTRAINT compliance_checks_project_id_fkey
    FOREIGN KEY (project_id) REFERENCES public.projects(id)
    ON DELETE CASCADE;

-- 3. tasks → projects (delete tasks when project is deleted)
ALTER TABLE public.tasks
  DROP CONSTRAINT tasks_project_id_fkey,
  ADD CONSTRAINT tasks_project_id_fkey
    FOREIGN KEY (project_id) REFERENCES public.projects(id)
    ON DELETE CASCADE;
