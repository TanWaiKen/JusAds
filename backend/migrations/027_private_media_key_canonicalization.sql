-- Private media key canonicalisation.
--
-- Canonical rule: every *_key column holds an S3 object key only, never an
-- http(s) URL. URLs are generated after authorization. This migration is
-- intentionally schema-aware: older deployments did not have every optional
-- asset column, and storyboard keys are not generated_ads columns.

BEGIN;

CREATE OR REPLACE FUNCTION public.canonical_s3_object_key(value text)
RETURNS text
LANGUAGE sql
IMMUTABLE
RETURNS NULL ON NULL INPUT
AS $$
  SELECT NULLIF(
    regexp_replace(
      regexp_replace(trim(value), '^https?://[^/]+/', '', 'i'),
      '\?.*$',
      ''
    ),
    ''
  )
$$;

-- A voice sample is private media. Keep sample_url only as a temporary legacy
-- read path; new writes must use sample_s3_key.
ALTER TABLE IF EXISTS public.brand_voices
  ADD COLUMN IF NOT EXISTS sample_s3_key text;

DO $$
DECLARE
  target record;
  check_expression text;
BEGIN
  -- Normalize only columns that exist in this deployment. In particular,
  -- anchor/raw keys belong to storyboard_scenes rather than generated_ads.
  FOR target IN
    SELECT *
    FROM (VALUES
      ('compliance_checks', 'task_id', 's3_upload_key'),
      ('compliance_checks', 'task_id', 's3_segmented_key'),
      ('compliance_checks', 'task_id', 's3_remix_key'),
      ('violations', 'id', 'clip_s3_key'),
      ('business_profiles', 'id', 'logo_s3_key'),
      ('storyboard_scenes', 'id', 's3_anchor_image_key'),
      ('storyboard_scenes', 'id', 's3_raw_video_key'),
      ('generated_ads', 'id', 's3_media_key'),
      ('generated_ads', 'id', 's3_draft_key'),
      ('generated_ads', 'id', 's3_rendered_key'),
      ('brand_voices', 'id', 'sample_s3_key'),
      ('remediation_logs', 'id', 'previous_s3_key'),
      ('remediation_logs', 'id', 'remediated_s3_key'),
      ('remediation_versions', 'id', 'source_asset_key'),
      ('remediation_versions', 'id', 'asset_key')
    ) AS t(table_name, id_column, column_name)
    WHERE to_regclass('public.' || t.table_name) IS NOT NULL
      AND EXISTS (
        SELECT 1
        FROM information_schema.columns c
        WHERE c.table_schema = 'public'
          AND c.table_name = t.table_name
          AND c.column_name = t.column_name
      )
  LOOP
    EXECUTE format(
      'UPDATE public.%I SET %I = public.canonical_s3_object_key(%I) WHERE %I ~* ''^https?://''',
      target.table_name, target.column_name, target.column_name, target.column_name
    );
  END LOOP;

  IF to_regclass('public.brand_voices') IS NOT NULL
     AND EXISTS (
       SELECT 1 FROM information_schema.columns
       WHERE table_schema = 'public' AND table_name = 'brand_voices' AND column_name = 'sample_url'
     ) THEN
    UPDATE public.brand_voices
    SET sample_s3_key = public.canonical_s3_object_key(sample_url)
    WHERE sample_s3_key IS NULL AND sample_url ~* '^https?://';
  END IF;

  -- generated_ads.metadata has historically carried these two redundant URL
  -- fields. Remove them without touching legitimate third-party links.
  IF to_regclass('public.generated_ads') IS NOT NULL
     AND EXISTS (
       SELECT 1 FROM information_schema.columns
       WHERE table_schema = 'public' AND table_name = 'generated_ads' AND column_name = 'metadata'
     ) THEN
    UPDATE public.generated_ads
    SET metadata = COALESCE(metadata, '{}'::jsonb) - 's3_url' - 'public_url'
    WHERE metadata ? 's3_url' OR metadata ? 'public_url';
  END IF;

  -- Add one validated private-key constraint per table, constructed from the
  -- columns actually present. This makes the migration safe for both old and
  -- current deployments.
  FOR target IN
    SELECT t.table_name, t.constraint_name,
           string_agg(format('COALESCE(%I, '''') !~* ''^https?://''', t.column_name), ' AND ') AS expression
    FROM (VALUES
      ('compliance_checks', 'compliance_checks_private_key_values', 's3_upload_key'),
      ('compliance_checks', 'compliance_checks_private_key_values', 's3_segmented_key'),
      ('compliance_checks', 'compliance_checks_private_key_values', 's3_remix_key'),
      ('violations', 'violations_private_key_values', 'clip_s3_key'),
      ('business_profiles', 'business_profiles_private_key_values', 'logo_s3_key'),
      ('storyboard_scenes', 'storyboard_scenes_private_key_values', 's3_anchor_image_key'),
      ('storyboard_scenes', 'storyboard_scenes_private_key_values', 's3_raw_video_key'),
      ('generated_ads', 'generated_ads_private_key_values', 's3_media_key'),
      ('generated_ads', 'generated_ads_private_key_values', 's3_draft_key'),
      ('generated_ads', 'generated_ads_private_key_values', 's3_rendered_key'),
      ('brand_voices', 'brand_voices_private_key_values', 'sample_s3_key'),
      ('remediation_logs', 'remediation_logs_private_key_values', 'previous_s3_key'),
      ('remediation_logs', 'remediation_logs_private_key_values', 'remediated_s3_key'),
      ('remediation_versions', 'remediation_versions_private_key_values', 'source_asset_key'),
      ('remediation_versions', 'remediation_versions_private_key_values', 'asset_key')
    ) AS t(table_name, constraint_name, column_name)
    WHERE to_regclass('public.' || t.table_name) IS NOT NULL
      AND EXISTS (
        SELECT 1 FROM information_schema.columns c
        WHERE c.table_schema = 'public'
          AND c.table_name = t.table_name
          AND c.column_name = t.column_name
      )
    GROUP BY t.table_name, t.constraint_name
  LOOP
    EXECUTE format('ALTER TABLE public.%I DROP CONSTRAINT IF EXISTS %I', target.table_name, target.constraint_name);
    EXECUTE format('ALTER TABLE public.%I ADD CONSTRAINT %I CHECK (%s)', target.table_name, target.constraint_name, target.expression);
  END LOOP;
