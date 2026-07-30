import re

sql_file = r"c:\Users\tanwa\OneDrive\TWK developer\Documents\Langhub-main\backend\migrations\full_schema.sql"

with open(sql_file, "r", encoding="utf-8") as f:
    content = f.read()

tables_to_remove = [
    "pipeline_progress",
    "storyboard_scenes",
    "post_statistics_cache",
    "remediation_logs",
    "tavily_usage_log",
    "creative_trend_sources",
    "compliance_evaluations",
    "remediation_recheck_jobs",
    "remediation_versions",
    "private_media_url_audit"
]

for table in tables_to_remove:
    # Remove CREATE TABLE block
    # Matches `CREATE TABLE IF NOT EXISTS public.<table_name> (...);`
    pattern_table = re.compile(
        r"CREATE TABLE IF NOT EXISTS public\." + table + r"\s*\([\s\S]*?\);\n+",
        re.MULTILINE
    )
    content = pattern_table.sub("", content)

    # Remove CREATE INDEX blocks for the table
    # Matches `CREATE INDEX IF NOT EXISTS ... ON public.<table_name>(...);`
    pattern_index = re.compile(
        r"CREATE INDEX IF NOT EXISTS[^\n]+ON public\." + table + r"\s*\([\s\S]*?\);\n+",
        re.MULTILINE
    )
    content = pattern_index.sub("", content)
    
    # Remove triggers
    pattern_trigger = re.compile(
        r"(CREATE OR REPLACE FUNCTION[^;]+;" + r"|DROP TRIGGER IF EXISTS[^;]+;" + r"|CREATE TRIGGER[^;]+;)\n+",
        re.MULTILINE
    )
    # Be careful with triggers, only if they belong to the table
    if table == "pipeline_progress":
        content = re.sub(r"CREATE OR REPLACE FUNCTION update_pipeline_progress_updated_at\(\)[\s\S]*?\$\$ LANGUAGE plpgsql;\n+", "", content)
        content = re.sub(r"DROP TRIGGER IF EXISTS trg_pipeline_progress_updated_at ON public\.pipeline_progress;\n+", "", content)
        content = re.sub(r"CREATE TRIGGER trg_pipeline_progress_updated_at[\s\S]*?EXECUTE FUNCTION update_pipeline_progress_updated_at\(\);\n+", "", content)

# Add evidence_urls to creative_trend_signals
if "evidence_urls jsonb" not in content:
    content = content.replace(
        "title text NOT NULL,",
        "title text NOT NULL,\n    evidence_urls jsonb NOT NULL DEFAULT '[]',"
    )

with open(sql_file, "w", encoding="utf-8") as f:
    f.write(content)

print("Cleaned full_schema.sql")
