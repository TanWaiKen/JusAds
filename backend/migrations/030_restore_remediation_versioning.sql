-- Restore immutable remediation versions and mandatory compliance rechecks.
--
-- Migration 029 removed these tables while the application still relies on the
-- associated RPCs.  This forward migration deliberately reinstates the
-- complete state machine; generated edits are never compliant until an
-- append-only evaluation passes.

BEGIN;

CREATE TABLE IF NOT EXISTS public.remediation_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id uuid NOT NULL REFERENCES public.compliance_checks(task_id) ON DELETE CASCADE,
    version_number integer NOT NULL CHECK (version_number > 0),
    parent_version_id uuid REFERENCES public.remediation_versions(id),
    idempotency_key text NOT NULL CHECK (char_length(idempotency_key) BETWEEN 1 AND 200),
    status text NOT NULL CHECK (status IN (
        'queued', 'processing', 'pending_recheck', 'rechecking',
        'verified_compliant', 'verified_non_compliant',
        'generation_failed', 'recheck_error', 'cancelled'
    )),
    media_type text NOT NULL CHECK (media_type IN ('text', 'image', 'audio', 'video')),
    source_asset_key text,
    asset_key text,
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
    prompt_inputs jsonb NOT NULL DEFAULT '{}'::jsonb,
    generation_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by_subject text NOT NULL,
    failure_code text,
    created_at timestamptz NOT NULL DEFAULT now(),
    generation_started_at timestamptz NOT NULL DEFAULT now(),
    generated_at timestamptz,
    recheck_started_at timestamptz,
    recheck_completed_at timestamptz,
    verified_at timestamptz,
    CONSTRAINT remediation_versions_task_number_unique UNIQUE (task_id, version_number),
    CONSTRAINT remediation_versions_idempotency_unique UNIQUE (task_id, idempotency_key),
    CONSTRAINT remediation_versions_no_public_keys CHECK (
        (source_asset_key IS NULL OR source_asset_key !~* '^https?://')
        AND (asset_key IS NULL OR asset_key !~* '^https?://')
    )
);

CREATE INDEX IF NOT EXISTS idx_remediation_versions_task_created
    ON public.remediation_versions(task_id, created_at DESC);

ALTER TABLE public.compliance_checks
    ADD COLUMN IF NOT EXISTS current_remediation_version_id uuid
    REFERENCES public.remediation_versions(id);

ALTER TABLE public.compliance_checks
    DROP CONSTRAINT IF EXISTS compliance_checks_status_check;
-- Historical "remediated" records were never automatically re-evaluated and
-- therefore cannot be grandfathered into a compliant terminal state.
UPDATE public.compliance_checks
SET status = 'pending_recheck', updated_at = now()
WHERE status = 'remediated';
ALTER TABLE public.compliance_checks
    ADD CONSTRAINT compliance_checks_status_check CHECK (status IN (
        'pending', 'checked', 'verified', 'edit_pending',
        'remix_failed', 'pass', 'critical_regen', 'remediate',
        'queued', 'processing', 'pending_recheck', 'rechecking',
        'verified_compliant', 'verified_non_compliant',
        'generation_failed', 'recheck_error', 'cancelled'
    ));