END
$$;

-- Audit only key-bearing fields that exist. The view is service-only and obeys
-- RLS when it is ever queried through the Data API.
DO $$
DECLARE
  target record;
  query_text text := '';
BEGIN
  FOR target IN
    SELECT *
    FROM (VALUES
      ('compliance_checks', 'task_id', 's3_upload_key'),
      ('compliance_checks', 'task_id', 's3_segmented_key'),
      ('compliance_checks', 'task_id', 's3_remix_key'),
      ('violations', 'id', 'clip_s3_key'),
      ('business_profiles', 'id', 'logo_s3_key'),
      ('storyboard_scenes', 'id', 's3_anchor_image_key'),
      ('storyboard_scenes', 'id', 's3_raw_video_key'),
      ('generated_ads', 'id', 's3_media_key'),
      ('generated_ads', 'id', 's3_draft_key'),
      ('generated_ads', 'id', 's3_rendered_key'),
      ('brand_voices', 'id', 'sample_s3_key'),
      ('remediation_versions', 'id', 'source_asset_key'),
      ('remediation_versions', 'id', 'asset_key')
    ) AS t(table_name, id_column, column_name)
    WHERE to_regclass('public.' || t.table_name) IS NOT NULL
      AND EXISTS (
        SELECT 1 FROM information_schema.columns c
        WHERE c.table_schema = 'public'
          AND c.table_name = t.table_name
          AND c.column_name = t.column_name
      )
  LOOP
    query_text := query_text || CASE WHEN query_text = '' THEN '' ELSE ' UNION ALL ' END || format(
      'SELECT %L::text AS field_name, %I::text AS record_id, %I::text AS value FROM public.%I WHERE %I ~* ''^https?://''',
      target.table_name || '.' || target.column_name,
      target.id_column,
      target.column_name,
      target.table_name,
      target.column_name
    );
  END LOOP;

  IF query_text = '' THEN
    query_text := 'SELECT NULL::text AS field_name, NULL::text AS record_id, NULL::text AS value WHERE false';
  END IF;

  EXECUTE 'CREATE OR REPLACE VIEW public.private_media_url_audit WITH (security_invoker = true) AS ' || query_text;
END
$$;

REVOKE ALL ON TABLE public.private_media_url_audit FROM PUBLIC, anon, authenticated;
GRANT SELECT ON TABLE public.private_media_url_audit TO service_role;

COMMIT;
