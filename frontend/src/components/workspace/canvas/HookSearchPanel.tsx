/**
 * HookSearchPanel — YouTube Shorts hook video browser.
 *
 * Allows users to search for viral meme/transition Shorts clips
 * to use as creative references for the meme_shock strategy.
 * Integrates with the SettingsPanel creative style selection.
 */

import { useState, useRef, useCallback } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { Search, Play, X, Loader2 } from "lucide-react";
import { searchHookVideos, recordHookPreference } from "@/services/hookSearchApi";
import type { HookVideoResult } from "@/services/hookSearchApi";
import { useAuth } from "@/hooks/useAuth";

gsap.registerPlugin(useGSAP);

interface HookSearchPanelProps {
  creativeStyle: string;
  market: string;
  ethnicity: string;
  productCategory: string;
  onSelectHook: (video: HookVideoResult) => void;
  onClose: () => void;
}

export function HookSearchPanel({
  creativeStyle,
  market,
  ethnicity,
  productCategory,
  onSelectHook,
  onClose,
}: HookSearchPanelProps): React.ReactElement {
  const { user } = useAuth();
  const containerRef = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<HookVideoResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  useGSAP(
    () => {
      gsap.from(".hook-panel", {
        autoAlpha: 0,
        y: 12,
        scale: 0.97,
        duration: 0.35,
        ease: "power2.out",
      });
    },
    { scope: containerRef }
  );

  const handleSearch = useCallback(async () => {
    setLoading(true);
    setSearched(true);
    try {
      const response = await searchHookVideos({
        query,
        creativeStyle,
        market,
        ethnicity,
        productCategory,
        maxResults: 8,
      });
      setResults(response.results);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, [query, creativeStyle, market, ethnicity, productCategory]);

  const handleSelect = useCallback(
    (video: HookVideoResult) => {
      // Record preference for learning
      recordHookPreference({
        videoId: video.videoId,
        tags: video.tags,
        creativeStyle,
        productCategory,
        userEmail: user?.profile?.email,
      });

      onSelectHook(video);
    },
    [creativeStyle, productCategory, user?.profile?.email, onSelectHook]
  );

  return (
    <div
      ref={containerRef}
      className="absolute inset-0 z-50 flex items-center justify-center bg-[#09090b]/50 backdrop-blur-xs pointer-events-auto"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="hook-panel pointer-events-auto w-full max-w-2xl rounded-xl bg-white shadow-[rgba(0,0,0,0.08)_0px_0px_0px_1px,rgba(0,0,0,0.04)_0px_2px_2px] relative overflow-hidden max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#ebebeb] px-6 py-4 shrink-0">
          <div>
            <h2 className="!text-sm !font-bold text-[#171717] tracking-tight !m-0">
              Hook Video Search
            </h2>
            <p className="text-[10px] text-[#666666] mt-0.5">
              Find YouTube Shorts (≤60s) for creative hook references
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-7 w-7 items-center justify-center rounded-md text-[#666666] hover:bg-[#fafafa] hover:text-[#171717] transition-colors cursor-pointer"
          >
            <X size={16} />
          </button>
        </div>

        {/* Search Bar */}
        <div className="px-6 py-3 border-b border-[#ebebeb] shrink-0">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search
                size={14}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-[#808080]"
              />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleSearch();
                }}
                placeholder="e.g. car crash transition, meme reveal, food ASMR..."
                className="w-full rounded-md pl-9 pr-3 py-2 text-xs text-[#171717] shadow-[rgba(0,0,0,0.08)_0px_0px_0px_1px] placeholder:text-[#808080] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsla(212,100%,48%,1)]"
              />
            </div>
            <button
              type="button"
              onClick={handleSearch}
              disabled={loading}
              className="rounded-md bg-[#171717] px-4 py-2 text-xs font-semibold text-white hover:bg-[#333] disabled:opacity-50 transition-colors cursor-pointer"
            >
              {loading ? <Loader2 size={14} className="animate-spin" /> : "Search"}
            </button>
          </div>
          <p className="text-[10px] text-[#999] mt-1.5">
            Strategy: <span className="font-medium text-[#666]">{creativeStyle.replace("_", " ")}</span>
            {" · "}Leave empty to auto-search based on your creative style
          </p>
        </div>

        {/* Results Grid */}
        <div className="flex-1 overflow-y-auto p-4">
          {loading && (
            <div className="flex items-center justify-center py-12">
              <Loader2 size={24} className="animate-spin text-[#808080]" />
              <span className="ml-2 text-xs text-[#808080]">Searching YouTube Shorts...</span>
            </div>
          )}

          {!loading && searched && results.length === 0 && (
            <div className="text-center py-12 text-[#808080]">
              <p className="text-sm font-medium">No Shorts found</p>
              <p className="text-xs mt-1">Try different keywords or clear the query for auto-suggestions</p>
            </div>
          )}

          {!loading && results.length > 0 && (
            <div className="grid grid-cols-2 gap-3">
              {results.map((video) => (
                <div
                  key={video.videoId}
                  className="group rounded-lg border border-[#ebebeb] overflow-hidden hover:border-[#171717] hover:shadow-md transition-all cursor-pointer"
                  onClick={() => handleSelect(video)}
                >
                  {/* Thumbnail */}
                  <div className="relative aspect-[9/16] max-h-[180px] bg-[#f5f5f5] overflow-hidden">
                    {video.thumbnailUrl ? (
                      <img
                        src={video.thumbnailUrl}
                        alt={video.title}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <Play size={24} className="text-[#ccc]" />
                      </div>
                    )}
                    <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center">
                      <Play
                        size={24}
                        className="text-white opacity-0 group-hover:opacity-100 transition-opacity"
                      />
                    </div>
                  </div>
                  {/* Info */}
                  <div className="p-2">
                    <p className="text-[11px] font-medium text-[#171717] line-clamp-2 leading-tight">
                      {video.title}
                    </p>
                    <p className="text-[10px] text-[#808080] mt-0.5">{video.channel}</p>
                  </div>
                </div>
              ))}
            </div>
          )}

          {!loading && !searched && (
            <div className="text-center py-12 text-[#808080]">
              <Play size={32} className="mx-auto mb-3 text-[#ddd]" />
              <p className="text-sm font-medium">Search for hook videos</p>
              <p className="text-xs mt-1">
                Find viral Shorts clips for your ad's opening hook.
                <br />
                Click a video to use it as a reference.
              </p>
            </div>
          )}
        </div>

        {/* Footer tip */}
        {results.length > 0 && (
          <div className="border-t border-[#ebebeb] px-6 py-2.5 text-[10px] text-[#999] shrink-0">
            Click a video to select it as your hook reference. Your choices improve future recommendations.
          </div>
        )}
      </div>
    </div>
  );
}

export default HookSearchPanel;