CREATE TABLE IF NOT EXISTS public.compliance_evaluations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    remediation_version_id uuid NOT NULL
        REFERENCES public.remediation_versions(id) ON DELETE CASCADE,
    attempt_number integer NOT NULL CHECK (attempt_number > 0),
    idempotency_key text NOT NULL CHECK (char_length(idempotency_key) BETWEEN 1 AND 200),
    status text NOT NULL CHECK (status IN ('passed', 'failed', 'error')),
    verdict text,
    risk_percentage numeric CHECK (
        risk_percentage IS NULL OR (risk_percentage >= 0 AND risk_percentage <= 100)
    ),
    result_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    policy_version text NOT NULL,
    rule_version text NOT NULL,
    model_provider text NOT NULL DEFAULT '',
    model_name text NOT NULL DEFAULT '',
    model_version text NOT NULL DEFAULT '',
    error_code text,
    started_at timestamptz NOT NULL,
    completed_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT compliance_evaluations_attempt_unique
        UNIQUE (remediation_version_id, attempt_number),
    CONSTRAINT compliance_evaluations_idempotency_unique
        UNIQUE (remediation_version_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_compliance_evaluations_version_created
    ON public.compliance_evaluations(remediation_version_id, created_at DESC);

-- Durable outbox. A worker claims queued records and invokes the compliance
-- evaluator; a unique version key guarantees one automatic recheck job.
CREATE TABLE IF NOT EXISTS public.remediation_recheck_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    remediation_version_id uuid NOT NULL UNIQUE
        REFERENCES public.remediation_versions(id) ON DELETE CASCADE,
    status text NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
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
REVOKE ALL ON TABLE public.remediation_versions FROM anon, authenticated;
REVOKE ALL ON TABLE public.compliance_evaluations FROM anon, authenticated;
REVOKE ALL ON TABLE public.remediation_recheck_jobs FROM anon, authenticated;
GRANT ALL ON TABLE public.remediation_versions TO service_role;
GRANT ALL ON TABLE public.compliance_evaluations TO service_role;
GRANT ALL ON TABLE public.remediation_recheck_jobs TO service_role;

CREATE OR REPLACE FUNCTION public.remediation_versions_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    allowed boolean := false;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'remediation versions are append-only';
    END IF;

    IF NEW.id IS DISTINCT FROM OLD.id
       OR NEW.task_id IS DISTINCT FROM OLD.task_id
       OR NEW.version_number IS DISTINCT FROM OLD.version_number
       OR NEW.parent_version_id IS DISTINCT FROM OLD.parent_version_id
       OR NEW.idempotency_key IS DISTINCT FROM OLD.idempotency_key
       OR NEW.media_type IS DISTINCT FROM OLD.media_type
       OR NEW.source_asset_key IS DISTINCT FROM OLD.source_asset_key
       OR NEW.agent_strategy IS DISTINCT FROM OLD.agent_strategy
       OR NEW.policy_version IS DISTINCT FROM OLD.policy_version
       OR NEW.rule_version IS DISTINCT FROM OLD.rule_version
       OR NEW.model_provider IS DISTINCT FROM OLD.model_provider
       OR NEW.model_name IS DISTINCT FROM OLD.model_name
       OR NEW.model_version IS DISTINCT FROM OLD.model_version
       OR NEW.prompt_template_version IS DISTINCT FROM OLD.prompt_template_version
       OR NEW.prompt_inputs IS DISTINCT FROM OLD.prompt_inputs
       OR NEW.created_by_subject IS DISTINCT FROM OLD.created_by_subject
       OR NEW.created_at IS DISTINCT FROM OLD.created_at
       OR (OLD.asset_key IS NOT NULL AND NEW.asset_key IS DISTINCT FROM OLD.asset_key)
       OR (OLD.asset_sha256 IS NOT NULL AND NEW.asset_sha256 IS DISTINCT FROM OLD.asset_sha256)
       OR (OLD.asset_size_bytes IS NOT NULL AND NEW.asset_size_bytes IS DISTINCT FROM OLD.asset_size_bytes)
       OR (OLD.content_type IS NOT NULL AND NEW.content_type IS DISTINCT FROM OLD.content_type)
       OR (OLD.generation_metadata <> '{}'::jsonb
           AND NEW.generation_metadata IS DISTINCT FROM OLD.generation_metadata)
       OR (OLD.status <> 'processing' AND (
           NEW.asset_key IS DISTINCT FROM OLD.asset_key
           OR NEW.asset_sha256 IS DISTINCT FROM OLD.asset_sha256
           OR NEW.asset_size_bytes IS DISTINCT FROM OLD.asset_size_bytes
           OR NEW.content_type IS DISTINCT FROM OLD.content_type
           OR NEW.generation_metadata IS DISTINCT FROM OLD.generation_metadata
           OR NEW.generated_at IS DISTINCT FROM OLD.generated_at
       ))
       OR (OLD.status IN (
           'verified_compliant', 'verified_non_compliant',
           'generation_failed', 'recheck_error', 'cancelled'
       ) AND NEW.failure_code IS DISTINCT FROM OLD.failure_code)
    THEN
        RAISE EXCEPTION 'immutable remediation version fields cannot be changed';
    END IF;

    allowed := (NEW.status = OLD.status)
        OR (OLD.status = 'queued' AND NEW.status IN ('processing', 'generation_failed', 'cancelled'))
        OR (OLD.status = 'processing' AND NEW.status IN ('pending_recheck', 'generation_failed', 'cancelled'))
        OR (OLD.status = 'pending_recheck' AND NEW.status IN ('rechecking', 'cancelled'))
        OR (OLD.status = 'rechecking' AND NEW.status IN (
            'verified_compliant', 'verified_non_compliant', 'recheck_error', 'cancelled'
        ));
    IF NOT allowed THEN
        RAISE EXCEPTION 'invalid remediation transition: % -> %', OLD.status, NEW.status;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS remediation_versions_guard_trigger ON public.remediation_versions;
CREATE TRIGGER remediation_versions_guard_trigger
BEFORE UPDATE OR DELETE ON public.remediation_versions
FOR EACH ROW EXECUTE FUNCTION public.remediation_versions_guard();

CREATE OR REPLACE FUNCTION public.compliance_evaluations_append_only()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'compliance evaluations are append-only';
END;
$$;

DROP TRIGGER IF EXISTS compliance_evaluations_append_only_trigger
    ON public.compliance_evaluations;
CREATE TRIGGER compliance_evaluations_append_only_trigger
BEFORE UPDATE OR DELETE ON public.compliance_evaluations
FOR EACH ROW EXECUTE FUNCTION public.compliance_evaluations_append_only();

CREATE OR REPLACE FUNCTION public.begin_remediation_version(
    p_task_id uuid,
    p_idempotency_key text,
    p_media_type text,
    p_source_asset_key text,
    p_created_by_subject text,
    p_parent_version_id uuid DEFAULT NULL,
    p_agent_strategy text DEFAULT '',
    p_policy_version text DEFAULT '',
    p_rule_version text DEFAULT '',
    p_model_provider text DEFAULT '',
    p_model_name text DEFAULT '',
    p_model_version text DEFAULT '',
    p_prompt_template_version text DEFAULT '',
    p_prompt_inputs jsonb DEFAULT '{}'::jsonb
) RETURNS public.remediation_versions
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    existing public.remediation_versions;
    created public.remediation_versions;
    next_number integer;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended(p_task_id::text, 0));
    SELECT * INTO existing FROM remediation_versions
      WHERE task_id = p_task_id AND idempotency_key = p_idempotency_key;
    IF FOUND THEN RETURN existing; END IF;

    PERFORM 1 FROM compliance_checks WHERE task_id = p_task_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'compliance task not found'; END IF;

    SELECT COALESCE(max(version_number), 0) + 1 INTO next_number
      FROM remediation_versions WHERE task_id = p_task_id;
    INSERT INTO remediation_versions (
        task_id, version_number, parent_version_id, idempotency_key, status,
        media_type, source_asset_key, created_by_subject, agent_strategy,
        policy_version, rule_version, model_provider, model_name, model_version,
        prompt_template_version, prompt_inputs
    ) VALUES (
        p_task_id, next_number, p_parent_version_id, p_idempotency_key, 'processing',
        p_media_type, p_source_asset_key, p_created_by_subject, p_agent_strategy,
        p_policy_version, p_rule_version, p_model_provider, p_model_name, p_model_version,
        p_prompt_template_version, COALESCE(p_prompt_inputs, '{}'::jsonb)
    ) RETURNING * INTO created;

    UPDATE compliance_checks SET
        current_remediation_version_id = created.id,
        status = 'processing',
        updated_at = now()
    WHERE task_id = p_task_id;
    RETURN created;
