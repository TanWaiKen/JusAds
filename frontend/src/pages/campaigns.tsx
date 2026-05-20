import { useState } from "react";
import { 
  Megaphone, 
  Plus, 
  Sparkles, 
  Lightbulb, 
  Film, 
  Globe, 
  Loader2, 
  CheckCircle2
} from "lucide-react";
import { campaignService } from "../services/campaignService";
import type { Campaign } from "../services/campaignService";

export default function DashboardCampaigns() {
  const [campaigns, setCampaigns] = useState<Campaign[]>(() => campaignService.getDefaultCampaigns());
  const [selectedId, setSelectedId] = useState<string>("raya_2024");
  const [isGenerating, setIsGenerating] = useState(false);
  const [genSuccess, setGenSuccess] = useState(false);
  const [newCampaignTitle, setNewCampaignTitle] = useState("");
  const [newCampaignProduct, setNewCampaignProduct] = useState("");
  const [showAddForm, setShowAddForm] = useState(false);

  const selectedCampaign = campaigns.find(c => c.id === selectedId) || campaigns[0];

  const handleGenerate = async () => {
    setIsGenerating(true);
    setGenSuccess(false);
    try {
      const generatedInsights = await campaignService.localizeCampaign(selectedId);
      // Add the new insights dynamically to the state!
      setCampaigns(prev => 
        prev.map(c => 
          c.id === selectedId 
            ? { ...c, insights: Array.from(new Set([...c.insights, ...generatedInsights])) } 
            : c
        )
      );
      setGenSuccess(true);
    } catch {
      // Mock error handling
    } finally {
      setIsGenerating(false);
    }
  };

  const handleCreateCampaign = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCampaignTitle || !newCampaignProduct) return;

    const newCampaign: Campaign = {
      id: "camp_" + Math.random().toString(36).substring(2, 11),
      title: newCampaignTitle,
      objective: "Direct Response",
      product: newCampaignProduct,
      market: "Singapore (SG)",
      status: "Draft",
      insights: [
        "Leverages eco-friendly tags popular in urban centers.",
        "Highly engaging text typography overlays."
      ],
      references: [
        "master_creative_ref.mp4"
      ]
    };

    setCampaigns([newCampaign, ...campaigns]);
    setSelectedId(newCampaign.id);
    setNewCampaignTitle("");
    setNewCampaignProduct("");
    setShowAddForm(false);
  };

  return (
    <div className="flex flex-col lg:flex-row h-[calc(100vh-68px)] overflow-hidden animate-in fade-in duration-300">
      
      {/* Left Sidebar: Campaign List */}
      <div className="w-full lg:w-[320px] bg-[#fafafa] dark:bg-[#111116] border-b lg:border-b-0 lg:border-r border-gray-200 dark:border-white/10 flex flex-col h-1/2 lg:h-full shrink-0">
        
        {/* Sidebar Header */}
        <div className="p-5 border-b border-gray-200 dark:border-white/10 flex items-center justify-between">
          <h2 className="text-[16px] font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <Megaphone size={16} className="text-[#0080FF]" /> Workspaces
          </h2>
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="p-1 rounded-[6px] hover:bg-black/5 dark:hover:bg-white/5 border border-gray-200 dark:border-white/10 text-gray-700 dark:text-gray-300 active:scale-95 transition-all cursor-pointer"
            title="Create Campaign"
          >
            <Plus size={16} />
          </button>
        </div>

        {/* Create Campaign Modal inline */}
        {showAddForm && (
          <form onSubmit={handleCreateCampaign} className="p-4 border-b border-gray-200 dark:border-white/10 bg-white dark:bg-[#15151c] space-y-3 animate-in slide-in-from-top duration-200">
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-gray-500 mb-1">Campaign Name</label>
              <input
                type="text"
                required
                value={newCampaignTitle}
                onChange={e => setNewCampaignTitle(e.target.value)}
                placeholder="Raya 2024"
                className="w-full text-xs bg-transparent border border-gray-200 dark:border-white/10 rounded-[6px] px-2.5 py-1.5 outline-hidden text-gray-900 dark:text-white focus:border-[#0080FF]"
              />
            </div>
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-gray-500 mb-1">Product</label>
              <input
                type="text"
                required
                value={newCampaignProduct}
                onChange={e => setNewCampaignProduct(e.target.value)}
                placeholder="Hydration Hampers"
                className="w-full text-xs bg-transparent border border-gray-200 dark:border-white/10 rounded-[6px] px-2.5 py-1.5 outline-hidden text-gray-900 dark:text-white focus:border-[#0080FF]"
              />
            </div>
            <div className="flex gap-2 justify-end pt-1">
              <button
                type="button"
                onClick={() => setShowAddForm(false)}
                className="px-2.5 py-1.5 text-[11px] font-semibold text-gray-500 hover:text-gray-700 cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-3 py-1.5 text-[11px] font-semibold bg-[#171717] dark:bg-white text-white dark:text-[#171717] rounded-[6px] hover:opacity-90 active:scale-95 transition-all cursor-pointer"
              >
                Create
              </button>
            </div>
          </form>
        )}

        {/* Campaign List Scrollable */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {campaigns.map(camp => (
            <button
              key={camp.id}
              onClick={() => {
                setSelectedId(camp.id);
                setGenSuccess(false);
              }}
              className={`w-full text-left p-4 rounded-xl border transition-all cursor-pointer ${
                selectedId === camp.id
                  ? "bg-white dark:bg-[#181822] border-[#0080FF] shadow-sm"
                  : "bg-transparent border-transparent hover:border-gray-200 dark:hover:border-white/5"
              }`}
            >
              <div className="flex justify-between items-start mb-1.5">
                <h3 className="text-[14px] font-semibold text-gray-900 dark:text-white truncate max-w-[170px]">
                  {camp.title}
                </h3>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full shrink-0 ${
                  camp.status === "Active" 
                    ? "bg-emerald-50 dark:bg-emerald-950/20 text-emerald-600" 
                    : camp.status === "Review"
                    ? "bg-amber-50 dark:bg-amber-950/20 text-amber-600"
                    : "bg-gray-100 dark:bg-white/5 text-gray-500"
                }`}>
                  {camp.status}
                </span>
              </div>
              <div className="flex items-center gap-1.5 text-[12px] text-gray-500 dark:text-gray-400">
                <Globe size={12} />
                <span>{camp.market}</span>
              </div>
            </button>
          ))}
        </div>

      </div>

      {/* Right Area: Campaign Detail Scrollable */}
      <div className="flex-1 min-w-0 overflow-y-auto p-8 bg-white dark:bg-[#0a0a0f] h-1/2 lg:h-full">
        <div className="max-w-3xl space-y-8">
          
          {/* Header Info */}
          <div className="flex justify-between items-start border-b border-gray-100 dark:border-white/5 pb-6">
            <div className="space-y-1">
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                {selectedCampaign.title}
              </h1>
              <p className="text-[14px] text-gray-500 dark:text-gray-400">
                Turn trend insights into structured campaign workspaces.
              </p>
            </div>
            
            <button
              onClick={handleGenerate}
              disabled={isGenerating}
              className="flex items-center gap-2 bg-[#171717] dark:bg-white text-white dark:text-[#171717] font-semibold text-[13px] px-4 py-2 rounded-lg hover:bg-black/90 dark:hover:bg-white/90 active:scale-95 transition-all shadow-md disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
            >
              {isGenerating ? (
                <>
                  <Loader2 size={14} className="animate-spin" /> Localizing...
                </>
              ) : (
                <>
                  <Sparkles size={14} /> Localize Master
                </>
              )}
            </button>
          </div>

          {/* Active Generation Panel */}
          {isGenerating && (
            <div className="rounded-xl border border-blue-200 dark:border-blue-900/40 bg-blue-50/50 dark:bg-blue-950/10 p-6 space-y-4 animate-in fade-in slide-in-from-top-4 duration-300">
              <h3 className="text-[15px] font-bold text-[#0080FF] flex items-center gap-2">
                <Loader2 size={16} className="animate-spin" /> AI Generation in Progress
              </h3>
              <p className="text-[13px] text-gray-600 dark:text-gray-400 leading-relaxed">
                Our localized engine is currently processing your references to create platform-ready variants and compliance reports for the <strong className="text-gray-900 dark:text-white">{selectedCampaign.market}</strong> market.
              </p>
              <div className="w-full h-1 bg-blue-100 dark:bg-blue-950 rounded-full overflow-hidden">
                <div className="h-full bg-[#0080FF] rounded-full animate-progress" style={{ width: "60%" }} />
              </div>
            </div>
          )}

          {/* Generation Success Panel */}
          {genSuccess && (
            <div className="rounded-xl border border-emerald-200 dark:border-emerald-900/40 bg-emerald-50/50 dark:bg-emerald-950/10 p-6 space-y-3 animate-in fade-in slide-in-from-top-4 duration-300">
              <h3 className="text-[15px] font-bold text-emerald-600 dark:text-emerald-400 flex items-center gap-2">
                <CheckCircle2 size={16} /> Ready to Ship!
              </h3>
              <p className="text-[13px] text-gray-600 dark:text-gray-400 leading-relaxed">
                Variant generation complete! 5 custom video variant drafts have been generated matching Malaysian dialect hooks and ASMR triggers. We verified compliance with Meta standards.
              </p>
              <span className="inline-block text-[11px] font-bold uppercase tracking-widest text-emerald-600 bg-emerald-100/50 dark:bg-emerald-950/30 px-2 py-0.5 rounded-full">
                Compliance Score: 98%
              </span>
            </div>
          )}

          {/* Info Details Section */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-[#fafafa] dark:bg-[#111116] rounded-xl p-5 border border-gray-200 dark:border-white/5 space-y-1">
              <span className="text-[11px] font-bold uppercase tracking-widest text-gray-400">Campaign Objective</span>
              <p className="text-[15px] font-semibold text-gray-900 dark:text-white">{selectedCampaign.objective}</p>
            </div>
            <div className="bg-[#fafafa] dark:bg-[#111116] rounded-xl p-5 border border-gray-200 dark:border-white/5 space-y-1">
              <span className="text-[11px] font-bold uppercase tracking-widest text-gray-400">Target Product</span>
              <p className="text-[15px] font-semibold text-gray-900 dark:text-white">{selectedCampaign.product}</p>
            </div>
          </div>

          {/* References & Insights Section */}
          <div className="space-y-6">
            <h3 className="text-[16px] font-bold text-gray-900 dark:text-white flex items-center gap-2">
              <Film size={16} className="text-[#FF1493]" /> Master References ({selectedCampaign.references.length})
            </h3>
            
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {selectedCampaign.references.map((ref, idx) => (
                <div key={idx} className="bg-white dark:bg-[#111116] border border-gray-200 dark:border-white/10 rounded-xl p-4 flex flex-col justify-between aspect-video relative group overflow-hidden">
                  <div className="absolute inset-0 bg-linear-to-tr from-black/40 via-transparent to-transparent pointer-events-none" />
                  <span className="p-1.5 rounded-full bg-white/15 backdrop-blur-md text-white w-fit">
                    <Film size={14} />
                  </span>
                  <span className="text-xs font-semibold text-white truncate z-10">{ref}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Trend Insights Section */}
          <div className="space-y-4">
            <h3 className="text-[16px] font-bold text-gray-900 dark:text-white flex items-center gap-2">
              <Lightbulb size={16} className="text-amber-500 animate-pulse" /> Selected Localized Insights
            </h3>

            <div className="space-y-3">
              {selectedCampaign.insights.map((insight, idx) => (
                <div key={idx} className="flex gap-3 bg-gray-50 dark:bg-black/10 border border-gray-100 dark:border-white/5 p-4 rounded-xl items-start">
                  <span className="p-1 rounded-lg bg-amber-50 dark:bg-amber-950/20 text-amber-500 mt-0.5">
                    <Sparkles size={14} />
                  </span>
                  <p className="text-[13px] text-gray-600 dark:text-gray-400 leading-relaxed">
                    {insight}
                  </p>
                </div>
              ))}
            </div>
          </div>

        </div>
      </div>

    </div>
  );
}
