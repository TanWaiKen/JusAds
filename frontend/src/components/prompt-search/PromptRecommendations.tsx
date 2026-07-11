/**
 * PromptRecommendations — Personalized "Recommended for you" prompt feed.
 *
 * Auto-loads on mount based on the user's profile settings (product, category,
 * audience, platform). Shows visual prompt cards. User clicks "Try it now" to
 * use a prompt. They can also search manually to override the recommendations.
 */

import React, { useEffect, useRef, useState } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { Sparkles, RefreshCw, Loader2 } from "lucide-react";
import { API_BASE } from "@/services/generationApi";
import { PromptCard } from "./PromptCard";
import { PromptSearchBox, type PromptSuggestion } from "./PromptSearchBox";

gsap.registerPlugin(useGSAP);

interface ProfileContext {
  productName?: string;
  productCategory?: string;
  targetEthnicity?: string;
  platform?: string;
  ageGroup?: string;
}

interface PromptRecommendationsProps {
  /** User's profile settings for personalized recommendations. */
  profile: ProfileContext;
  /** Called when the user clicks "Try it now" on a card. */
  onUse: (prompt: string) => void;
  /** Number of recommendation cards to show. */
  maxCards?: number;
}

async function fetchRecommendations(profile: ProfileContext, topK: number): Promise<PromptSuggestion[]> {
  const params = new URLSearchParams();
  if (profile.productName) params.set("product_name", profile.productName);
  if (profile.productCategory) params.set("product_category", profile.productCategory);
  if (profile.targetEthnicity) params.set("target_ethnicity", profile.targetEthnicity);
  if (profile.platform) params.set("platform", profile.platform);
  if (profile.ageGroup) params.set("age_group", profile.ageGroup);
  params.set("top_k", String(topK));

  try {
    const res = await fetch(`${API_BASE}/api/prompt-recommendations?${params.toString()}`);
    if (!res.ok) return [];
    const data = (await res.json()) as { recommendations?: unknown[] };
    if (!Array.isArray(data.recommendations)) return [];

    return data.recommendations.map((s) => {
      const item = s as Record<string, unknown>;
      return {
        title: typeof item.title === "string" ? item.title : "",
        description: typeof item.description === "string" ? item.description : "",
        content: typeof item.content === "string" ? item.content : "",
        score: typeof item.score === "number" ? item.score : 0,
        sourceMedia: typeof item.source_media === "string" ? item.source_media : "",
        sourceLink: typeof item.source_link === "string" ? item.source_link : "",
      };
    });
  } catch {
    return [];
  }
}

export function PromptRecommendations({
  profile,
  onUse,
  maxCards = 6,
}: PromptRecommendationsProps): React.ReactElement {
  const containerRef = useRef<HTMLDivElement>(null);
  const [recommendations, setRecommendations] = useState<PromptSuggestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [showSearch, setShowSearch] = useState(false);

  // Auto-load recommendations based on profile on mount.
  // Cache in sessionStorage so they persist across tab switches and page navigations
  // without re-fetching every time (same result for entire session).
  useEffect(() => {
    const cacheKey = `prompt_recs_${profile.productName}_${profile.productCategory}_${profile.targetEthnicity}_${profile.platform}_${profile.ageGroup}`;

    // Try loading from session cache first
    try {
      const cached = sessionStorage.getItem(cacheKey);
      if (cached) {
        const parsed = JSON.parse(cached) as PromptSuggestion[];
        if (parsed.length > 0) {
          setRecommendations(parsed);
          setLoading(false);
          return;
        }
      }
    } catch {}

    let cancelled = false;
    setLoading(true);
    fetchRecommendations(profile, maxCards).then((results) => {
      if (!cancelled) {
        setRecommendations(results);
        setLoading(false);
        // Save to session cache
        try { sessionStorage.setItem(cacheKey, JSON.stringify(results)); } catch {}
      }
    });
    return () => { cancelled = true; };
  }, [profile.productName, profile.productCategory, profile.targetEthnicity, profile.platform, profile.ageGroup, maxCards]);

  useGSAP(
    () => {
      if (recommendations.length > 0) {
        gsap.from(".prompt-card", {
          y: 20,
          autoAlpha: 0,
          stagger: 0.08,
          duration: 0.4,
          ease: "power2.out",
        });
      }
    },
    { scope: containerRef, dependencies: [recommendations.length] }
  );

  const handleRefresh = (): void => {
    setLoading(true);
    fetchRecommendations(profile, maxCards).then((results) => {
      setRecommendations(results);
      setLoading(false);
    });
  };

  return (
    <div ref={containerRef} className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-sm font-bold text-foreground">
          <Sparkles size={16} className="text-primary" />
          Recommended for you
        </h3>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowSearch((v) => !v)}
            className="text-[10px] font-medium text-muted-foreground hover:text-primary transition-colors cursor-pointer"
          >
            {showSearch ? "Hide search" : "Search other prompts"}
          </button>
          <button
            type="button"
            onClick={handleRefresh}
            disabled={loading}
            className="inline-flex h-7 w-7 items-center justify-center rounded-md border hover:bg-muted transition-colors cursor-pointer disabled:opacity-50"
            title="Refresh recommendations"
          >
            <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
          </button>
        </div>
      </div>

      {/* Optional manual search */}
      {showSearch && (
        <PromptSearchBox onSelect={onUse} maxResults={4} placeholder="Search for a different style..." />
      )}

      {/* Loading state */}
      {loading && (
        <div className="flex items-center justify-center py-8">
          <Loader2 size={20} className="animate-spin text-muted-foreground" />
          <span className="ml-2 text-xs text-muted-foreground">Loading recommendations...</span>
        </div>
      )}

      {/* Recommendation grid */}
      {!loading && recommendations.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {recommendations.map((suggestion, idx) => (
            <PromptCard key={idx} suggestion={suggestion} onUse={onUse} />
          ))}
        </div>
      )}

      {!loading && recommendations.length === 0 && (
        <p className="text-xs text-muted-foreground text-center py-6">
          No prompt templates found. Try searching manually above.
        </p>
      )}
    </div>
  );
}

export default PromptRecommendations;
