from pathlib import Path


SCHEMA = Path(__file__).resolve().parents[1] / "migrations" / "full_schema.sql"
MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"


def test_full_schema_matches_active_remediation_and_trend_models():
    sql = SCHEMA.read_text(encoding="utf-8")

    for table in (
        "creative_trend_signals",
        "daily_creative_ideas",
        "hook_preferences",
        "remediation_versions",
        "compliance_evaluations",
        "remediation_recheck_jobs",
    ):
        assert f"CREATE TABLE IF NOT EXISTS public.{table}" in sql

    assert "pending_recheck" in sql
    assert "verified_compliant" in sql
    assert "sample_s3_key" in sql
    assert "sample_url text" not in sql


def test_full_schema_does_not_recreate_unreferenced_legacy_tables():
    sql = SCHEMA.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS public.remediation_logs" not in sql
    assert "CREATE TABLE IF NOT EXISTS public.post_statistics_cache" not in sql
    assert "CREATE TABLE IF NOT EXISTS public.creative_trend_sources" not in sql
    assert "CREATE TABLE IF NOT EXISTS public.pipeline_progress" not in sql
    assert "CREATE TABLE IF NOT EXISTS public.storyboard_scenes" not in sql
    assert "CREATE TABLE IF NOT EXISTS public.private_media_url_audit" not in sql
    assert "CREATE TABLE IF NOT EXISTS public.tavily_usage_log" not in sql


def test_cleanup_preserves_the_remediation_audit_contract():
    """Schema cleanup must never erase proof of a remediation and its recheck."""

    cleanup = (MIGRATIONS / "029_cleanup_and_merge_tables.sql").read_text(encoding="utf-8")
    restore = (MIGRATIONS / "030_restore_remediation_versioning.sql").read_text(encoding="utf-8")

    for protected_table in (
        "remediation_versions",
        "compliance_evaluations",
        "remediation_recheck_jobs",
    ):
        assert f"DROP TABLE IF EXISTS public.{protected_table}" not in cleanup

    # Migration 030 remains a forward-recovery safeguard for any environment
    # where an earlier cleanup was already applied.
    for required in (
        "CREATE TABLE IF NOT EXISTS public.remediation_versions",
        "CREATE TABLE IF NOT EXISTS public.compliance_evaluations",
        "CREATE TABLE IF NOT EXISTS public.remediation_recheck_jobs",
        "FUNCTION public.begin_remediation_version",
        "FUNCTION public.finalize_remediation_version",
        "FUNCTION public.start_remediation_recheck",
        "FUNCTION public.record_remediation_evaluation",
        "FUNCTION public.fail_remediation_version",
    ):
        assert required in restore
