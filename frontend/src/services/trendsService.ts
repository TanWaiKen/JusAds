/**
 * Trends intelligence API client. The authenticated backend derives the
 * current user from Cognito; callers must not pass owner email addresses.
 */
import { API_BASE } from "@/lib/apiConfig";
import { authenticatedFetch, toApiRequestError } from "@/lib/apiAuth";
import type {
  CreativeSignalsResponse,
  CreativeTrendSignal,
  CulturalEvent,
  DailyCreativeIdea,
  EventsResponse,
  ResearchRefreshResponse,
  TrendResearchResponse,
  TrendItem,
  TrendsResponse,
  YouTubeHookReferencesResponse,
} from "@/models/trends";

export type {
  CreativeTrendSignal,
  CreativeSignalsResponse,
  CulturalEvent,
  DailyCreativeIdea,
  EventsResponse,
  ResearchRefreshResponse,
  TrendItem,
  TrendResearchResponse,
  TrendsResponse,
  YouTubeHookReference,
  YouTubeHookReferencesResponse,
} from "@/models/trends";

export async function fetchTrends(
  platform?: string,
  market?: string,
  limit = 50,
): Promise<TrendsResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (platform) params.set("platform", platform);
  if (market) params.set("market", market);
  const response = await authenticatedFetch(`${API_BASE}/api/trends?${params}`);
  if (!response.ok) throw await toApiRequestError(response, "Trends could not be loaded.");
  return response.json();
}

export async function fetchYouTubeHookReferences(market: string): Promise<YouTubeHookReferencesResponse> {
  const response = await authenticatedFetch(
    `${API_BASE}/api/trends/youtube-hook-references?${new URLSearchParams({ market })}`,
  );
  if (!response.ok) throw await toApiRequestError(response, "YouTube hook references could not be loaded.");
  return response.json();
}

export async function researchTrends(
  market: string,
  platform?: string,
  limit = 30,
): Promise<TrendResearchResponse> {
  const response = await authenticatedFetch(`${API_BASE}/api/trends/research`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ market, platform: platform || "", limit }),
  });
  if (!response.ok) throw await toApiRequestError(response, "Trend research could not be started.");
  return response.json();
}

export async function fetchCulturalEvents(market?: string, windowDays = 60): Promise<EventsResponse> {
  const params = new URLSearchParams({ window_days: String(windowDays) });
  if (market) params.set("market", market);
  const response = await authenticatedFetch(`${API_BASE}/api/trends/events?${params}`);
  if (!response.ok) throw await toApiRequestError(response, "Cultural events could not be loaded.");
  return response.json();
}

export async function fetchDailyCreativeIdea(market = "malaysia"): Promise<DailyCreativeIdea> {
  const response = await authenticatedFetch(`${API_BASE}/api/trends/daily-idea?${new URLSearchParams({ market })}`);
  if (!response.ok) throw await toApiRequestError(response, "Today's creative idea could not be loaded.");
  return response.json();
}

export async function refreshTrends(market: string): Promise<ResearchRefreshResponse> {
  const response = await authenticatedFetch(
    `${API_BASE}/api/trends/refresh-research?${new URLSearchParams({ market })}`,
    { method: "POST" },
  );
  if (!response.ok) throw await toApiRequestError(response, "Research refresh could not be started.");
  return response.json();
}

export async function fetchCreativeSignals(market: string, platform?: string): Promise<CreativeSignalsResponse> {
  const params = new URLSearchParams({ market });
  if (platform) params.set("platform", platform);
  const response = await authenticatedFetch(`${API_BASE}/api/trends/signals?${params}`);
  if (!response.ok) throw await toApiRequestError(response, "Creative signals could not be loaded.");
  return response.json();
}

export async function researchCreativeSignals(market: string, platform?: string): Promise<CreativeSignalsResponse> {
  const response = await authenticatedFetch(`${API_BASE}/api/trends/signals/research`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ market, platform: platform || "" }),
  });
  if (!response.ok) throw await toApiRequestError(response, "Creative signal research could not be started.");
  return response.json();
}

/**
 * Dashboard-level trends orchestration. Kept in this service so the Trends UI
 * has one canonical backend-integration module.
 */
export interface TrendsDashboardRequest {
  market: string;
  platform?: string;
  /** Retained only for UI compatibility; Cognito supplies authorization. */
  ownerEmail?: string;
}

export interface TrendsDashboardData {
  trendsData: Record<string, TrendItem[]>;
  totalItems: number;
  lastRefresh: Record<string, string>;
  emptyMessage: string | null;
  events: CulturalEvent[];
  eventSourceCounts: Record<string, number>;
  latestPredictHqSync: string | null;
  creativeSignals: CreativeTrendSignal[];
  signalMessage: string | null;
  dailyIdea: DailyCreativeIdea | null;
  youtubeHookReferenceCount: number;
  youtubeHooksCached: boolean | null;
}

export async function loadTrendsDashboard({
  market,
  platform,
  ownerEmail,
}: TrendsDashboardRequest): Promise<TrendsDashboardData> {
  void ownerEmail;
  const [trendsRes, eventsRes, signalsRes, dailyIdea, youtubeHooksRes] = await Promise.all([
    fetchTrends(platform || undefined, market, 30),
    fetchCulturalEvents(market === "all" ? undefined : market, 60),
    fetchCreativeSignals(market, platform || undefined).catch(() => ({ signals: [], count: 0, message: undefined })),
    fetchDailyCreativeIdea(market).catch(() => null),
    fetchYouTubeHookReferences(market).catch(() => null),
  ]);

  const cachedTrends = Array.isArray(trendsRes.trends) ? {} : trendsRes.trends;
  const hookItems: TrendItem[] = (youtubeHooksRes?.items ?? []).map((item) => ({
    id: `youtube-hook-${item.video_id}`,
    title: item.title,
    url: item.watch_url,
    platform: "youtube",
    content_type: "video",
    engagement_metrics: { views: 0, likes: 0, shares: 0, comments: 0 },
    hashtags: ["hook-reference"],
    categories: ["company-context", "hook-reference"],
    cultural_event_tag: null,
    scraped_at: youtubeHooksRes?.fetched_at ?? new Date().toISOString(),
  }));

  return {
    trendsData: { ...cachedTrends, youtube: [...hookItems, ...(cachedTrends.youtube ?? [])] },
    totalItems: (trendsRes.total_items || 0) + hookItems.length,
    lastRefresh: trendsRes.last_refresh || {},
    emptyMessage: trendsRes.message ?? null,
    events: eventsRes.events || [],
    eventSourceCounts: eventsRes.source_counts || {},
    latestPredictHqSync: eventsRes.latest_predicthq_sync || null,
    creativeSignals: signalsRes.signals || [],
    signalMessage: signalsRes.message ?? null,
    dailyIdea,
    youtubeHookReferenceCount: hookItems.length,
    youtubeHooksCached: youtubeHooksRes?.cached ?? null,
  };
}

export async function findTrendResearch(request: TrendsDashboardRequest): Promise<TrendResearchResponse> {
  return researchTrends(request.market, request.platform);
}

export async function refreshTrendResearch(request: TrendsDashboardRequest): Promise<ResearchRefreshResponse> {
  return refreshTrends(request.market);
}

export async function findCreativeIdeas(request: TrendsDashboardRequest): Promise<CreativeSignalsResponse> {
  return researchCreativeSignals(request.market, request.platform);
}
