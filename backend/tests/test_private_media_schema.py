from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "027_private_media_key_canonicalization.sql"
)


def test_private_media_migration_normalizes_legacy_urls_and_rejects_new_ones():
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "canonical_s3_object_key" in sql
    assert "UPDATE public.compliance_checks" in sql
    assert "UPDATE public.generated_ads" in sql
    assert "sample_s3_key" in sql
    assert "compliance_checks_private_key_values" in sql
    assert "generated_ads_private_key_values" in sql
    assert "!~* '^https?://'" in sql
    assert "('storyboard_scenes', 'id', 's3_anchor_image_key')" in sql
    assert "('storyboard_scenes', 'id', 's3_raw_video_key')" in sql
    assert "information_schema.columns" in sql


def test_private_media_migration_does_not_treat_storyboard_columns_as_generated_ads_columns():
    sql = MIGRATION.read_text(encoding="utf-8")

    generated_ads_block = sql.split("('generated_ads', 'id', 's3_media_key')", 1)[1].split(
        "('brand_voices', 'id', 'sample_s3_key')", 1
    )[0]
    assert "s3_anchor_image_key" not in generated_ads_block
    assert "s3_raw_video_key" not in generated_ads_block


def test_private_media_audit_view_is_not_exposed_to_client_roles():
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "WITH (security_invoker = true)" in sql
    assert "REVOKE ALL ON TABLE public.private_media_url_audit FROM PUBLIC, anon, authenticated" in sql
    assert "GRANT SELECT ON TABLE public.private_media_url_audit TO service_role" in sql
