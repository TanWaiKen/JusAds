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
import { getPromptRecommendations } from "@/services/mediaService";
import type { PromptRecommendationContext } from "@/models/generation";
import { PromptCard } from "./PromptCard";
import { PromptSearchBox, type PromptSuggestion } from "./PromptSearchBox";

gsap.registerPlugin(useGSAP);

type ProfileContext = PromptRecommendationContext & { userEmail?: string };

interface PromptRecommendationsProps {
  /** User's profile settings for personalized recommendations. */
  profile: ProfileContext;
  /** Called when the user clicks "Try it now" on a card. */
  onUse: (prompt: string, suggestion: PromptSuggestion) => void;
  /** Number of recommendation cards to show. */
  maxCards?: number;
}

export function PromptRecommendations({
  profile,
  onUse,
  maxCards = 6,
}: PromptRecommendationsProps): React.ReactElement {
  const containerRef = useRef<HTMLDivElement>(null);
  const [recommendations, setRecommendations] = useState<PromptSuggestion[]>([]);
  const [loading, setLoading] = useState(true);

  // Auto-load recommendations based on profile on mount.
  // Cache in sessionStorage so they persist across tab switches and page navigations
  // without re-fetching every time (same result for entire session).
  useEffect(() => {
    const cacheKey = `prompt_recs_${profile.productName}_${profile.productCategory}_${profile.targetEthnicity}_${profile.platform}_${profile.ageGroup}_${profile.userEmail}`;

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
    getPromptRecommendations(profile, maxCards).catch(() => []).then((results) => {
      if (!cancelled) {
        setRecommendations(results);
        setLoading(false);
        // Save to session cache
        try { sessionStorage.setItem(cacheKey, JSON.stringify(results)); } catch {}
      }
    });
    return () => { cancelled = true; };
  }, [profile.productName, profile.productCategory, profile.targetEthnicity, profile.platform, profile.ageGroup, profile.userEmail, maxCards]);

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
    getPromptRecommendations(profile, maxCards).catch(() => []).then((results) => {
      setRecommendations(results);
      setLoading(false);
    });
  };

  return (
    <div ref={containerRef} className="flex flex-col gap-6">
      {/* Search box permanently visible at the top */}
      <div className="space-y-2">
        <h3 className="text-sm font-semibold text-foreground">Search Prompt Library</h3>
        <PromptSearchBox onSelect={(prompt) => onUse(prompt, { title: "Searched Prompt", description: "", content: prompt, score: 1, sourceMedia: "", sourceLink: "" })} maxResults={4} placeholder="Search for a style, platform, or ad concept..." />
      </div>

      {/* Divider */}
      <div className="border-t border-border-default my-1" />

      {/* Recommendations Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-foreground">
            <Sparkles size={16} className="text-primary" />
            Recommended for you
          </h3>
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
    </div>
  );
}

export default PromptRecommendations;
