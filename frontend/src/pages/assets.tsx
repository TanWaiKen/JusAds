import { useState } from "react";
import { 
  FolderOpen, 
  Download, 
  CheckCircle2, 
  Info, 
  Video, 
  Calendar, 
  Tag, 
  Search,
  ChevronRight
} from "lucide-react";
import { assetService } from "../services/assetService";
import type { CreativeAsset } from "../services/assetService";

export default function DashboardAssets() {
  const [assets] = useState<CreativeAsset[]>(() => assetService.getDefaultAssets());
  const [selectedId, setSelectedId] = useState<string>("aria_summer");
  const [searchTerm, setSearchTerm] = useState("");
  const [isDownloading, setIsDownloading] = useState(false);

  const selectedAsset = assets.find(a => a.id === selectedId) || assets[0];

  const filteredAssets = assets.filter(a => 
    a.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    a.campaign.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleDownload = () => {
    setIsDownloading(true);
    setTimeout(() => {
      setIsDownloading(false);
      alert(`${selectedAsset.title} download started!`);
    }, 1500);
  };

  return (
    <div className="flex flex-col lg:flex-row h-[calc(100vh-68px)] overflow-hidden animate-in fade-in duration-300">
      
      {/* Left Column: Grid Scrollable */}
      <div className="flex-1 min-w-0 bg-white dark:bg-[#0a0a0f] overflow-y-auto p-8 h-1/2 lg:h-full">
        <div className="max-w-4xl space-y-6">
          
          {/* Header & Search */}
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 pb-4 border-b border-gray-100 dark:border-white/5">
            <div className="space-y-1">
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
                <FolderOpen size={24} className="text-[#0080FF]" /> Assets Library
              </h1>
              <p className="text-[14px] text-gray-500 dark:text-gray-400">
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
                className="w-full bg-gray-50 dark:bg-black/20 text-xs pl-9 pr-4 py-2 rounded-lg border border-gray-200 dark:border-white/10 outline-hidden focus:border-[#0080FF] focus:ring-2 focus:ring-[#0080FF]/15 transition-all"
              />
            </div>
          </div>

          {/* Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6">
            {filteredAssets.map(asset => {
              const isSelected = selectedId === asset.id;
              return (
                <div
                  key={asset.id}
                  onClick={() => setSelectedId(asset.id)}
                  className={`bg-white dark:bg-[#111116] border rounded-2xl overflow-hidden shadow-xs hover:shadow-md hover:scale-[1.01] transition-all cursor-pointer flex flex-col group ${
                    isSelected 
                      ? "border-[#0080FF] ring-2 ring-[#0080FF]/15" 
                      : "border-gray-200 dark:border-white/10"
                  }`}
                >
                  {/* Aspect ratio block simulating video cover */}
                  <div className={`aspect-video w-full bg-linear-to-tr ${asset.gradient} relative flex items-center justify-center p-4 overflow-hidden`}>
                    {/* Hover effect glass */}
                    <div className="absolute inset-0 bg-black/10 group-hover:bg-black/20 transition-colors" />
                    
                    <span className="p-2.5 rounded-full bg-white/20 backdrop-blur-md text-white border border-white/20 shadow-xs z-10">
                      <Video size={18} />
                    </span>
                  </div>

                  {/* Content details */}
                  <div className="p-4 flex-1 flex flex-col justify-between">
                    <div>
                      <h3 className="text-[14px] font-bold text-gray-900 dark:text-white truncate">
                        {asset.title}
                      </h3>
                      <p className="text-[11px] font-semibold text-gray-400 truncate mt-0.5">
                        {asset.campaign}
                      </p>
                    </div>

                    <div className="flex items-center justify-between mt-4 pt-2 border-t border-gray-50 dark:border-white/5 text-[11px] text-gray-500">
                      <span>{asset.format}</span>
                      <ChevronRight size={14} className="text-gray-400 group-hover:translate-x-0.5 transition-transform" />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

        </div>
      </div>

      {/* Right Column: Asset Attribute Details */}
      <div className="w-full lg:w-[360px] bg-[#fafafa] dark:bg-[#111116] border-t lg:border-t-0 lg:border-l border-gray-200 dark:border-white/10 flex flex-col h-1/2 lg:h-full shrink-0">
        
        <div className="p-5 border-b border-gray-200 dark:border-white/10 flex items-center gap-2">
          <Info size={16} className="text-[#FF1493]" />
          <h2 className="text-[15px] font-bold text-gray-900 dark:text-white">Asset Details</h2>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Cover representation */}
          <div className={`aspect-video w-full bg-linear-to-tr ${selectedAsset.gradient} rounded-xl shadow-xs flex items-center justify-center relative p-4`}>
            <span className="p-3 rounded-full bg-white/20 backdrop-blur-md text-white shadow-md">
              <Video size={24} />
            </span>
          </div>

          {/* Details list */}
          <div className="space-y-4">
            <div className="flex justify-between items-start">
              <div>
                <h3 className="text-[16px] font-bold text-gray-900 dark:text-white">{selectedAsset.title}</h3>
                <p className="text-xs font-semibold text-[#0080FF]">{selectedAsset.campaign}</p>
              </div>
              <span className="text-xs font-semibold text-gray-500 bg-gray-100 dark:bg-white/5 px-2 py-0.5 rounded-full">{selectedAsset.size}</span>
            </div>
            
            <p className="text-[13px] text-gray-600 dark:text-gray-400 leading-relaxed font-medium">
              {selectedAsset.description}
            </p>
          </div>

          {/* Specs Grid */}
          <div className="grid grid-cols-2 gap-4 border-t border-b border-gray-200 dark:border-white/5 py-4">
            <div className="space-y-0.5">
              <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 flex items-center gap-1">
                <Calendar size={10} /> Created
              </span>
              <p className="text-xs font-bold text-gray-800 dark:text-white">{selectedAsset.created}</p>
            </div>
            <div className="space-y-0.5">
              <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 flex items-center gap-1">
                <Video size={10} /> Specs
              </span>
              <p className="text-xs font-bold text-gray-800 dark:text-white">{selectedAsset.resolution}</p>
            </div>
          </div>

          {/* Tags */}
          <div className="space-y-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 flex items-center gap-1">
              <Tag size={10} /> Tone Tags
            </span>
            <div className="flex flex-wrap gap-1.5">
              {selectedAsset.tags.map(t => (
                <span key={t} className="text-[10px] font-semibold bg-gray-100 dark:bg-white/5 border border-gray-200 dark:border-white/10 px-2 py-0.5 rounded-md text-gray-600 dark:text-gray-400">
                  {t}
                </span>
              ))}
            </div>
          </div>

          {/* Compliance Info */}
          <div className="p-4 bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-100 dark:border-emerald-900/40 rounded-xl space-y-2">
            <h4 className="text-xs font-bold text-emerald-700 dark:text-emerald-400 flex items-center gap-1.5">
              <CheckCircle2 size={14} /> Compliance: Passed
            </h4>
            <p className="text-[11.5px] text-emerald-600 dark:text-emerald-500 leading-relaxed font-semibold">
              {selectedAsset.compliance}
            </p>
          </div>

        </div>

        {/* Footer Actions */}
        <div className="p-5 border-t border-gray-200 dark:border-white/10 bg-white dark:bg-[#111116] shrink-0">
          <button
            onClick={handleDownload}
            disabled={isDownloading}
            className="w-full flex items-center justify-center gap-2 bg-[#171717] dark:bg-white text-white dark:text-[#171717] font-semibold text-[13px] py-2.5 rounded-lg hover:bg-black/90 dark:hover:bg-white/90 active:scale-[0.98] transition-all cursor-pointer disabled:opacity-50 shadow-xs"
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
