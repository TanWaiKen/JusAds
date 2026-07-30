/** Authenticated YouTube Shorts hook-reference search client. */
import { API_BASE } from "@/lib/apiConfig";
import { authenticatedFetch, toApiRequestError } from "@/lib/apiAuth";
import type { HookSearchResponse, HookTagSuggestion, HookVideoResult } from "@/models/generation";

export type { HookSearchResponse, HookTagSuggestion, HookVideoResult } from "@/models/generation";

export async function searchHookVideos(params: {
  query?: string;
  creativeStyle?: string;
  market?: string;
  ethnicity?: string;
  productCategory?: string;
  maxResults?: number;
}): Promise<HookSearchResponse> {
  const response = await authenticatedFetch(`${API_BASE}/api/hook-search`, {
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
  if (!response.ok) throw await toApiRequestError(response, "Hook search could not be completed.");

  const data = await response.json() as Record<string, unknown>;
  const rawResults = Array.isArray(data.results) ? data.results : [];
  return {
    results: rawResults.map(normalizeHookResult),
    count: typeof data.count === "number" ? data.count : rawResults.length,
    queryUsed: typeof data.query_used === "string" ? data.query_used : "",
  };
}

export async function recordHookPreference(params: {
  videoId: string;
  tags: string[];
  creativeStyle?: string;
  productCategory?: string;
}): Promise<void> {
  const response = await authenticatedFetch(`${API_BASE}/api/hook-search/preference`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      video_id: params.videoId,
      tags: params.tags,
      creative_style: params.creativeStyle ?? "meme_shock",
      product_category: params.productCategory ?? "",
    }),
  });
  if (!response.ok) throw await toApiRequestError(response, "Hook preference could not be saved.");
}

export async function suggestHookTags(brief: string, creativeStyle = "meme_shock"): Promise<HookTagSuggestion> {
  const params = new URLSearchParams({ brief, creative_style: creativeStyle });
  const response = await authenticatedFetch(`${API_BASE}/api/hook-search/tags?${params}`);
  if (!response.ok) throw await toApiRequestError(response, "Hook tag suggestions could not be loaded.");
  const data = await response.json() as Record<string, unknown>;
  return {
    suggestions: Array.isArray(data.suggestions) ? data.suggestions.filter((value): value is string => typeof value === "string") : [],
    allTags: Array.isArray(data.all_tags) ? data.all_tags.filter((value): value is string => typeof value === "string") : [],
  };
}

function normalizeHookResult(raw: unknown): HookVideoResult {
  const data = raw && typeof raw === "object" ? raw as Record<string, unknown> : {};
  return {
    videoId: typeof data.video_id === "string" ? data.video_id : "",
    title: typeof data.title === "string" ? data.title : "",
    url: typeof data.url === "string" ? data.url : "",
    thumbnailUrl: typeof data.thumbnail_url === "string" ? data.thumbnail_url : "",
    channel: typeof data.channel === "string" ? data.channel : "",
    durationLabel: typeof data.duration_label === "string" ? data.duration_label : "",
    viewCount: typeof data.view_count === "number" ? data.view_count : 0,
    tags: Array.isArray(data.tags) ? data.tags.filter((value): value is string => typeof value === "string") : [],
    relevanceScore: typeof data.relevance_score === "number" ? data.relevance_score : 0,
  };
}
