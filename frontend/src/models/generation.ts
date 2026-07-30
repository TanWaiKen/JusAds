export interface PromptSuggestion {
  title: string;
  description: string;
  content: string;
  score: number;
  sourceMedia: string;
  sourceLink: string;
}

export interface PromptRecommendationContext {
  productName?: string;
  productCategory?: string;
  targetEthnicity?: string;
  platform?: string;
  ageGroup?: string;
}

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
