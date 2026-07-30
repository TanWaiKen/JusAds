-- Atomically claim bounded remediation recheck jobs for the backend worker.
-- A stale running job is recoverable after 15 minutes; only the service role
-- can call this function, so browser clients cannot promote a remediation.

BEGIN;

CREATE OR REPLACE FUNCTION public.claim_remediation_recheck_jobs(p_limit integer DEFAULT 2)
RETURNS SETOF jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    RETURN QUERY
    WITH candidates AS (
        SELECT job.id
        FROM public.remediation_recheck_jobs AS job
        JOIN public.remediation_versions AS version
          ON version.id = job.remediation_version_id
        WHERE job.available_at <= now()
          AND (
              (job.status = 'queued' AND version.status = 'pending_recheck')
              OR (
                  job.status = 'running'
                  AND job.claimed_at < now() - interval '15 minutes'
                  AND version.status = 'rechecking'
              )
          )
        ORDER BY job.created_at
        FOR UPDATE OF job SKIP LOCKED
        LIMIT GREATEST(1, LEAST(COALESCE(p_limit, 2), 10))
    ), claimed AS (
        UPDATE public.remediation_recheck_jobs AS job
        SET status = 'running',
            claimed_at = now(),
            attempt_count = job.attempt_count + 1
        FROM candidates
        WHERE job.id = candidates.id
        RETURNING job.*
    )
    SELECT jsonb_build_object(
        'id', claimed.id,
        'attempt_count', claimed.attempt_count,
        'version', to_jsonb(version)
    )
    FROM claimed
    JOIN public.remediation_versions AS version
      ON version.id = claimed.remediation_version_id;
END;
$$;

REVOKE ALL ON FUNCTION public.claim_remediation_recheck_jobs(integer)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.claim_remediation_recheck_jobs(integer)
    TO service_role;

COMMIT;
