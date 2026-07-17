import { useRef, useState, useEffect } from "react";
import { useNavigate } from "react-router";
import { useAuth } from "@/hooks/useAuth";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { PromptRecommendations } from "@/components/prompt-search/PromptRecommendations";
import { toast } from "sonner";
import { fetchPostStatistics } from "@/services/statisticsApi";
import type { StatsResponse } from "@/services/statisticsApi";
import { createGenerationTask } from "@/services/taskApi";
import { setPrefill } from "@/services/session";
import {
  Eye,
  Users,
  Heart,
  TrendingUp,
  Clock,
  Zap,
  ExternalLink,
  RefreshCw,
  Globe,
} from "lucide-react";

gsap.registerPlugin(useGSAP);

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return String(n);
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function DashboardHome() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const displayName = user?.profile.name ?? user?.profile.email ?? "Creative Lead";
  const containerRef = useRef<HTMLDivElement>(null);

  const [profile, setProfile] = useState<any>({});
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);

  // ── Fetch user profile for prompt recommendations ──────────────────────────
  useEffect(() => {
    const email = user?.profile?.email;
    if (!email) return;
    fetch(`${API_BASE}/api/profile/${email}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) {
          setProfile({
            productName: data.company_name,
            productCategory: data.product_category,
            userEmail: email,
          });
        } else {
          setProfile({ userEmail: email });
        }
      })
      .catch(() => setProfile({ userEmail: user?.profile?.email }));
  }, [user]);

  // ── Fetch real social media statistics ────────────────────────────────────
  useEffect(() => {
    setStatsLoading(true);
    fetchPostStatistics()
      .then(setStats)
      .catch(() => setStats(null))
      .finally(() => setStatsLoading(false));
  }, []);

  // ── Derived stats from API ─────────────────────────────────────────────────
  const overview = stats?.account_overview;
  const totalFollowersReached = overview?.total_followers_reached ?? 0;
  const totalEngagement = overview?.total_engagement ?? 0;
  const organicPosts = stats?.organic_posts ?? [];
  const platformEntries = Object.entries(overview?.platforms ?? {});

  // ── Summary cards ─────────────────────────────────────────────────────────
  const summaryCards = [
    {
      label: "Followers Reached",
      value: totalFollowersReached,
      icon: Users,
      iconBg: "bg-blue-50 dark:bg-blue-950/30 text-[#0080FF]",
    },
    {
      label: "Total Engagement",
      value: totalEngagement,
      icon: Heart,
      iconBg: "bg-pink-50 dark:bg-pink-950/30 text-[#FF1493]",
    },
    {
      label: "Posts Published",
      value: stats?.post_count ?? 0,
      icon: Eye,
      iconBg: "bg-cyan-50 dark:bg-cyan-950/30 text-cyan-500",
    },
  ];

  // ── GSAP entrance ─────────────────────────────────────────────────────────
  useGSAP(() => {
    const tl = gsap.timeline({ defaults: { ease: "power3.out" } });

    tl.fromTo(".dash-header",
      { y: -20, autoAlpha: 0 },
      { y: 0, autoAlpha: 1, duration: 0.6, clearProps: "all" }
    ).fromTo(".dash-header-sub",
      { y: 10, autoAlpha: 0 },
      { y: 0, autoAlpha: 1, duration: 0.4, clearProps: "all" },
      "<0.15"
    );

    tl.fromTo(".stat-card",
      { y: 40, autoAlpha: 0, scale: 0.95 },
      { y: 0, autoAlpha: 1, scale: 1, stagger: 0.1, duration: 0.5, ease: "back.out(1.4)", clearProps: "all" },
      "-=0.3"
    );

    tl.fromTo(".promo-card",
      { y: 30, autoAlpha: 0 },
      { y: 0, autoAlpha: 1, duration: 0.6, clearProps: "all" },
      "-=0.2"
    );

    tl.fromTo(".sentiment-panel",
      { y: 20, autoAlpha: 0 },
      { y: 0, autoAlpha: 1, duration: 0.5, clearProps: "all" },
      "-=0.5"
    );

    tl.fromTo(".activity-item",
      { x: 30, autoAlpha: 0 },
      { x: 0, autoAlpha: 1, stagger: 0.08, duration: 0.4, clearProps: "all" },
      "-=0.4"
    );
  }, { scope: containerRef });

  // ── GSAP count-up for stat cards (runs when stats load) ───────────────────
  useGSAP(() => {
    if (statsLoading) return;
    const statNumbers = containerRef.current?.querySelectorAll(".stat-number");
    statNumbers?.forEach((el) => {
      const target = parseInt(el.getAttribute("data-value") || "0", 10);
      const obj = { val: 0 };
      gsap.to(obj, {
        val: target,
        duration: 1.2,
        ease: "power2.out",
        onUpdate: () => { el.textContent = Math.round(obj.val).toLocaleString(); },
      });
    });
  }, { scope: containerRef, dependencies: [statsLoading] });

  return (
    <div
      ref={containerRef}
      className="flex flex-col gap-6 pt-4 px-8 pb-8 max-w-5xl mx-auto w-full font-hanken"
    >
      {/* ── Welcome Header ───────────────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div className="space-y-1">
          <h2 className="dash-header text-[24px] font-bold tracking-[-0.04em] text-text-heading">
            Welcome, {displayName}
          </h2>
          <p className="dash-header-sub text-body-md text-text-caption font-medium tracking-tight">
            Your global advertising engine is ready. Localize your campaigns across SEA with precision AI.
          </p>
        </div>
        <div className="dash-header-sub flex items-center gap-3">
          <div className="flex items-center gap-2 px-4 py-2 rounded-full border border-border-default">
            <Zap size={14} className="text-text-caption" />
            <span className="text-label-ui font-semibold text-text-body">AI Engine Active</span>
          </div>
        </div>
      </div>

      {/* ── Social Media Summary Cards ───────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {statsLoading
          ? [1, 2, 3].map((i) => (
              <div key={i} className="h-28 rounded-2xl bg-surface-card border border-border-default animate-pulse" />
            ))
          : summaryCards.map((card, idx) => {
              const Icon = card.icon;
              return (
                <div
                  key={idx}
                  className="stat-card bg-surface-card border border-border-default p-6 rounded-2xl retina-border card-shadow hover:-translate-y-1 transition-all duration-300 cursor-default"
                >
                  <div className="flex items-center justify-between mb-4">
                    <span className="text-label-ui font-semibold text-text-caption">{card.label}</span>
                    <span className={`p-2 rounded-lg ${card.iconBg}`}>
                      <Icon size={18} />
                    </span>
                  </div>
                  <div
                    className="stat-number text-[32px] font-bold tracking-tight text-text-heading font-mono"
                    data-value={card.value}
                  >
                    0
                  </div>
                </div>
              );
            })}
      </div>

      {/* ── Platform Breakdown (from account_overview.platforms) ─────────── */}
      {!statsLoading && platformEntries.length > 0 && (
        <div className="promo-card bg-surface-card border border-border-default rounded-2xl p-6 retina-border shadow-xs">
          <div className="flex items-center justify-between mb-5">
            <h3 className="font-bold text-[16px] text-text-heading flex items-center gap-2">
              <Globe size={16} className="text-accent-blue" />
              Platform Breakdown
            </h3>
            <button
              onClick={() => navigate("/dashboard/social-media")}
              className="text-[12px] font-semibold text-accent-blue hover:opacity-80 transition-opacity flex items-center gap-1"
            >
              View all posts <ExternalLink size={11} />
            </button>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {platformEntries.map(([platform, data]) => {
              const platformColor =
                platform === "tiktok"
                  ? "text-[#fe2c55] bg-pink-50 dark:bg-pink-950/20"
                  : "text-[#e1306c] bg-purple-50 dark:bg-purple-950/20";
              const label = platform.charAt(0).toUpperCase() + platform.slice(1);
              return (
                <div
                  key={platform}
                  className="flex items-center justify-between p-4 rounded-xl bg-surface-inset border border-border-subtle"
                >
                  <div className="flex items-center gap-3">
                    <span className={`p-2 rounded-lg text-[13px] font-bold ${platformColor}`}>
                      {label}
                    </span>
                  </div>
                  <div className="flex gap-6 text-right">
                    <div>
                      <span className="block text-[10px] uppercase font-bold text-text-caption/60">Reach</span>
                      <span className="font-mono text-[14px] font-bold text-text-heading">{formatCount(data.reach)}</span>
                    </div>
                    <div>
                      <span className="block text-[10px] uppercase font-bold text-text-caption/60">Likes</span>
                      <span className="font-mono text-[14px] font-bold text-text-heading">{formatCount(data.likes)}</span>
                    </div>
                    <div>
                      <span className="block text-[10px] uppercase font-bold text-text-caption/60">Posts</span>
                      <span className="font-mono text-[14px] font-bold text-text-heading">{data.posts}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Main Grid: Prompts + Recent Posts ────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 cols: Prompt Recommendations */}
        <div className="lg:col-span-2 space-y-6">
          <div className="sentiment-panel bg-surface-card border border-border-default p-6 rounded-2xl shadow-sm hover:shadow-md transition-shadow duration-300">
            <PromptRecommendations
              profile={profile}
              onUse={async (prompt, suggestion) => {
                const loadingToast = toast.loading("Initializing generation workspace...");
                try {
                  const email = user?.profile?.email ?? "demo_user";

                  // 1. Create a new "Untitled" project
                  const createRes = await fetch(`${API_BASE}/api/projects`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      name: "Untitled",
                      username: email,
                    }),
                  });
                  if (!createRes.ok) throw new Error("Failed to create project");
                  const project = await createRes.json();
                  const projectId = project.id;

                  // 2. Create a generation task
                  const task = await createGenerationTask(projectId);

                  // 3. Store prefill data in sessionStorage
                  setPrefill({
                    prompt,
                    referenceImageUrl: suggestion.sourceMedia || undefined,
                    referenceImageLabel: suggestion.title || "Reference Image",
                  });

                  // 4. Navigate to Advanced Mode
                  toast.dismiss(loadingToast);
                  navigate(`/dashboard/project/${projectId}/${task.id}`);
                  toast.success("Workspace ready — prompt prefilled.");
                } catch (err) {
                  toast.dismiss(loadingToast);
                  toast.error("Could not load workspace. Prompt copied to clipboard instead.");
                  navigator.clipboard.writeText(prompt);
                }
              }}
              maxCards={3}
            />
          </div>
        </div>

        {/* Right 1 col: Recent Organic Posts */}
        <div className="bg-surface-card border border-border-default p-6 rounded-2xl shadow-sm">
          <div className="flex items-center justify-between mb-5">
            <h3 className="text-body-md font-bold text-text-heading flex items-center gap-2">
              <TrendingUp size={16} className="text-[#FF1493]" /> Recent Posts
            </h3>
            {statsLoading && <RefreshCw size={14} className="animate-spin text-text-caption" />}
          </div>

          {!statsLoading && organicPosts.length === 0 && (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <Globe size={28} className="text-text-caption/30 mb-2" />
              <p className="text-[13px] text-text-caption">No posts yet.</p>
              <p className="text-[12px] text-text-caption/60 mt-1">
                Connect accounts in Social Media.
              </p>
            </div>
          )}

          {!statsLoading && organicPosts.length > 0 && (
            <div className="space-y-3">
              {organicPosts.slice(0, 4).map((post, idx) => {
                const platformName = post.platform || "unknown";
                const platformColor =
                  platformName.toLowerCase() === "tiktok"
                    ? "text-[#fe2c55]"
                    : "text-[#e1306c]";
                const title =
                  post.post_external_id?.length > 50
                    ? post.post_external_id.slice(0, 50) + "…"
                    : post.post_external_id || "Untitled Post";
                return (
                  <div
                    key={idx}
                    className="activity-item flex gap-3 items-start p-3 rounded-xl bg-surface-inset border border-border-subtle hover:border-border-default transition-all group"
                  >
                    <div className="shrink-0 mt-0.5">
                      <Clock size={14} className="text-text-caption/50" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-[12px] font-medium text-text-body truncate">{title}</p>
                      <div className="flex items-center gap-3 mt-1">
                        <span className={`text-[10px] font-bold uppercase ${platformColor}`}>
                          {platformName}
                        </span>
                        <span className="text-[10px] text-text-caption font-mono">
                          {formatCount(post.impressions)} views
                        </span>
                        {(post.likes ?? 0) > 0 && (
                          <span className="text-[10px] text-text-caption font-mono">
                            {formatCount(post.likes ?? 0)} likes
                          </span>
                        )}
                      </div>
                    </div>
                    {post.post_url && (
                      <a
                        href={post.post_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity text-accent-blue"
                      >
                        <ExternalLink size={12} />
                      </a>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          <div className="mt-5 pt-4 border-t border-border-subtle">
            <button
              onClick={() => navigate("/dashboard/social-media")}
              className="w-full py-2.5 px-4 rounded-xl text-code-sm font-semibold text-accent-blue bg-accent-blue/5 hover:bg-accent-blue/10 transition-colors flex items-center justify-center gap-2"
            >
              <Globe size={14} />
              View All Social Media
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
