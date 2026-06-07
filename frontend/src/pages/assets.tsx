import { useState, useRef } from "react";
import { 
  FolderOpen, 
  Download, 
  CheckCircle2, 
  Info, 
  Video, 
  Calendar, 
  Tag, 
  Search,
  ChevronRight,
  PlayCircle
} from "lucide-react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { assetService } from "../services/assetService";
import type { CreativeAsset } from "../services/assetService";
import { StatusBadge } from "@/components/layout";

gsap.registerPlugin(useGSAP);

export default function DashboardAssets() {
  const [assets] = useState<CreativeAsset[]>(() => assetService.getDefaultAssets());
  const [selectedId, setSelectedId] = useState<string>("aria_summer");
  const [searchTerm, setSearchTerm] = useState("");
  const [assetType, setAssetType] = useState("All");
  const [campaignFilter, setCampaignFilter] = useState("All");
  const [isDownloading, setIsDownloading] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const detailPanelRef = useRef<HTMLDivElement>(null);

  const selectedAsset = assets.find(a => a.id === selectedId) || assets[0];

  const uniqueCampaigns = Array.from(new Set(assets.map(a => a.campaign)));

  const filteredAssets = assets.filter(a => {
    const matchesSearch = a.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          a.campaign.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesType = assetType === "All" || 
                        (assetType === "Video" && (a.format.includes("MP4") || a.format.includes("MOV")));
    const matchesCampaign = campaignFilter === "All" || a.campaign === campaignFilter;
    return matchesSearch && matchesType && matchesCampaign;
  });

  const handleDownload = () => {
    setIsDownloading(true);
    setTimeout(() => {
      setIsDownloading(false);
      alert(`${selectedAsset.title} download started!`);
    }, 1500);
  };

  // GSAP animation for mount
  useGSAP(() => {
    const tl = gsap.timeline({ defaults: { duration: 0.5, ease: "power3.out" } });

    // Stagger asset card grid entrances
    tl.from(".asset-card", {
      scale: 0.9,
      autoAlpha: 0,
      stagger: 0.08,
      duration: 0.6
    });

    // Slide in detail sidebar
    tl.from(".assets-detail-drawer", {
      x: 50,
      autoAlpha: 0,
      duration: 0.6
    }, "-=0.35");
  }, { scope: containerRef });

  // GSAP animation on selected asset change
  useGSAP(() => {
    if (!selectedId) return;
    gsap.fromTo(".drawer-detail-content",
      { autoAlpha: 0, x: 20 },
      { autoAlpha: 1, x: 0, duration: 0.5, ease: "power2.out" }
    );
  }, { scope: containerRef, dependencies: [selectedId] });

  return (
    <div ref={containerRef} className="flex flex-col lg:flex-row h-[calc(100vh-68px)] overflow-hidden font-hanken">
      
      {/* Left Column: Grid Scrollable */}
      <div className="flex-1 min-w-0 bg-background overflow-y-auto p-8 h-1/2 lg:h-full">
        <div className="max-w-4xl space-y-6">
          
          {/* Header & Search */}
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 pb-4 border-b border-border-subtle">
            <div className="space-y-1">
              <h2 className="text-[24px] font-bold text-text-heading flex items-center gap-2">
                <FolderOpen size={24} className="text-[#0080FF]" /> Assets Library
              </h2>
              <p className="text-label-ui text-text-caption">
                Browse creatives generated or uploaded in your workspace.
              </p>
            </div>

            <div className="relative w-full sm:w-64">
              <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-gray-400">
                <Search size={15} />
              </span>
              <input
                type="text"
                value={searchTerm}
                onChange={e => setSearchTerm(e.target.value)}
                placeholder="Search assets or campaigns..."
                className="w-full bg-input-bg text-xs pl-9 pr-4 py-2 rounded-lg border border-input-border outline-hidden focus:border-input-focus focus:ring-2 focus:ring-[#0080FF]/15 transition-all retina-border"
              />
            </div>
          </div>

          {/* Filter Bar */}
          <div className="bg-surface-card p-4 rounded-xl shadow-as-border retina-border mb-8 flex flex-wrap items-center gap-3">
            <select 
              value={assetType}
              onChange={e => setAssetType(e.target.value)}
              className="bg-input-bg border border-input-border focus:border-input-focus focus:ring-2 focus:ring-[#0080FF]/15 rounded-lg text-xs font-semibold py-2 pl-3 pr-8 text-text-heading outline-hidden cursor-pointer"
            >
              <option value="All">All Types</option>
              <option value="Video">Video Assets</option>
            </select>

            <select 
              value={campaignFilter}
              onChange={e => setCampaignFilter(e.target.value)}
              className="bg-input-bg border border-input-border focus:border-input-focus focus:ring-2 focus:ring-[#0080FF]/15 rounded-lg text-xs font-semibold py-2 pl-3 pr-8 text-text-heading outline-hidden cursor-pointer"
            >
              <option value="All">All Campaigns</option>
              {uniqueCampaigns.map(c => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>

            {(assetType !== "All" || campaignFilter !== "All" || searchTerm !== "") && (
              <button 
                onClick={() => { setAssetType("All"); setCampaignFilter("All"); setSearchTerm(""); }}
                className="text-[#0080FF] hover:underline text-xs font-bold px-2 py-2 cursor-pointer"
              >
                Clear all
              </button>
            )}
          </div>

          {/* Asset Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6">
            {filteredAssets.map(asset => {
              const isSelected = selectedId === asset.id;
              return (
                <div
                  key={asset.id}
                  onClick={() => setSelectedId(asset.id)}
                  className={`asset-card bg-surface-card border rounded-2xl overflow-hidden shadow-xs hover:shadow-md hover:scale-[1.01] transition-all cursor-pointer flex flex-col group retina-border ${
                    isSelected 
                      ? "border-[#0080FF] ring-2 ring-[#0080FF]/15" 
                      : "border-border-default"
                  }`}
                >
                  {/* Aspect ratio block simulating video cover */}
                  <div className={`aspect-video w-full bg-linear-to-tr ${asset.gradient} relative flex items-center justify-center p-4 overflow-hidden`}>
                    {/* Hover effect glass */}
                    <div className="absolute inset-0 bg-black/10 group-hover:bg-black/25 transition-colors" />
                    
                    {/* compliance badge top right */}
                    <div className="absolute top-2 right-2">
                      <StatusBadge status="passed" size="sm" />
                    </div>

                    <span className="p-2.5 rounded-full bg-white/20 backdrop-blur-md text-white border border-white/20 shadow-xs z-10">
                      <PlayCircle size={18} />
                    </span>
                  </div>

                  {/* Content details */}
                  <div className="p-4 flex-1 flex flex-col justify-between">
                    <div>
                      <h3 className="text-label-ui font-bold text-text-heading truncate">
                        {asset.title}
                      </h3>
                      <p className="text-code-xs font-semibold text-text-caption truncate mt-2">
                        {asset.campaign}
                      </p>
                    </div>

                    <div className="flex items-center justify-between mt-4 pt-2 border-t border-border-subtle text-code-xs text-text-caption">
                      <span className="font-bold">{asset.format.split(" ")[0]}</span>
                      <ChevronRight size={14} className="text-text-caption group-hover:translate-x-0.5 transition-transform" />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

        </div>
      </div>

      {/* Right Column: Asset Attribute Details Drawer */}
      <div 
        ref={detailPanelRef}
        className="assets-detail-drawer w-full lg:w-[360px] bg-surface-panel border-t lg:border-t-0 lg:border-l border-border-default flex flex-col h-1/2 lg:h-full shrink-0"
      >
        
        <div className="p-5 border-b border-border-default flex items-center gap-2">
          <Info size={16} className="text-[#FF1493]" />
          <h3 className="text-[24px] font-bold text-text-heading">Asset Details</h3>
        </div>

        <div className="drawer-detail-content flex-1 overflow-y-auto p-6 space-y-6">
          {/* Cover representation */}
          <div className={`aspect-video w-full bg-linear-to-tr ${selectedAsset.gradient} rounded-xl shadow-xs flex items-center justify-center relative p-4 card-shadow retina-border`}>
            <span className="p-3 rounded-full bg-white/20 backdrop-blur-md text-white shadow-md">
              <PlayCircle size={24} />
            </span>
          </div>

          {/* Details list */}
          <div className="space-y-4">
            <div className="flex justify-between items-start">
              <div>
                <h3 className="text-body-md font-bold text-text-heading">{selectedAsset.title}</h3>
                <p className="text-xs font-semibold text-[#0080FF]">{selectedAsset.campaign}</p>
              </div>
              <span className="text-xs font-semibold text-text-caption bg-surface-inset px-2 py-0.5 rounded-full shrink-0">{selectedAsset.size}</span>
            </div>
            
            <p className="text-code-sm text-text-body leading-relaxed font-semibold italic border-l-2 border-blue-500 pl-2">
              {selectedAsset.description}
            </p>
          </div>

          {/* Specs Grid */}
          <div className="grid grid-cols-2 gap-4 border-t border-b border-border-default py-4">
            <div className="space-y-2">
              <span className="text-label-ui font-bold uppercase tracking-wider text-text-caption flex items-center gap-1">
                <Calendar size={10} /> Created
              </span>
              <p className="text-label-ui font-bold text-text-heading">{selectedAsset.created}</p>
            </div>
            <div className="space-y-2">
              <span className="text-label-ui font-bold uppercase tracking-wider text-text-caption flex items-center gap-1">
                <Video size={10} /> Specs
              </span>
              <p className="text-label-ui font-bold text-text-heading">{selectedAsset.resolution}</p>
            </div>
          </div>

          {/* Tags */}
          <div className="space-y-2">
            <span className="text-label-ui font-bold uppercase tracking-wider text-text-caption flex items-center gap-1">
              <Tag size={10} /> Tone Tags
            </span>
            <div className="flex flex-wrap gap-1.5">
              {selectedAsset.tags.map(t => (
                <span key={t} className="text-code-xs font-semibold bg-surface-inset border border-border-default px-2.5 py-0.5 rounded-md text-text-body retina-border">
                  #{t.toUpperCase()}
                </span>
              ))}
            </div>
          </div>

          {/* Compliance Info */}
          <div className="p-4 bg-emerald-50/50 dark:bg-emerald-950/20 border border-emerald-100/50 dark:border-emerald-900/10 rounded-xl space-y-2 retina-border card-shadow">
            <h4 className="text-xs font-bold text-emerald-700 dark:text-emerald-400 flex items-center gap-1.5">
              <CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> Compliance Status: Passed
            </h4>
            <p className="text-label-ui text-text-body leading-relaxed font-semibold">
              {selectedAsset.compliance}
            </p>
          </div>

        </div>

        {/* Footer Actions */}
        <div className="p-5 border-t border-border-default bg-surface-card shrink-0">
          <button
            onClick={handleDownload}
            disabled={isDownloading}
            className="w-full flex items-center justify-center gap-2 bg-text-primary dark:bg-white text-white dark:text-text-primary font-semibold text-code-sm py-3 rounded-lg hover:opacity-90 active:scale-[0.98] transition-all cursor-pointer disabled:opacity-50 shadow-md"
          >
            {isDownloading ? (
              "Preparing Download..."
            ) : (
              <>
                <Download size={14} /> Download {selectedAsset.format.split(" ")[0]}
              </>
            )}
          </button>
        </div>

      </div>

    </div>
  );
}
