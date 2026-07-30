-- The browser accesses data through the authenticated backend only.  Do not
-- expose application records through PostgREST merely because a table is in
-- the public schema.  The service-role backend bypasses RLS and retains the
-- required database permissions.

BEGIN;

ALTER TABLE public.personas ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.creative_trend_signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.daily_creative_ideas ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.generated_ads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.project_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.compliance_checks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.business_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.violations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ad_policy_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.platform_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.brand_voices ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.hook_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.youtube_hook_reference_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.trends_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cultural_events ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.personas, public.creative_trend_signals,
    public.daily_creative_ideas, public.users, public.projects,
    public.generated_ads, public.project_members, public.compliance_checks,
    public.tasks, public.business_profiles, public.violations,
    public.ad_policy_rules, public.chat_messages, public.platform_rules,
    public.brand_voices, public.hook_preferences,
    public.youtube_hook_reference_cache, public.trends_cache,
    public.cultural_events FROM PUBLIC, anon, authenticated;

GRANT ALL ON TABLE public.personas, public.creative_trend_signals,
    public.daily_creative_ideas, public.users, public.projects,
    public.generated_ads, public.project_members, public.compliance_checks,
    public.tasks, public.business_profiles, public.violations,
    public.ad_policy_rules, public.chat_messages, public.platform_rules,
    public.brand_voices, public.hook_preferences,
    public.youtube_hook_reference_cache, public.trends_cache,
    public.cultural_events TO service_role;

ALTER FUNCTION public.remediation_versions_guard() SET search_path = public;
ALTER FUNCTION public.compliance_evaluations_append_only() SET search_path = public;
ALTER FUNCTION public.canonical_s3_object_key(text) SET search_path = public;
ALTER FUNCTION public.update_pipeline_progress_updated_at() SET search_path = public;

COMMIT;
