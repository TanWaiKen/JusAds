/**
 * Trends Intelligence API Service
 * Connects to /api/trends endpoints for trending content and cultural events.
 */

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

// ─── Interfaces ──────────────────────────────────────────────────────────────

export interface TrendItem {
  id: string;
  title: string;
  url: string;
  platform: "tiktok" | "instagram" | "youtube" | "facebook_ads";
  content_type: "video" | "image" | "carousel" | "ad";
  engagement_metrics: {
    views: number;
    likes: number;
    shares: number;
    comments: number;
  };
  hashtags: string[];
  categories: string[];
  cultural_event_tag: string | null;
  scraped_at: string;
}

export interface TrendsResponse {
  trends: Record<string, TrendItem[]>;
  last_refresh: Record<string, string>;
  total_items: number;
  message?: string;
}

export interface CulturalEvent {
  id: string;
  name: string;
  market: string;
  start_date: string;
  end_date: string;
  event_type: "religious" | "festive" | "sports" | "national" | "global";
  tags: string[];
  impact_score: number;
}

export interface EventsResponse {
  events: CulturalEvent[];
  market: string;
  window_days: number;
  count: number;
}

// ─── API Functions ───────────────────────────────────────────────────────────

export async function fetchTrends(
  platform?: string,
  market?: string,
  limit: number = 50
): Promise<TrendsResponse> {
  const params = new URLSearchParams();
  if (platform) params.set("platform", platform);
  if (market) params.set("market", market);
  params.set("limit", String(limit));

  const response = await fetch(`${API_BASE}/api/trends?${params.toString()}`);
  if (!response.ok) throw new Error(`Failed to fetch trends: ${response.status}`);
  return response.json();
}

export async function fetchCulturalEvents(
  market: string = "malaysia",
  windowDays: number = 30
): Promise<EventsResponse> {
  const params = new URLSearchParams({ market, window_days: String(windowDays) });
  const response = await fetch(`${API_BASE}/api/trends/events?${params.toString()}`);
  if (!response.ok) throw new Error(`Failed to fetch events: ${response.status}`);
  return response.json();
}

export async function triggerTrendRefresh(): Promise<{ status: string; message: string }> {
  const response = await fetch(`${API_BASE}/api/trends/refresh`, { method: "POST" });
  if (!response.ok) throw new Error(`Failed to trigger refresh: ${response.status}`);
  return response.json();
}

export async function syncCulturalEvents(): Promise<{ status: string; message: string; count: number }> {
  const response = await fetch(`${API_BASE}/api/trends/events/sync`, { method: "POST" });
  if (!response.ok) throw new Error(`Failed to sync cultural events: ${response.status}`);
  return response.json();
}
