/**
 * DashboardAssets — User's generated assets + prompt library.
 *
 * Two tabs:
 *   "My Assets" — real generated ads from the user's projects (fetched from DB)
 *   "Asset Library" — prompt recommendations feed (vector search)
 */

import { useState, useRef, useEffect } from "react";
import {
  FolderOpen,
  Search,
  Image as ImageIcon,
  Video,
  Volume2,
  FileText,
  Loader2,
  ExternalLink,
} from "lucide-react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { PromptRecommendations } from "@/components/prompt-search/PromptRecommendations";
import { API_BASE } from "@/services/generationApi";
import { useAuth } from "@/hooks/useAuth";

gsap.registerPlugin(useGSAP);

interface UserAsset {
  id: string;
  mediaType: string;
  platform: string;
  publicUrl: string;
  promptUsed: string;
  status: string;
  createdAt: string;
  projectId: string;
  taskId: string;
}

const MEDIA_ICONS: Record<string, typeof ImageIcon> = {
  image: ImageIcon,
  video: Video,
  audio: Volume2,
  text: FileText,
};

export default function DashboardAssets() {
  const { user } = useAuth();
  const [assets, setAssets] = useState<UserAsset[]>([]);
  const [loadingAssets, setLoadingAssets] = useState(true);
  const [activeTab, setActiveTab] = useState<"my-assets" | "library">("my-assets");
  const [searchTerm, setSearchTerm] = useState("");
  const [typeFilter, setTypeFilter] = useState("All");

  const containerRef = useRef<HTMLDivElement>(null);

  // Fetch real generated ads from all user projects (cached — only fetches once per mount).
  useEffect(() => {
    const email = user?.profile?.email;
    if (!email) return;
    if (assets.length > 0) return; // Already loaded — don't re-fetch on re-render.
    setLoadingAssets(true);
    fetch(`${API_BASE}/api/user-assets?user_email=${encodeURIComponent(email)}&limit=100`)
      .then((res) => (res.ok ? res.json() : { assets: [] }))
      .then((data) => {
        const raw = data.assets || [];
        setAssets(
          raw.map((r: Record<string, unknown>) => ({
            id: String(r.id || ""),
            mediaType: String(r.media_type || ""),
            platform: String(r.platform || ""),
            publicUrl: String(r.public_url || ""),
            promptUsed: String(r.prompt_used || ""),
            status: String(r.status || ""),
            createdAt: String(r.created_at || ""),
            projectId: String(r.project_id || ""),
            taskId: String(r.task_id || ""),
          }))
        );
      })
      .catch(() => setAssets([]))
      .finally(() => setLoadingAssets(false));
  }, [user?.profile?.email]);

  useGSAP(
    () => {
      if (assets.length > 0) {
        gsap.from(".asset-card", {
          y: 16,
          autoAlpha: 0,
          stagger: 0.06,
          duration: 0.4,
          ease: "power2.out",
        });
      }
    },
    { scope: containerRef, dependencies: [assets.length, activeTab] }
  );

  const filteredAssets = assets.filter((a) => {
    const matchesSearch =
      a.promptUsed.toLowerCase().includes(searchTerm.toLowerCase()) ||
      a.platform.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesType = typeFilter === "All" || a.mediaType === typeFilter.toLowerCase();
    return matchesSearch && matchesType;
  });

  return (
    <div ref={containerRef} className="flex flex-col h-[calc(100vh-68px)] overflow-hidden">
      {/* Header */}
      <div className="border-b px-8 py-5 bg-background">
        <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
          <FolderOpen size={20} className="text-primary" />
          Assets
        </h2>
        <p className="text-xs text-muted-foreground mt-1">
          Browse your generated ad creatives and discover prompt templates.
        </p>
      </div>

      {/* Tab switcher */}
      <div className="flex border-b px-8 bg-background">
        <button
          onClick={() => setActiveTab("my-assets")}
          className={`py-3 px-4 text-xs font-semibold border-b-2 transition-colors cursor-pointer ${
            activeTab === "my-assets"
              ? "text-foreground border-foreground"
              : "text-muted-foreground border-transparent hover:text-foreground"
          }`}
        >
          My Assets
          {assets.length > 0 && (
            <span className="ml-1.5 rounded-full bg-muted px-1.5 py-0.5 text-[10px]">
              {assets.length}
            </span>
          )}
        </button>
        <button
          onClick={() => setActiveTab("library")}
          className={`py-3 px-4 text-xs font-semibold border-b-2 transition-colors cursor-pointer ${
            activeTab === "library"
              ? "text-foreground border-foreground"
              : "text-muted-foreground border-transparent hover:text-foreground"
          }`}
        >
          Asset Library
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-8">
        {activeTab === "my-assets" ? (
          <div className="max-w-5xl space-y-5">
            {/* Search + filter */}
            <div className="flex items-center gap-3">
              <div className="relative flex-1">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="text"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  placeholder="Search by prompt or platform..."
                  className="w-full rounded-lg border bg-background pl-9 pr-4 py-2 text-xs placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50"
                />
              </div>
              <select
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                className="rounded-lg border bg-background px-3 py-2 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50"
              >
                <option value="All">All Types</option>
                <option value="image">Image</option>
                <option value="video">Video</option>
                <option value="audio">Audio</option>
                <option value="text">Text</option>
              </select>
            </div>

            {/* Loading */}
            {loadingAssets && (
              <div className="flex items-center justify-center py-12">
                <Loader2 size={20} className="animate-spin text-muted-foreground" />
                <span className="ml-2 text-xs text-muted-foreground">Loading your assets...</span>
              </div>
            )}

            {/* Empty state */}
            {!loadingAssets && filteredAssets.length === 0 && (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <FolderOpen size={40} className="text-muted-foreground/30 mb-3" />
                <p className="text-sm text-muted-foreground">No generated assets yet.</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Generate ads in a task and they'll appear here.
                </p>
              </div>
            )}

            {/* Asset grid */}
            {!loadingAssets && filteredAssets.length > 0 && (
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                {filteredAssets.map((asset) => {
                  const Icon = MEDIA_ICONS[asset.mediaType] || FileText;
                  return (
                    <div
                      key={asset.id}
                      className="asset-card flex flex-col overflow-hidden rounded-xl border bg-card shadow-sm hover:shadow-md transition-shadow"
                    >
                      {/* Preview */}
                      {asset.mediaType === "image" && asset.publicUrl ? (
                        <img
                          src={asset.publicUrl}
                          alt={asset.promptUsed.slice(0, 40)}
                          className="h-36 w-full object-cover"
                          loading="lazy"
                        />
                      ) : asset.mediaType === "video" && asset.publicUrl ? (
                        <video
                          src={asset.publicUrl}
                          className="h-36 w-full object-cover bg-black"
                          muted
                        />
                      ) : (
                        <div className="flex h-36 w-full items-center justify-center bg-muted/50">
                          <Icon size={28} className="text-muted-foreground/40" />
                        </div>
                      )}

                      {/* Info */}
                      <div className="flex flex-col gap-1.5 p-3">
                        <div className="flex items-center justify-between">
                          <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[9px] font-bold text-primary uppercase">
                            {asset.mediaType}
                          </span>
                          <span className="text-[9px] text-muted-foreground">
                            {asset.platform}
                          </span>
                        </div>
                        <p className="text-[10px] text-foreground line-clamp-2">
                          {asset.promptUsed || "Generated ad"}
                        </p>
                        <p className="text-[9px] text-muted-foreground">
                          {new Date(asset.createdAt).toLocaleDateString("en-MY", {
                            month: "short",
                            day: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </p>
                        {asset.publicUrl && (
                          <a
                            href={asset.publicUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-[9px] text-primary hover:underline mt-1"
                          >
                            <ExternalLink size={9} />
                            View full size
                          </a>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        ) : (
          /* Asset Library tab — prompt recommendations */
          <div className="max-w-5xl">
            <PromptRecommendations
              profile={{}}
              onUse={(prompt) => {
                navigator.clipboard.writeText(prompt);
              }}
              maxCards={6}
            />
          </div>
        )}
      </div>
    </div>
  );
}
