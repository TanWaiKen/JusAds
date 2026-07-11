import { useRef, useState, useEffect } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import {
  Eye,
  MousePointerClick,
  TrendingUp,
  Users,
  Target,
  AlertTriangle,
  RefreshCw,
  BarChart2,
  ExternalLink,
  Megaphone,
  Globe,
  Heart,
  MessageCircle,
  Share2,
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from "recharts";
import { fetchPostStatistics } from "@/services/statisticsApi";
import type { StatsResponse, PostStats } from "@/services/statisticsApi";

gsap.registerPlugin(useGSAP);

// ─── Components ──────────────────────────────────────────────────────────────

interface MetricCardProps {
  label: string;
  value: number | string;
  icon: React.ReactNode;
  suffix?: string;
  size?: "sm" | "md";
}

function MetricCard({ label, value, icon, suffix, size = "md" }: MetricCardProps) {
  const textSize = size === "sm" ? "text-[20px]" : "text-[28px]";
  return (
    <div className="metric-card bg-surface-elevated border border-border-default rounded-xl p-5 retina-border shadow-xs">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-accent-blue">{icon}</span>
        <span className="text-[11px] font-bold uppercase tracking-wider text-text-caption">{label}</span>
      </div>
      <div className={`font-mono ${textSize} font-extrabold text-text-heading`}>
        {typeof value === "number" ? value.toLocaleString() : value}
        {suffix && <span className="text-[14px] font-bold text-text-caption ml-1">{suffix}</span>}
      </div>
    </div>
  );
}

function PostRow({ post, index }: { post: PostStats; index: number }) {
  const platformColors: Record<string, string> = {
    instagram: "bg-pink-100 text-pink-700 dark:bg-pink-900/30 dark:text-pink-400",
    tiktok: "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-200",
  };
  const badgeClass = platformColors[post.platform?.toLowerCase()] ??
    "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400";

  return (
    <tr className="post-row border-b border-border-subtle last:border-0 hover:bg-surface-inset/50 transition-colors">
      <td className="py-3 px-4 text-[13px] font-mono text-text-caption">#{index + 1}</td>
      <td className="py-3 px-4">
        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-bold ${badgeClass}`}>
          {post.platform || "Unknown"}
        </span>
      </td>
      <td className="py-3 px-4 text-[13px] text-text-body font-medium truncate max-w-[300px]">
        {post.post_external_id}
      </td>
      <td className="py-3 px-4 text-[13px] font-mono text-text-heading text-right">
        {post.impressions.toLocaleString()}
      </td>
      <td className="py-3 px-4 text-[13px] font-mono text-text-heading text-right">
        {(post.likes ?? 0).toLocaleString()}
      </td>
      <td className="py-3 px-4 text-[13px] font-mono text-text-heading text-right">
        {(post.comments ?? 0).toLocaleString()}
      </td>
      <td className="py-3 px-4 text-[13px] font-mono text-text-heading text-right">
        {(post.shares ?? 0).toLocaleString()}
      </td>
      <td className="py-3 px-4 text-[13px] font-mono text-accent-blue text-right">
        {post.engagement_rate.toFixed(2)}%
      </td>
      <td className="py-3 px-4 text-center">
        {post.post_url ? (
          <a href={post.post_url} target="_blank" rel="noopener noreferrer"
            className="inline-flex items-center text-accent-blue hover:text-accent-blue-hover transition-colors">
            <ExternalLink size={14} />
          </a>
        ) : (
          <span className="text-text-caption/30">-</span>
        )}
      </td>
    </tr>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function StatisticsPage() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [platform, setPlatform] = useState("");
  const [data, setData] = useState<StatsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadStats();
  }, [platform]);

  async function loadStats() {
    setIsLoading(true);
    setError(null);
    try {
      const result = await fetchPostStatistics(undefined, { platform: platform || undefined });
      setData(result);
    } catch {
      setError("Failed to load post statistics.");
    } finally {
      setIsLoading(false);
    }
  }

  // ── GSAP entrance animation
  useGSAP(() => {
    if (isLoading) return;
    const tl = gsap.timeline({ defaults: { ease: "power2.out" } });
    tl.fromTo(".metric-card", { y: 20, autoAlpha: 0 }, { y: 0, autoAlpha: 1, stagger: 0.08, duration: 0.4 })
      .fromTo(".chart-container", { y: 16, autoAlpha: 0 }, { y: 0, autoAlpha: 1, duration: 0.5 }, "-=0.2")
      .fromTo(".post-row", { x: -10, autoAlpha: 0 }, { x: 0, autoAlpha: 1, stagger: 0.04, duration: 0.3 }, "-=0.3");
  }, { scope: containerRef, dependencies: [isLoading] });

  // ── Derived data
  const jusadsPosts = data?.jusads_posts ?? [];
  const organicPosts = data?.organic_posts ?? [];
  const accountOverview = data?.account_overview;

  // Platform bar chart data
  const platformChartData = accountOverview
    ? Object.entries(accountOverview.platforms).map(([name, stats]) => ({
        platform: name.charAt(0).toUpperCase() + name.slice(1),
        impressions: stats.impressions,
        likes: stats.likes,
        reach: stats.reach,
      }))
    : [];

  return (
    <div ref={containerRef} className="min-h-screen bg-background p-8 font-hanken">
      <div className="max-w-[1200px] mx-auto space-y-8">

        {/* ── Header ───────────────────────────────────────────────────── */}
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-headline-md font-extrabold text-text-heading mb-1">
              Post Performance
            </h1>
            <p className="text-label-ui text-text-caption">
              Track your JusAds campaigns and overall social media performance.
              {data?.last_refresh && (
                <span className="ml-2 text-[11px] text-text-caption/70">
                  Synced: {new Date(data.last_refresh).toLocaleString("en-MY")}
                </span>
              )}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <select
              value={platform}
              onChange={(e) => setPlatform(e.target.value)}
              className="bg-surface-inset border border-border-default rounded-lg text-[13px] py-1.5 px-3 text-text-body cursor-pointer focus:outline-none focus:ring-2 focus:ring-accent-blue/20"
            >
              <option value="">All Platforms</option>
              <option value="tiktok">TikTok</option>
              <option value="instagram">Instagram</option>
            </select>
            <button
              onClick={loadStats}
              className="p-2 rounded-lg border border-border-default hover:bg-surface-inset transition-colors"
              aria-label="Refresh statistics"
            >
              <RefreshCw size={16} className={isLoading ? "animate-spin" : ""} />
            </button>
          </div>
        </div>

        {/* ── Error / Stale ─────────────────────────────────────────────── */}
        {error && (
          <div className="flex items-center gap-3 p-4 bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-800 rounded-xl text-red-700 dark:text-red-400 text-[13px] font-medium">
            <AlertTriangle size={16} /> {error}
          </div>
        )}
        {data?.is_stale && (
          <div className="flex items-center gap-3 p-3 bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800 rounded-xl text-amber-700 dark:text-amber-400 text-[13px] font-medium">
            <AlertTriangle size={16} /> Showing cached data — live metrics temporarily unavailable.
          </div>
        )}

        {/* ══════════════════════════════════════════════════════════════════
            SECTION 1: JusAds Campaigns
        ══════════════════════════════════════════════════════════════════ */}
        <section className="space-y-5">
          <div className="flex items-center gap-2">
            <Megaphone size={18} className="text-accent-blue" />
            <h2 className="text-[18px] font-bold text-text-heading">JusAds Campaigns</h2>
            <span className="text-[12px] text-text-caption bg-surface-inset px-2 py-0.5 rounded-full border border-border-subtle font-mono">
              {data?.jusads_count ?? 0} posts
            </span>
          </div>

          {/* JusAds Metrics */}
          {isLoading ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-24 rounded-xl bg-surface-elevated border border-border-default animate-pulse" />
              ))}
            </div>
          ) : data && jusadsPosts.length > 0 ? (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <MetricCard label="Impressions" value={data.jusads_totals.impressions} icon={<Eye size={16} />} />
                <MetricCard label="Likes" value={data.jusads_totals.likes ?? 0} icon={<Heart size={16} />} />
                <MetricCard label="Engagement" value={(data.jusads_totals.engagement_rate).toFixed(2)} icon={<TrendingUp size={16} />} suffix="%" />
                <MetricCard label="Reach" value={data.jusads_totals.reach} icon={<Users size={16} />} />
              </div>

              {/* JusAds Posts Table */}
              <div className="bg-surface-elevated border border-border-default rounded-xl overflow-hidden retina-border shadow-xs">
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="bg-surface-inset border-b border-border-default">
                        <th className="text-left py-3 px-4 text-[11px] uppercase font-bold text-text-caption tracking-wider">#</th>
                        <th className="text-left py-3 px-4 text-[11px] uppercase font-bold text-text-caption tracking-wider">Platform</th>
                        <th className="text-left py-3 px-4 text-[11px] uppercase font-bold text-text-caption tracking-wider">Content</th>
                        <th className="text-right py-3 px-4 text-[11px] uppercase font-bold text-text-caption tracking-wider">Views</th>
                        <th className="text-right py-3 px-4 text-[11px] uppercase font-bold text-text-caption tracking-wider">Likes</th>
                        <th className="text-right py-3 px-4 text-[11px] uppercase font-bold text-text-caption tracking-wider">Comments</th>
                        <th className="text-right py-3 px-4 text-[11px] uppercase font-bold text-text-caption tracking-wider">Shares</th>
                        <th className="text-right py-3 px-4 text-[11px] uppercase font-bold text-text-caption tracking-wider">Engagement</th>
                        <th className="text-center py-3 px-4 text-[11px] uppercase font-bold text-text-caption tracking-wider">Link</th>
                      </tr>
                    </thead>
                    <tbody>
                      {jusadsPosts.map((post, i) => (
                        <PostRow key={`jusads-${i}`} post={post} index={i} />
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          ) : !isLoading ? (
            <div className="flex flex-col items-center justify-center py-12 text-center bg-surface-elevated border border-border-default rounded-xl">
              <Megaphone size={36} className="text-text-caption/30 mb-3" />
              <h4 className="font-bold text-[15px] text-text-heading mb-1">No JusAds campaigns yet</h4>
              <p className="text-text-caption text-[13px] mb-4">
                Generate ads and distribute them to see campaign performance here.
              </p>
              <a href="/dashboard/generate"
                className="px-4 py-2 rounded-lg bg-accent-blue text-white text-[13px] font-semibold hover:opacity-90 transition-all">
                Go to Generation
              </a>
            </div>
          ) : null}
        </section>

        {/* ══════════════════════════════════════════════════════════════════
            SECTION 2: Account Overview
        ══════════════════════════════════════════════════════════════════ */}
        <section className="space-y-5">
          <div className="flex items-center gap-2">
            <Globe size={18} className="text-accent-blue" />
            <h2 className="text-[18px] font-bold text-text-heading">Account Overview</h2>
            <span className="text-[12px] text-text-caption">All connected accounts</span>
          </div>

          {!isLoading && data && accountOverview && (
            <>
              {/* Account-level summary metrics */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <MetricCard
                  label="Total Reach"
                  value={accountOverview.total_followers_reached}
                  icon={<Users size={16} />}
                  size="sm"
                />
                <MetricCard
                  label="Total Engagement"
                  value={accountOverview.total_engagement}
                  icon={<Heart size={16} />}
                  size="sm"
                />
                <MetricCard
                  label="Total Posts"
                  value={data.post_count}
                  icon={<BarChart2 size={16} />}
                  size="sm"
                />
                <MetricCard
                  label="Avg Engagement Rate"
                  value={data.totals.engagement_rate.toFixed(2)}
                  icon={<Target size={16} />}
                  suffix="%"
                  size="sm"
                />
              </div>

              {/* Platform comparison chart */}
              {platformChartData.length > 0 && (
                <div className="chart-container bg-surface-elevated border border-border-default rounded-xl p-6 retina-border shadow-xs">
                  <h3 className="font-bold text-[16px] text-text-heading flex items-center gap-2 mb-4">
                    <BarChart2 size={16} className="text-accent-blue" />
                    Platform Performance Comparison
                  </h3>
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={platformChartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle, #eee)" />
                      <XAxis dataKey="platform" tick={{ fontSize: 12 }} />
                      <YAxis tick={{ fontSize: 12 }} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "var(--surface-elevated, #fff)",
                          border: "1px solid var(--border-default, #eee)",
                          borderRadius: "8px",
                          fontSize: "12px",
                        }}
                      />
                      <Bar dataKey="impressions" fill="#0080FF" radius={[4, 4, 0, 0]} name="Impressions" />
                      <Bar dataKey="likes" fill="#cf5497" radius={[4, 4, 0, 0]} name="Likes" />
                    </BarChart>
                  </ResponsiveContainer>
                  <div className="flex gap-4 mt-3 text-[12px] text-text-caption">
                    <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-[#0080FF] rounded" /> Impressions</span>
                    <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-[#cf5497] rounded" /> Likes</span>
                  </div>
                </div>
              )}

              {/* Organic posts table (all account posts) */}
              {organicPosts.length > 0 && (
                <div className="bg-surface-elevated border border-border-default rounded-xl overflow-hidden retina-border shadow-xs">
                  <div className="px-6 py-4 border-b border-border-default flex items-center justify-between">
                    <h3 className="font-bold text-[15px] text-text-heading flex items-center gap-2">
                      <Share2 size={14} className="text-text-caption" />
                      Organic Posts (Account Activity)
                    </h3>
                    <span className="text-[12px] text-text-caption font-mono">{organicPosts.length} posts</span>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="bg-surface-inset border-b border-border-default">
                          <th className="text-left py-3 px-4 text-[11px] uppercase font-bold text-text-caption tracking-wider">#</th>
                          <th className="text-left py-3 px-4 text-[11px] uppercase font-bold text-text-caption tracking-wider">Platform</th>
                          <th className="text-left py-3 px-4 text-[11px] uppercase font-bold text-text-caption tracking-wider">Content</th>
                          <th className="text-right py-3 px-4 text-[11px] uppercase font-bold text-text-caption tracking-wider">Views</th>
                          <th className="text-right py-3 px-4 text-[11px] uppercase font-bold text-text-caption tracking-wider">Likes</th>
                          <th className="text-right py-3 px-4 text-[11px] uppercase font-bold text-text-caption tracking-wider">Comments</th>
                          <th className="text-right py-3 px-4 text-[11px] uppercase font-bold text-text-caption tracking-wider">Shares</th>
                          <th className="text-right py-3 px-4 text-[11px] uppercase font-bold text-text-caption tracking-wider">Engagement</th>
                          <th className="text-center py-3 px-4 text-[11px] uppercase font-bold text-text-caption tracking-wider">Link</th>
                        </tr>
                      </thead>
                      <tbody>
                        {organicPosts.map((post, i) => (
                          <PostRow key={`organic-${i}`} post={post} index={i} />
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          )}
        </section>
      </div>
    </div>
  );
}