END;
$$;

CREATE OR REPLACE FUNCTION public.finalize_remediation_version(
    p_version_id uuid,
    p_asset_key text,
    p_asset_sha256 text,
    p_asset_size_bytes bigint,
    p_content_type text DEFAULT NULL,
    p_generation_metadata jsonb DEFAULT '{}'::jsonb
) RETURNS public.remediation_versions
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE version_row public.remediation_versions;
BEGIN
    IF p_asset_key ~* '^https?://' THEN RAISE EXCEPTION 'asset key must not be a public URL'; END IF;
    SELECT * INTO version_row FROM remediation_versions WHERE id = p_version_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'remediation version not found'; END IF;
    IF version_row.status = 'pending_recheck' THEN RETURN version_row; END IF;
    IF version_row.status <> 'processing' THEN
        RAISE EXCEPTION 'invalid remediation transition: % -> pending_recheck', version_row.status;
    END IF;

    UPDATE remediation_versions SET
        asset_key = p_asset_key,
        asset_sha256 = lower(p_asset_sha256),
        asset_size_bytes = p_asset_size_bytes,
        content_type = p_content_type,
        generation_metadata = COALESCE(p_generation_metadata, '{}'::jsonb),
        status = 'pending_recheck',
        generated_at = now()
    WHERE id = p_version_id RETURNING * INTO version_row;

    INSERT INTO remediation_recheck_jobs(remediation_version_id)
    VALUES (p_version_id) ON CONFLICT (remediation_version_id) DO NOTHING;
    UPDATE compliance_checks SET status = 'pending_recheck', updated_at = now()
      WHERE task_id = version_row.task_id AND current_remediation_version_id = p_version_id;
    RETURN version_row;
