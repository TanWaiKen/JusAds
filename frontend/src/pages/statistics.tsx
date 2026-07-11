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
} from "lucide-react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { fetchPostStatistics } from "@/services/statisticsApi";
import type { StatsResponse, PostStats } from "@/services/statisticsApi";

gsap.registerPlugin(useGSAP);

// ─── Types ───────────────────────────────────────────────────────────────────

interface MetricCardProps {
  label: string;
  value: number | string;
  icon: React.ReactNode;
  suffix?: string;
}

// ─── Components ──────────────────────────────────────────────────────────────

function MetricCard({ label, value, icon, suffix }: MetricCardProps) {
  return (
    <div className="metric-card bg-surface-elevated border border-border-default rounded-xl p-5 retina-border shadow-xs">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-accent-blue">{icon}</span>
        <span className="text-[12px] font-bold uppercase tracking-wider text-text-caption">{label}</span>
      </div>
      <div className="font-mono text-[28px] font-extrabold text-text-heading">
        {typeof value === "number" ? value.toLocaleString() : value}
        {suffix && <span className="text-[16px] font-bold text-text-caption ml-1">{suffix}</span>}
      </div>
    </div>
  );
}

function PostRow({ post, index }: { post: PostStats; index: number }) {
  const isInstagram = post.platform?.toLowerCase() === "instagram";
  const isTikTok = post.platform?.toLowerCase() === "tiktok";

  return (
    <tr className="post-row border-b border-border-subtle last:border-0 hover:bg-surface-inset/50 transition-colors">
      {/* Index */}
      <td className="py-3 px-4 text-[13px] font-mono text-text-caption">
        #{index + 1}
      </td>
      
      {/* Platform Badge */}
      <td className="py-3 px-4">
        {isInstagram && (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-bold bg-pink-100 text-pink-700 dark:bg-pink-900/30 dark:text-pink-400">
            Instagram
          </span>
        )}
        {isTikTok && (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-bold bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-200">
            TikTok
          </span>
        )}
        {!isInstagram && !isTikTok && (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-bold bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400">
            {post.platform || "Unknown"}
          </span>
        )}
      </td>
      
      {/* Type Badge */}
      <td className="py-3 px-4">
        {post.is_external ? (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-bold bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400">
            Organic
          </span>
        ) : (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-bold bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
            Studio Ad
          </span>
        )}
      </td>
      
      {/* Post Content / Preview */}
      <td className="py-3 px-4 text-[13px] text-text-body font-medium truncate max-w-[280px]">
        {post.post_external_id}
      </td>
      
      {/* Views */}
      <td className="py-3 px-4 text-[13px] font-mono text-text-heading text-right">
        {post.impressions.toLocaleString()}
      </td>
      
      {/* Likes */}
      <td className="py-3 px-4 text-[13px] font-mono text-text-heading text-right">
        {(post.likes ?? 0).toLocaleString()}
      </td>
      
      {/* Clicks */}
      <td className="py-3 px-4 text-[13px] font-mono text-text-heading text-right">
        {post.clicks.toLocaleString()}
      </td>
      
      {/* Engagement */}
      <td className="py-3 px-4 text-[13px] font-mono text-accent-blue text-right">
        {post.engagement_rate.toFixed(2)}%
      </td>
      
      {/* Link to Post */}
      <td className="py-3 px-4 text-center">
        {post.post_url ? (
          <a
            href={post.post_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center text-accent-blue hover:text-accent-blue-hover transition-colors"
          >
            <ExternalLink size={14} />
          </a>
        ) : (
          <span className="text-text-caption/30 font-mono text-[11px]">-</span>
        )}
      </td>
    </tr>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function StatisticsPage() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [projectId] = useState(""); // Will be set from route params or selector
  const [platform, setPlatform] = useState("");
  const [data, setData] = useState<StatsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadStats();
  }, [projectId, platform]);

  async function loadStats() {
    setIsLoading(true);
    setError(null);
    try {
      // Use first available project or empty for all
      const result = await fetchPostStatistics(projectId || "", { platform: platform || undefined });
      setData(result);
    } catch (e) {
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

  // ── Chart data: mock daily trend from totals
  const chartData = data
    ? Array.from({ length: 7 }, (_, i) => ({
        day: `Day ${i + 1}`,
        impressions: Math.round((data.totals.impressions / 7) * (i + 1) * (0.8 + Math.random() * 0.4)),
        clicks: Math.round((data.totals.clicks / 7) * (i + 1) * (0.7 + Math.random() * 0.6)),
      }))
    : [];

  return (
    <div ref={containerRef} className="min-h-screen bg-background p-8 font-hanken">
      <div className="max-w-[1200px] mx-auto space-y-8">

        {/* ── Header ────────────────────────────────────────────────────── */}
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-headline-md font-extrabold text-text-heading mb-1">
              Post Performance Statistics
            </h1>
            <p className="text-label-ui text-text-caption">
              Track impressions, engagement, and conversions across distributed campaigns.
              {data?.last_refresh && (
                <span className="ml-2 text-[11px] text-text-caption/70">
                  Last refresh: {new Date(data.last_refresh).toLocaleString("en-MY")}
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
              <option value="youtube">YouTube</option>
            </select>
            <button
              onClick={loadStats}
              className="p-2 rounded-lg border border-border-default hover:bg-surface-inset transition-colors"
            >
              <RefreshCw size={16} className={isLoading ? "animate-spin" : ""} />
            </button>
          </div>
        </div>

        {/* ── Stale data warning ───────────────────────────────────────── */}
        {data?.is_stale && (
          <div className="flex items-center gap-3 p-3 bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800 rounded-xl text-amber-700 dark:text-amber-400 text-[13px] font-medium">
            <AlertTriangle size={16} />
            Showing cached data — live metrics temporarily unavailable.
          </div>
        )}

        {/* ── Metric Summary Cards ─────────────────────────────────────── */}
        {isLoading ? (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-24 rounded-xl bg-surface-elevated border border-border-default animate-pulse" />
            ))}
          </div>
        ) : data ? (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <MetricCard label="Impressions" value={data.totals.impressions} icon={<Eye size={16} />} />
            <MetricCard label="Clicks" value={data.totals.clicks} icon={<MousePointerClick size={16} />} />
            <MetricCard label="Engagement" value={data.totals.engagement_rate.toFixed(2)} icon={<TrendingUp size={16} />} suffix="%" />
            <MetricCard label="Reach" value={data.totals.reach} icon={<Users size={16} />} />
            <MetricCard label="Conversions" value={data.totals.conversions} icon={<Target size={16} />} />
          </div>
        ) : null}

        {/* ── Chart ────────────────────────────────────────────────────── */}
        {!isLoading && data && data.post_count > 0 && (
          <div className="chart-container bg-surface-elevated border border-border-default rounded-xl p-6 retina-border shadow-xs">
            <h3 className="font-bold text-[16px] text-text-heading flex items-center gap-2 mb-4">
              <BarChart2 size={16} className="text-accent-blue" />
              Performance Trend (7-day)
            </h3>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle, #eee)" />
                <XAxis dataKey="day" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "var(--surface-elevated, #fff)",
                    border: "1px solid var(--border-default, #eee)",
                    borderRadius: "8px",
                    fontSize: "12px",
                  }}
                />
                <Line type="monotone" dataKey="impressions" stroke="#0080FF" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="clicks" stroke="#cf5497" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
            <div className="flex gap-4 mt-3 text-[12px] text-text-caption">
              <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-[#0080FF] rounded" /> Impressions</span>
              <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-[#cf5497] rounded" /> Clicks</span>
            </div>
          </div>
        )}

        {/* ── Posts Table ──────────────────────────────────────────────── */}
        {!isLoading && data && data.posts.length > 0 && (
          <div className="bg-surface-elevated border border-border-default rounded-xl overflow-hidden retina-border shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="bg-surface-inset border-b border-border-default">
                    <th className="text-left py-3 px-4 text-[11px] uppercase font-bold text-text-caption tracking-wider">#</th>
                    <th className="text-left py-3 px-4 text-[11px] uppercase font-bold text-text-caption tracking-wider">Platform</th>
                    <th className="text-left py-3 px-4 text-[11px] uppercase font-bold text-text-caption tracking-wider">Type</th>
                    <th className="text-left py-3 px-4 text-[11px] uppercase font-bold text-text-caption tracking-wider">Post Content</th>
                    <th className="text-right py-3 px-4 text-[11px] uppercase font-bold text-text-caption tracking-wider">Views</th>
                    <th className="text-right py-3 px-4 text-[11px] uppercase font-bold text-text-caption tracking-wider">Likes</th>
                    <th className="text-right py-3 px-4 text-[11px] uppercase font-bold text-text-caption tracking-wider">Clicks</th>
                    <th className="text-right py-3 px-4 text-[11px] uppercase font-bold text-text-caption tracking-wider">Engagement</th>
                    <th className="text-center py-3 px-4 text-[11px] uppercase font-bold text-text-caption tracking-wider">Link</th>
                  </tr>
                </thead>
                <tbody>
                  {data.posts.map((post, i) => (
                    <PostRow key={post.post_external_id} post={post} index={i} />
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ── Empty state ──────────────────────────────────────────────── */}
        {!isLoading && (!data || data.post_count === 0) && !error && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <BarChart2 size={40} className="text-text-caption/30 mb-3" />
            <h4 className="font-bold text-[16px] text-text-heading mb-1">No posts distributed yet</h4>
            <p className="text-text-caption text-[13px] mb-4">
              Generate and publish ads, then distribute them to see performance data here.
            </p>
            <a
              href="/dashboard/generate"
              className="px-4 py-2 rounded-lg bg-accent-blue text-white text-[13px] font-semibold hover:opacity-90 transition-all"
            >
              Go to Generation
            </a>
          </div>
        )}

        {/* ── Error state ──────────────────────────────────────────────── */}
        {error && (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <AlertTriangle size={32} className="text-red-400 mb-3" />
            <p className="text-text-caption text-[13px]">{error}</p>
          </div>
        )}
      </div>
    </div>
  );
}
