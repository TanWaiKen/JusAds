/**
 * DashboardAssets — User's generated assets + uploaded reference assets.
 *
 * Two tabs:
 *   "Generated Ads" — real generated creatives from the user's projects (fetched from DB)
 *   "Upload History" — reference assets uploaded during generation (fetched from DB)
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
  Sparkles,
  UploadCloud,
} from "lucide-react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
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
  isReference?: boolean;
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
  const [activeTab, setActiveTab] = useState<"generated" | "uploaded">("generated");
  const [searchTerm, setSearchTerm] = useState("");
  const [typeFilter, setTypeFilter] = useState("All");

  const containerRef = useRef<HTMLDivElement>(null);

  // Fetch user assets from all user projects (cached — only fetches once per mount).
  useEffect(() => {
    const email = user?.profile?.email;
    if (!email) return;
    if (assets.length > 0) return;
    setLoadingAssets(true);
    fetch(`${API_BASE}/api/user-assets?user_email=${encodeURIComponent(email)}&limit=100`)
      .then((res) => (res.ok ? res.json() : { assets: [] }))
      .then((data) => {
        const raw = data.assets || [];
        setAssets(
          raw.map((r: Record<string, any>) => ({
            id: String(r.id || ""),
            mediaType: String(r.media_type || ""),
            platform: String(r.platform || ""),
            publicUrl: String(r.public_url || ""),
            promptUsed: String(r.prompt_used || ""),
            status: String(r.status || ""),
            createdAt: String(r.created_at || ""),
            projectId: String(r.project_id || ""),
            taskId: String(r.task_id || ""),
            isReference: !!r.is_reference,
          }))
        );
      })
      .catch(() => setAssets([]))
      .finally(() => setLoadingAssets(false));
  }, [user?.profile?.email]);

  useGSAP(
    () => {
      if (assets.length > 0) {
        gsap.fromTo(".asset-card", {
          y: 16,
          autoAlpha: 0,
        }, {
          y: 0,
          autoAlpha: 1,
          stagger: 0.06,
          duration: 0.4,
          ease: "power2.out",
        });
      }
    },
    { scope: containerRef, dependencies: [assets.length, activeTab] }
  );

  const generatedAssets = assets.filter((a) => !a.isReference);
  const uploadedAssets = assets.filter((a) => a.isReference);

  const filteredAssets = assets.filter((a) => {
    // Filter based on active tab
    if (activeTab === "generated" && a.isReference) return false;
    if (activeTab === "uploaded" && !a.isReference) return false;

    const matchesSearch =
      a.promptUsed.toLowerCase().includes(searchTerm.toLowerCase()) ||
      a.platform.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesType = typeFilter === "All" || a.mediaType === typeFilter.toLowerCase();
    return matchesSearch && matchesType;
  });

  return (
    <div ref={containerRef} className="flex h-[calc(100vh-68px)] flex-col overflow-hidden bg-background">
      {/* Header */}
      <div className="border-b bg-background px-8 py-6">
        <div className="mx-auto flex w-full max-w-6xl items-start justify-between gap-6">
          <div>
            <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">Creative library</p>
            <h1 className="flex items-center gap-2 font-semibold tracking-tight text-foreground">
              <FolderOpen size={23} className="text-primary" />
              Assets
            </h1>
            <p className="mt-1.5 text-sm text-muted-foreground">
              Generated creatives and reference files, in one place.
            </p>
          </div>
          <div className="hidden rounded-xl border bg-muted/30 px-3 py-2 text-right sm:block">
            <p className="text-lg font-semibold tabular-nums text-foreground">{assets.length}</p>
            <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">Total assets</p>
          </div>
        </div>
      </div>

      {/* Tab switcher */}
      <div className="border-b bg-background px-8 py-3">
        <div className="mx-auto flex w-full max-w-6xl rounded-xl bg-muted/50 p-1">
          <button
            onClick={() => setActiveTab("generated")}
            className={`flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-xs font-semibold transition-all cursor-pointer ${
              activeTab === "generated"
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Sparkles size={14} />
            Generated ads
            <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] tabular-nums">{generatedAssets.length}</span>
          </button>
          <button
            onClick={() => setActiveTab("uploaded")}
            className={`flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-xs font-semibold transition-all cursor-pointer ${
              activeTab === "uploaded"
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <UploadCloud size={14} />
            Upload history
            <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] tabular-nums">{uploadedAssets.length}</span>
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-8 py-6">
        <div className="mx-auto w-full max-w-6xl space-y-5">
          {/* Search + filter */}
          <div className="flex flex-col gap-3 rounded-2xl border bg-card p-3 shadow-sm sm:flex-row sm:items-center">
            <div className="relative flex-1">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder={activeTab === "generated" ? "Search by prompt or platform..." : "Search by file name..."}
                className="h-10 w-full rounded-xl border bg-background pl-9 pr-4 text-xs placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50"
              />
            </div>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="h-10 rounded-xl border bg-background px-3 text-xs font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50"
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
            <div className="flex min-h-[360px] flex-col items-center justify-center rounded-2xl border border-dashed bg-card px-6 text-center">
              <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                {activeTab === "generated" ? <Sparkles size={25} /> : <UploadCloud size={25} />}
              </div>
              <p className="text-base font-semibold text-foreground">
                {searchTerm || typeFilter !== "All"
                  ? "No assets match these filters."
                  : activeTab === "generated" ? "Your generated ads will appear here." : "Your reference uploads will appear here."}
              </p>
              <p className="mt-1.5 max-w-md text-sm leading-relaxed text-muted-foreground">
                {searchTerm || typeFilter !== "All"
                  ? "Try a different search term or clear the media-type filter."
                  : activeTab === "generated"
                    ? "Finish a generation task to keep its creative, prompt, and platform details in your library."
                    : "Reference images, videos, and audio uploaded in Easy or Advanced Mode are retained here for reuse."}
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
                        <div className="flex items-center gap-1.5">
                          <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[9px] font-bold text-primary uppercase">
                            {asset.mediaType}
                          </span>
                          {asset.isReference && (
                            <span className="rounded-full bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 px-2 py-0.5 text-[9px] font-bold text-slate-600 dark:text-slate-300 uppercase">
                              Reference
                            </span>
                          )}
                        </div>
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
      </div>
    </div>
  );
}
