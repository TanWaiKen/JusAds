export interface TrendQuery {
  platform?: string;
  market?: string;
  limit?: number;
}

export interface TrendItem {
  id: string;
  title: string;
  url: string;
  platform: "tiktok" | "instagram" | "youtube" | "facebook_ads";
  content_type: "video" | "image" | "carousel" | "ad";
  engagement_metrics: { views: number; likes: number; shares: number; comments: number };
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

export interface YouTubeHookReference {
  video_id: string;
  title: string;
  channel_title: string;
  published_at: string;
  thumbnail_url: string;
  watch_url: string;
}

export interface YouTubeHookReferencesResponse {
  items: YouTubeHookReference[];
  cached: boolean;
  query_text?: string;
  fetched_at: string;
  expires_at: string;
  disclaimer: string;
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
  source?: string;
  source_payload?: { source_url?: string; source_title?: string; verified_scope?: string };
}

export interface ResearchRefreshResponse {
  status: "completed" | "partial" | string;
  message: string;
  sections: Record<string, { status: "completed" | "failed" | string; items_count: number; message: string }>;
}

export interface EventsResponse {
  events: CulturalEvent[];
  global_events: CulturalEvent[];
  national_events: CulturalEvent[];
  market: string;
  available_markets: string[];
  window_days: number;
  count: number;
  source_counts?: Record<string, number>;
  latest_predicthq_sync?: string | null;
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
  payload_version?: number;
}