END;
$$;

CREATE OR REPLACE FUNCTION public.start_remediation_recheck(p_version_id uuid)
RETURNS public.remediation_versions
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE version_row public.remediation_versions;
BEGIN
    SELECT * INTO version_row FROM remediation_versions WHERE id = p_version_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'remediation version not found'; END IF;
    IF version_row.status = 'rechecking' THEN RETURN version_row; END IF;
    IF version_row.status <> 'pending_recheck' THEN
        RAISE EXCEPTION 'invalid remediation transition: % -> rechecking', version_row.status;
    END IF;
    UPDATE remediation_versions SET status = 'rechecking', recheck_started_at = now()
      WHERE id = p_version_id RETURNING * INTO version_row;
    UPDATE remediation_recheck_jobs SET status = 'running', claimed_at = now(),
        attempt_count = attempt_count + 1 WHERE remediation_version_id = p_version_id;
    UPDATE compliance_checks SET status = 'rechecking', updated_at = now()
      WHERE task_id = version_row.task_id AND current_remediation_version_id = p_version_id;
    RETURN version_row;
END;
$$;

CREATE OR REPLACE FUNCTION public.record_remediation_evaluation(
    p_version_id uuid,
    p_idempotency_key text,
    p_evaluation_status text,
    p_verdict text,
    p_result_json jsonb,
    p_policy_version text,
    p_rule_version text,
    p_model_provider text DEFAULT '',
    p_model_name text DEFAULT '',
    p_model_version text DEFAULT '',
    p_risk_percentage numeric DEFAULT NULL,
    p_error_code text DEFAULT NULL,
    p_target_version_status text DEFAULT NULL
) RETURNS public.compliance_evaluations
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    version_row public.remediation_versions;
    existing public.compliance_evaluations;
    evaluation public.compliance_evaluations;
    next_attempt integer;
    target_status text;
