/**
 * Post Statistics API Service
 * Connects to /api/statistics endpoints for Zernio post performance metrics.
 *
 * Two sections:
 * 1. JusAds Campaigns — posts published through Zernio/JusAds
 * 2. Account Overview — overall social media account performance
 */

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

// ─── Interfaces ──────────────────────────────────────────────────────────────

export interface PostStats {
  post_external_id: string;
  platform: string;
  impressions: number;
  clicks: number;
  engagement_rate: number;
  reach: number;
  conversions: number;
  is_stale?: boolean;
  fetched_at?: string;
  likes?: number;
  comments?: number;
  shares?: number;
  is_external?: boolean;
  published_at?: string;
  post_url?: string;
}

export interface MetricsTotals {
  impressions: number;
  clicks: number;
  engagement_rate: number;
  reach: number;
  conversions: number;
  likes?: number;
  comments?: number;
  shares?: number;
}

export interface PlatformBreakdown {
  posts: number;
  impressions: number;
  likes: number;
  reach: number;
}

export interface AccountOverview {
  total_followers_reached: number;
  total_engagement: number;
  platforms: Record<string, PlatformBreakdown>;
}

export interface StatsResponse {
  // JusAds-published posts (non-external)
  jusads_posts: PostStats[];
  jusads_totals: MetricsTotals;
  jusads_count: number;
  // Organic/external posts
  organic_posts: PostStats[];
  organic_totals: MetricsTotals;
  organic_count: number;
  // All posts combined (legacy)
  posts: PostStats[];
  totals: MetricsTotals;
  post_count: number;
  // Account-level overview
  account_overview: AccountOverview;
  is_stale: boolean;
  last_refresh: string | null;
}

// ─── API Functions ───────────────────────────────────────────────────────────

export async function fetchPostStatistics(
  _projectId?: string,
  options?: {
    platform?: string;
  }
): Promise<StatsResponse> {
  const params = new URLSearchParams();
  if (options?.platform) params.set("platform", options.platform);

  const url = params.toString()
    ? `${API_BASE}/api/statistics/posts?${params.toString()}`
    : `${API_BASE}/api/statistics/posts`;

  const response = await fetch(url);
  if (!response.ok) throw new Error(`Failed to fetch statistics: ${response.status}`);
  return response.json();
}
