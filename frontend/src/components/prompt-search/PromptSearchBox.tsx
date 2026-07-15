/**
 * PromptSearchBox — Vector-powered prompt template search.
 *
 * Queries the backend `/api/prompt-suggestions?query=...` endpoint (backed by
 * Qdrant + Titan v2 embeddings) and displays ranked template suggestions.
 * Can be used in the Assets page (browse prompts) or the Generation canvas
 * (find a starting template for your ad).
 */

import React, { useRef, useState, useCallback } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { Search, Sparkles, Copy, ExternalLink, Loader2 } from "lucide-react";
import { API_BASE } from "@/services/generationApi";

gsap.registerPlugin(useGSAP);

export interface PromptSuggestion {
  title: string;
  description: string;
  content: string;
  score: number;
  sourceMedia: string;
  sourceLink: string;
}

interface PromptSearchBoxProps {
  /** Called when the user clicks "Use" on a prompt suggestion. */
  onSelect?: (prompt: string) => void;
  /** Placeholder text for the search input. */
  placeholder?: string;
  /** Maximum results to show. */
  maxResults?: number;
}

async function searchPrompts(query: string, topK: number): Promise<PromptSuggestion[]> {
  try {
    const res = await fetch(
      `${API_BASE}/api/prompt-suggestions?query=${encodeURIComponent(query)}&top_k=${topK}`
    );
    if (!res.ok) return [];
    const data = (await res.json()) as { suggestions?: unknown[] };
    if (!Array.isArray(data.suggestions)) return [];

    return data.suggestions.map((s) => {
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

export function PromptSearchBox({
  onSelect,
  placeholder = "Search prompt templates (e.g. 'coffee shop poster', 'TikTok product hook')...",
  maxResults = 8,
}: PromptSearchBoxProps): React.ReactElement {
  const containerRef = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<PromptSuggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useGSAP(
    () => {
      if (results.length > 0) {
        gsap.from(".prompt-card", {
          y: 12,
          autoAlpha: 0,
          stagger: 0.06,
          duration: 0.3,
          ease: "power2.out",
        });
      }
    },
    { scope: containerRef, dependencies: [results.length] }
  );

  const handleSearch = useCallback(
    (value: string) => {
      setQuery(value);
      if (debounceRef.current) clearTimeout(debounceRef.current);

      if (!value.trim()) {
        setResults([]);
        setSearched(false);
        return;
      }

      debounceRef.current = setTimeout(async () => {
        setLoading(true);
        const suggestions = await searchPrompts(value.trim(), maxResults);
        setResults(suggestions);
        setSearched(true);
        setLoading(false);
      }, 400);
    },
    [maxResults]
  );

  const handleCopy = (content: string): void => {
    navigator.clipboard.writeText(content);
  };

  return (
    <div ref={containerRef} className="flex flex-col gap-3 w-full">
      {/* Search input — larger for easy access */}
      <div className="relative">
        <Search size={18} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <input
          type="text"
          value={query}
          onChange={(e) => handleSearch(e.target.value)}
          placeholder={placeholder}
          className="w-full rounded-xl border bg-background pl-11 pr-4 py-3.5 text-base placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50"
        />
        {loading && (
          <Loader2 size={18} className="absolute right-3.5 top-1/2 -translate-y-1/2 animate-spin text-muted-foreground" />
        )}
      </div>

      {/* Results */}
      {searched && results.length === 0 && !loading && (
        <p className="text-xs text-muted-foreground text-center py-4">
          No matching prompts found. Try a different search term.
        </p>
      )}

      {results.length > 0 && (
        <div className="flex flex-col gap-3 max-h-[500px] overflow-y-auto">
          {results.map((suggestion, idx) => (
            <div
              key={idx}
              className="prompt-card flex flex-col gap-2 rounded-xl border bg-card p-4 shadow-sm hover:border-primary/40 transition-colors"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Sparkles size={14} className="text-primary shrink-0" />
                  <span className="text-sm font-semibold text-foreground line-clamp-1">
                    {suggestion.title}
                  </span>
                </div>
                <span className="shrink-0 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold text-primary">
                  {Math.round(suggestion.score * 100)}%
                </span>
              </div>

              {suggestion.description && (
                <p className="text-xs text-muted-foreground line-clamp-2">
                  {suggestion.description}
                </p>
              )}

              {suggestion.content && (
                <pre className="mt-1 max-h-28 overflow-y-auto rounded-lg bg-muted/50 p-3 text-[11px] text-foreground whitespace-pre-wrap font-mono leading-relaxed">
                  {suggestion.content.slice(0, 400)}
                  {suggestion.content.length > 400 ? "..." : ""}
                </pre>
              )}

              <div className="flex items-center gap-2 mt-1.5">
                {onSelect && (
                  <button
                    type="button"
                    onClick={() => onSelect(suggestion.content || suggestion.description)}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 transition-colors cursor-pointer"
                  >
                    <Sparkles size={12} />
                    Use this prompt
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => handleCopy(suggestion.content || suggestion.description)}
                  className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                  title="Copy prompt to clipboard"
                >
                  <Copy size={12} />
                  Copy
                </button>
                {suggestion.sourceLink && (
                  <a
                    href={suggestion.sourceLink}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-primary transition-colors"
                    title="View source"
                  >
                    <ExternalLink size={12} />
                    Source
                  </a>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default PromptSearchBox;