BEGIN
    SELECT * INTO version_row FROM remediation_versions WHERE id = p_version_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'remediation version not found'; END IF;
    SELECT * INTO existing FROM compliance_evaluations
      WHERE remediation_version_id = p_version_id AND idempotency_key = p_idempotency_key;
    IF FOUND THEN RETURN existing; END IF;
    IF version_row.status <> 'rechecking' THEN
        RAISE EXCEPTION 'version must be rechecking before recording an evaluation';
    END IF;

    target_status := CASE
        WHEN p_evaluation_status = 'error' THEN 'recheck_error'
        WHEN p_evaluation_status = 'passed'
             AND lower(COALESCE(p_verdict, '')) IN ('accepted','compliant','pass','verified_compliant')
            THEN 'verified_compliant'
        WHEN p_evaluation_status IN ('passed','failed') THEN 'verified_non_compliant'
        ELSE NULL
    END;
    IF target_status IS NULL OR target_status IS DISTINCT FROM p_target_version_status THEN
        RAISE EXCEPTION 'invalid evaluation outcome';
    END IF;

    SELECT COALESCE(max(attempt_number), 0) + 1 INTO next_attempt
      FROM compliance_evaluations WHERE remediation_version_id = p_version_id;
    INSERT INTO compliance_evaluations (
        remediation_version_id, attempt_number, idempotency_key, status, verdict,
        risk_percentage, result_json, policy_version, rule_version,
        model_provider, model_name, model_version, error_code, started_at
    ) VALUES (
        p_version_id, next_attempt, p_idempotency_key, p_evaluation_status, p_verdict,
        p_risk_percentage, COALESCE(p_result_json, '{}'::jsonb), p_policy_version, p_rule_version,
        p_model_provider, p_model_name, p_model_version, p_error_code,
        COALESCE(version_row.recheck_started_at, now())
    ) RETURNING * INTO evaluation;

    UPDATE remediation_versions SET status = target_status,
        recheck_completed_at = now(),
        verified_at = CASE WHEN target_status = 'verified_compliant' THEN now() ELSE NULL END,
        failure_code = CASE WHEN target_status = 'recheck_error' THEN p_error_code ELSE NULL END
      WHERE id = p_version_id;
    UPDATE remediation_recheck_jobs SET
        status = CASE WHEN target_status = 'recheck_error' THEN 'failed' ELSE 'completed' END,
        completed_at = now(), last_error_code = p_error_code
      WHERE remediation_version_id = p_version_id;
    UPDATE compliance_checks SET status = target_status, updated_at = now()
      WHERE task_id = version_row.task_id AND current_remediation_version_id = p_version_id;
    RETURN evaluation;
END;
$$;

CREATE OR REPLACE FUNCTION public.fail_remediation_version(
    p_version_id uuid, p_error_code text
) RETURNS public.remediation_versions
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE version_row public.remediation_versions;
BEGIN
    SELECT * INTO version_row FROM remediation_versions WHERE id = p_version_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'remediation version not found'; END IF;
    IF version_row.status = 'generation_failed' THEN RETURN version_row; END IF;
    IF version_row.status NOT IN ('queued', 'processing') THEN
        RAISE EXCEPTION 'cannot fail generation from state %', version_row.status;
    END IF;
    UPDATE remediation_versions SET status = 'generation_failed', failure_code = p_error_code
      WHERE id = p_version_id RETURNING * INTO version_row;
    UPDATE compliance_checks SET status = 'generation_failed', updated_at = now()
      WHERE task_id = version_row.task_id AND current_remediation_version_id = p_version_id;
    RETURN version_row;
END;
$$;

-- These RPCs are backend-only. In particular, clients must not be able to
-- choose a task/version id and promote it with the service-level functions.
REVOKE ALL ON FUNCTION public.begin_remediation_version(
    uuid, text, text, text, text, uuid, text, text, text, text, text, text, text, jsonb
) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.finalize_remediation_version(
    uuid, text, text, bigint, text, jsonb
) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.start_remediation_recheck(uuid)
    FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.record_remediation_evaluation(
    uuid, text, text, text, jsonb, text, text, text, text, text, numeric, text, text
) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.fail_remediation_version(uuid, text)
    FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION public.begin_remediation_version(
    uuid, text, text, text, text, uuid, text, text, text, text, text, text, text, jsonb
) TO service_role;
GRANT EXECUTE ON FUNCTION public.finalize_remediation_version(
    uuid, text, text, bigint, text, jsonb
) TO service_role;
GRANT EXECUTE ON FUNCTION public.start_remediation_recheck(uuid) TO service_role;
GRANT EXECUTE ON FUNCTION public.record_remediation_evaluation(
    uuid, text, text, text, jsonb, text, text, text, text, text, numeric, text, text
) TO service_role;
GRANT EXECUTE ON FUNCTION public.fail_remediation_version(uuid, text) TO service_role;

COMMIT;
