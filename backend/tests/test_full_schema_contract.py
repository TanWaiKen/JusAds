from pathlib import Path


SCHEMA = Path(__file__).resolve().parents[1] / "migrations" / "full_schema.sql"


def test_full_schema_matches_active_remediation_and_trend_models():
    sql = SCHEMA.read_text(encoding="utf-8")

    for table in (
        "creative_trend_signals",
        "creative_trend_sources",
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
