/**
 * Post Statistics API Service
 * Connects to /api/statistics endpoints for Zernio post performance metrics.
 */

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

// ─── Interfaces ──────────────────────────────────────────────────────────────

export interface PostStats {
  post_external_id: string;
  impressions: number;
  clicks: number;
  engagement_rate: number;
  reach: number;
  conversions: number;
  is_stale: boolean;
  fetched_at: string;
}

export interface MetricsTotals {
  impressions: number;
  clicks: number;
  engagement_rate: number;
  reach: number;
  conversions: number;
}

export interface StatsResponse {
  posts: PostStats[];
  totals: MetricsTotals;
  post_count: number;
  is_stale: boolean;
  last_refresh: string | null;
}

export interface SinglePostStats {
  post_id: string;
  metrics: MetricsTotals;
  is_stale: boolean;
  fetched_at: string;
}

// ─── API Functions ───────────────────────────────────────────────────────────

export async function fetchPostStatistics(
  projectId: string,
  options?: {
    platform?: string;
    dateFrom?: string;
    dateTo?: string;
  }
): Promise<StatsResponse> {
  const params = new URLSearchParams({ project_id: projectId });
  if (options?.platform) params.set("platform", options.platform);
  if (options?.dateFrom) params.set("date_from", options.dateFrom);
  if (options?.dateTo) params.set("date_to", options.dateTo);

  const response = await fetch(`${API_BASE}/api/statistics/posts?${params.toString()}`);
  if (!response.ok) throw new Error(`Failed to fetch statistics: ${response.status}`);
  return response.json();
}

export async function fetchSinglePostStats(postId: string): Promise<SinglePostStats> {
  const response = await fetch(`${API_BASE}/api/statistics/posts/${postId}`);
  if (!response.ok) throw new Error(`Failed to fetch post stats: ${response.status}`);
  return response.json();
}
