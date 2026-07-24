/**
 * Trends Intelligence API Service
 * Connects to /api/trends endpoints for trending content and cultural events.
 */

import { API_BASE } from "@/lib/apiConfig";

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

export interface TrendResearchResponse extends TrendsResponse {
  research_provider: "google_grounding" | "tavily" | "none" | string;
  freshness: "fresh" | "cached" | "unavailable" | string;
  research_sources: Array<{ url: string; title?: string; provider?: string }>;
}

export interface CreativeTrendSignal {
  id: string;
  signal_type: "sound" | "music" | "dance_or_challenge" | "hook" | "meme_or_phrase" | "format_or_template" | "visual_style" | "creator_behavior" | "hashtag_or_topic" | "seasonal_or_cultural_moment";
  title: string;
  summary: string;
  why_trending: string;
  how_it_works: string;
  suggested_adaptation: string;
  do_not_do: string;
  target_platforms: string[];
  audience: string;
  language: string;
  momentum: "rising" | "peaking" | "stable" | "declining" | "unknown";
  confidence: "low" | "medium" | "high";
  evidence_urls: string[];
  detected_at: string;
}

export interface CreativeSignalsResponse {
  signals: CreativeTrendSignal[];
  count: number;
  freshness?: "fresh" | "unavailable" | string;
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
  global_events: CulturalEvent[];
  national_events: CulturalEvent[];
  market: string;
  available_markets: string[];
  window_days: number;
  count: number;
}

export interface DailyCreativeIdea {
  title: string;
  why_today: string;
  idea: string;
  hook: string;
  format: string;
  execution_steps: string[];
  event_name: string | null;
  confidence: string;
  idea_date: string;
  market: string;
  timezone: string;
  generated_at: string;
  expires_at: string;
  source_urls: string[];
  locked_for_day: boolean;
}

// ─── API Functions ───────────────────────────────────────────────────────────

export async function fetchTrends(
  platform?: string,
  market?: string,
  limit: number = 50,
  ownerEmail?: string,
): Promise<TrendsResponse> {
  const params = new URLSearchParams();
  if (platform) params.set("platform", platform);
  if (market) params.set("market", market);
  if (ownerEmail) params.set("owner_email", ownerEmail);
  params.set("limit", String(limit));

  const response = await fetch(`${API_BASE}/api/trends?${params.toString()}`);
  if (!response.ok) throw new Error(`Failed to fetch trends: ${response.status}`);
  return response.json();
}

export async function researchTrends(
  ownerEmail: string,
  market: string,
  platform?: string,
  limit: number = 30
): Promise<TrendResearchResponse> {
  const response = await fetch(`${API_BASE}/api/trends/research`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      owner_email: ownerEmail,
      market,
      platform: platform || "",
      limit,
    }),
  });
  if (!response.ok) throw new Error(`Failed to research trends: ${response.status}`);
  return response.json();
}

export async function fetchCulturalEvents(
  market?: string,
  windowDays: number = 60
): Promise<EventsResponse> {
  const params = new URLSearchParams({ window_days: String(windowDays) });
  if (market) params.set("market", market);
  const response = await fetch(`${API_BASE}/api/trends/events?${params.toString()}`);
  if (!response.ok) throw new Error(`Failed to fetch events: ${response.status}`);
  return response.json();
}

export async function fetchDailyCreativeIdea(
  market: string = "malaysia",
): Promise<DailyCreativeIdea> {
  const params = new URLSearchParams({ market });
  const response = await fetch(`${API_BASE}/api/trends/daily-idea?${params.toString()}`);
  if (!response.ok) throw new Error(`Failed to fetch today's creative idea: ${response.status}`);
  return response.json();
}

export async function refreshTrends(
  ownerEmail: string,
  market: string
): Promise<{ status: string; message: string; items_count: number }> {
  const response = await fetch(`${API_BASE}/api/trends/refresh?${new URLSearchParams({
    owner_email: ownerEmail,
    market,
  }).toString()}`, {
    method: "POST",
  });
  if (!response.ok) throw new Error(`Failed to refresh trends: ${response.status}`);
  return response.json();
}

export async function syncCulturalEvents(): Promise<{ status: string; message: string; count: number }> {
  const response = await fetch(`${API_BASE}/api/trends/events/sync`, { method: "POST" });
  if (!response.ok) throw new Error(`Failed to sync cultural events: ${response.status}`);
  return response.json();
}


export async function fetchCreativeSignals(
  ownerEmail: string,
  market: string,
  platform?: string,
): Promise<CreativeSignalsResponse> {
  const params = new URLSearchParams({ market, owner_email: ownerEmail });
  if (platform) params.set("platform", platform);
  const response = await fetch(`${API_BASE}/api/trends/signals?${params.toString()}`);
  if (!response.ok) throw new Error(`Failed to fetch creative signals: ${response.status}`);
  return response.json();
}

export async function researchCreativeSignals(
  ownerEmail: string,
  market: string,
  platform?: string,
): Promise<CreativeSignalsResponse> {
  const response = await fetch(`${API_BASE}/api/trends/signals/research`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ owner_email: ownerEmail, market, platform: platform || "" }),
  });
  if (!response.ok) throw new Error(`Failed to research creative signals: ${response.status}`);
  return response.json();
}
