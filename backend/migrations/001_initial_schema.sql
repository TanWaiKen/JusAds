-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.projects (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  user_id text NOT NULL,
  name text NOT NULL CHECK (char_length(name) <= 255),
  task_type text NOT NULL CHECK (task_type = ANY (ARRAY['compliance'::text, 'generation'::text])),
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT projects_pkey PRIMARY KEY (id)
);
CREATE TABLE public.compliance_checks (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  check_id text NOT NULL UNIQUE,
  user_id text NOT NULL,
  project_id uuid NOT NULL,
  media_type text NOT NULL CHECK (media_type = ANY (ARRAY['text'::text, 'image'::text, 'audio'::text, 'video'::text])),
  market text NOT NULL,
  ethnicity text NOT NULL,
  age_group text NOT NULL,
  platform text NOT NULL DEFAULT 'general'::text,
  risk_percentage numeric CHECK (risk_percentage >= 0::numeric AND risk_percentage <= 100::numeric),
  status text NOT NULL CHECK (status = ANY (ARRAY['pending'::text, 'checked'::text, 'verified'::text, 'edit_pending'::text, 'remediated'::text, 'remix_failed'::text])),
  result_json jsonb,
  s3_upload_key text,
  s3_segmented_key text,
  s3_remix_key text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT compliance_checks_pkey PRIMARY KEY (id),
  CONSTRAINT compliance_checks_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id)
);
CREATE TABLE public.violations (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  check_id text NOT NULL,
  violation_index integer NOT NULL,
  type text NOT NULL,
  severity text NOT NULL,
  description text CHECK (char_length(description) <= 2000),
  start_time numeric,
  end_time numeric,
  clip_s3_key text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT violations_pkey PRIMARY KEY (id),
  CONSTRAINT violations_check_id_fkey FOREIGN KEY (check_id) REFERENCES public.compliance_checks(check_id)
);
CREATE TABLE public.tasks (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  project_id uuid NOT NULL,
  type text NOT NULL CHECK (type = ANY (ARRAY['compliance'::text, 'generation'::text])),
  status text NOT NULL,
  summary text,
  reference_id text,
  pipeline_state jsonb,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT tasks_pkey PRIMARY KEY (id),
  CONSTRAINT tasks_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id)
);