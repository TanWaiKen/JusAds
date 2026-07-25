/**
 * Hook Search API Service
 * Connects to /api/hooks/* endpoints for YouTube Shorts hook video discovery.
 *
 * Used by the creative strategy flow to find viral meme/transition clips
 * that serve as reference material for ad hook scenes.
 */

import { API_BASE } from "@/lib/apiConfig";

// ─── Types ───────────────────────────────────────────────────────────────────

export interface HookVideoResult {
  videoId: string;
  title: string;
  url: string;
  thumbnailUrl: string;
  channel: string;
  durationLabel: string;
  viewCount: number;
  tags: string[];
  relevanceScore: number;
}

export interface HookSearchResponse {
  results: HookVideoResult[];
  count: number;
  queryUsed: string;
}

export interface HookTagSuggestion {
  suggestions: string[];
  allTags: string[];
}

// ─── API Functions ───────────────────────────────────────────────────────────

/**
 * Search YouTube Shorts for hook/transition videos.
 * Returns only Shorts (≤60s) suitable as ad hook references.
 */
export async function searchHookVideos(params: {
  query?: string;
  creativeStyle?: string;
  market?: string;
  ethnicity?: string;
  productCategory?: string;
  maxResults?: number;
}): Promise<HookSearchResponse> {
  const res = await fetch(`${API_BASE}/api/hook-search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query: params.query ?? "",
      creative_style: params.creativeStyle ?? "meme_shock",
      market: params.market ?? "malaysia",
      ethnicity: params.ethnicity ?? "all",
      product_category: params.productCategory ?? "",
      max_results: params.maxResults ?? 8,
    }),
  });

  if (!res.ok) {
    throw new Error(`Hook search failed: ${res.status}`);
  }

  const data = await res.json() as Record<string, unknown>;
  const rawResults = Array.isArray(data.results) ? data.results : [];

  return {
    results: rawResults.map(normalizeHookResult),
    count: typeof data.count === "number" ? data.count : rawResults.length,
    queryUsed: typeof data.query_used === "string" ? data.query_used : "",
  };
}

/**
 * Record a user's hook video selection for preference learning.
 * The system learns which hook styles the user prefers via association rules.
 */
export async function recordHookPreference(params: {
  videoId: string;
  tags: string[];
  creativeStyle?: string;
  productCategory?: string;
  userEmail?: string;
}): Promise<void> {
  const searchParams = new URLSearchParams();
  if (params.userEmail) searchParams.set("user_email", params.userEmail);

  await fetch(
    `${API_BASE}/api/hook-search/preference?${searchParams.toString()}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        video_id: params.videoId,
        tags: params.tags,
        creative_style: params.creativeStyle ?? "meme_shock",
        product_category: params.productCategory ?? "",
      }),
    }
  );
}

/**
 * Suggest hook style tags based on a brief and creative strategy.
 */
export async function suggestHookTags(
  brief: string,
  creativeStyle: string = "meme_shock"
): Promise<HookTagSuggestion> {
  const params = new URLSearchParams({
    brief,
    creative_style: creativeStyle,
  });

  const res = await fetch(`${API_BASE}/api/hook-search/tags?${params.toString()}`);
  if (!res.ok) {
    return { suggestions: [], allTags: [] };
  }

  const data = await res.json() as Record<string, unknown>;
  return {
    suggestions: Array.isArray(data.suggestions)
      ? data.suggestions.filter((s): s is string => typeof s === "string")
      : [],
    allTags: Array.isArray(data.all_tags)
      ? data.all_tags.filter((t): t is string => typeof t === "string")
      : [],
  };
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function normalizeHookResult(raw: unknown): HookVideoResult {
  if (typeof raw !== "object" || raw === null) {
    return emptyResult();
  }
  const r = raw as Record<string, unknown>;
  return {
    videoId: typeof r.video_id === "string" ? r.video_id : "",
    title: typeof r.title === "string" ? r.title : "",
    url: typeof r.url === "string" ? r.url : "",
    thumbnailUrl: typeof r.thumbnail_url === "string" ? r.thumbnail_url : "",
    channel: typeof r.channel === "string" ? r.channel : "",
    durationLabel: typeof r.duration_label === "string" ? r.duration_label : "",
    viewCount: typeof r.view_count === "number" ? r.view_count : 0,
    tags: Array.isArray(r.tags) ? r.tags.filter((t): t is string => typeof t === "string") : [],
    relevanceScore: typeof r.relevance_score === "number" ? r.relevance_score : 0,
  };
}

function emptyResult(): HookVideoResult {
  return {
    videoId: "",
    title: "",
    url: "",
    thumbnailUrl: "",
    channel: "",
    durationLabel: "",
    viewCount: 0,
    tags: [],
    relevanceScore: 0,
  };
}
