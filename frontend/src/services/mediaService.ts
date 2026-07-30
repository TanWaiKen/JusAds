import { API_BASE, getApiError } from "@/lib/apiConfig";
import { authenticatedFetch, toApiRequestError } from "@/lib/apiAuth";
import { uploadReferenceAsset } from "./fileService";
import type {
  ReferenceUploadResult,
  UserAssetRecord,
} from "@/models/media";
import type {
  PromptRecommendationContext,
  PromptSuggestion,
} from "@/models/generation";

export async function getUserAssets(limit = 100): Promise<UserAssetRecord[]> {
  const response = await authenticatedFetch(`${API_BASE}/api/user-assets?limit=${Math.max(1, Math.min(limit, 100))}`);
  if (!response.ok) throw new Error(await getApiError(response, "Unable to load assets"));
  const payload = await response.json() as { assets?: UserAssetRecord[] };
  return Array.isArray(payload.assets) ? payload.assets : [];
}

export async function deleteUserAsset(assetId: string): Promise<void> {
  const response = await authenticatedFetch(`${API_BASE}/api/user-assets/${encodeURIComponent(assetId)}`, { method: "DELETE" });
  if (!response.ok) throw new Error(await getApiError(response, "Unable to delete asset"));
}

/** Upload a project-scoped reference through the authorised signed-URL flow. */
export async function uploadProjectReference(
  file: File,
  projectId: string,
  taskId?: string,
): Promise<ReferenceUploadResult> {
  return uploadReferenceAsset(file, projectId, taskId);
}

/** Search the protected prompt library. */
export async function searchPromptLibrary(query: string, topK: number): Promise<PromptSuggestion[]> {
  const params = new URLSearchParams({ query, top_k: String(topK) });
  const response = await authenticatedFetch(`${API_BASE}/api/search-prompt?${params.toString()}`);
  if (!response.ok) throw await toApiRequestError(response, "Prompt library could not be searched.");
  const payload = await response.json() as { suggestions?: unknown[] };
  return normalizePromptSuggestions(payload.suggestions);
}

/** Load personalised prompts. The backend derives the user from the bearer token. */
export async function getPromptRecommendations(
  context: PromptRecommendationContext,
  topK: number,
): Promise<PromptSuggestion[]> {
  const params = new URLSearchParams({ top_k: String(topK) });
  if (context.productName) params.set("product_name", context.productName);
  if (context.productCategory) params.set("product_category", context.productCategory);
  if (context.targetEthnicity) params.set("target_ethnicity", context.targetEthnicity);
  if (context.platform) params.set("platform", context.platform);
  if (context.ageGroup) params.set("age_group", context.ageGroup);
  const response = await authenticatedFetch(`${API_BASE}/api/prompt-recommendations?${params.toString()}`);
  if (!response.ok) throw await toApiRequestError(response, "Prompt recommendations could not be loaded.");
  const payload = await response.json() as { recommendations?: unknown[] };
  return normalizePromptSuggestions(payload.recommendations);
}

function normalizePromptSuggestions(items: unknown[] | undefined): PromptSuggestion[] {
  if (!Array.isArray(items)) return [];
  return items.flatMap((item) => {
    if (typeof item !== "object" || item === null) return [];
    const value = item as Record<string, unknown>;
    return [{
      title: typeof value.title === "string" ? value.title : "",
      description: typeof value.description === "string" ? value.description : "",
      content: typeof value.content === "string" ? value.content : "",
      score: typeof value.score === "number" ? value.score : 0,
      sourceMedia: typeof value.source_media === "string" ? value.source_media : "",
      sourceLink: typeof value.source_link === "string" ? value.source_link : "",
    }];
  });
}
