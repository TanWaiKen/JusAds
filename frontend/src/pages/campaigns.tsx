import { useState, useRef } from "react";
import { 
  Megaphone, 
  Plus, 
  Sparkles, 
  Lightbulb, 
  Film, 
  Globe, 
  Loader2, 
  CheckCircle2,
  PlayCircle
} from "lucide-react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { campaignService } from "../services/campaignService";
import type { Campaign } from "../services/campaignService";
import { FilterBar, StatusBadge } from "@/components/layout";

gsap.registerPlugin(useGSAP);

export default function DashboardCampaigns() {
  const [campaigns, setCampaigns] = useState<Campaign[]>(() => campaignService.getDefaultCampaigns());
  const [selectedId, setSelectedId] = useState<string>("raya_2024");
  const [filter, setFilter] = useState<string>("All");
  const [isGenerating, setIsGenerating] = useState(false);
  const [genSuccess, setGenSuccess] = useState(false);
  const [newCampaignTitle, setNewCampaignTitle] = useState("");
  const [newCampaignProduct, setNewCampaignProduct] = useState("");
  const [showAddForm, setShowAddForm] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);

  const selectedCampaign = campaigns.find(c => c.id === selectedId) || campaigns[0];

  const filteredCampaigns = campaigns.filter(camp => {
    if (filter === "All") return true;
    return camp.status.toLowerCase() === filter.toLowerCase();
  });

  const filterItems = [
    { label: "All", value: "All" },
    { label: "Draft", value: "Draft" },
    { label: "Active", value: "Active" },
  ];

  const handleGenerate = async () => {
    setIsGenerating(true);
    setGenSuccess(false);
    try {
      const generatedInsights = await campaignService.localizeCampaign(selectedId);
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

  // GSAP animation for entrance
  useGSAP(() => {
    const tl = gsap.timeline({ defaults: { duration: 0.5, ease: "power3.out" } });
    
    // Stagger workspace card entrances
    tl.from(".workspace-card", {
      x: -30,
      autoAlpha: 0,
      stagger: 0.08,
      duration: 0.6
    });

    // Reveal right side detail area
    tl.from(".details-container", {
      y: 25,
      autoAlpha: 0,
      duration: 0.6
    }, "-=0.35");
  }, { scope: containerRef });

  // GSAP animation for transition between campaign details
  useGSAP(() => {
    if (!selectedId) return;
    gsap.fromTo(".details-content", 
      { autoAlpha: 0, y: 15 },
      { autoAlpha: 1, y: 0, duration: 0.5, ease: "power2.out" }
    );
  }, { scope: containerRef, dependencies: [selectedId] });

  return (
    <div ref={containerRef} className="flex flex-col lg:flex-row h-[calc(100vh-68px)] overflow-hidden font-hanken">
      
      {/* Left Sidebar: Workspace Campaigns List */}
      <div className="w-full lg:w-1/4 lg:min-w-[260px] lg:max-w-[360px] bg-surface-panel border-b lg:border-b-0 lg:border-r border-border-default flex flex-col h-1/2 lg:h-full shrink-0">
        
        {/* Sidebar Header */}
        <div className="p-5 border-b border-border-default flex items-center justify-between">
          <h3 className="text-[24px] font-bold text-text-heading flex items-center gap-2">
            <Megaphone size={16} className="text-accent-blue" /> Workspaces
          </h3>
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="p-1 rounded-[6px] hover:bg-surface-inset border border-border-default text-text-body active:scale-95 transition-all cursor-pointer"
            title="Create Campaign"
          >
            <Plus size={16} />
          </button>
        </div>

        {/* Create Campaign Modal inline */}
        {showAddForm && (
          <form onSubmit={handleCreateCampaign} className="p-4 border-b border-border-default bg-surface-card space-y-3 animate-in slide-in-from-top duration-200">
            <div>
              <label className="block text-code-xs font-bold uppercase tracking-wider text-text-caption mb-1">Campaign Name</label>
              <input
                type="text"
                required
                value={newCampaignTitle}
                onChange={e => setNewCampaignTitle(e.target.value)}
                placeholder="Raya 2024"
                className="w-full text-xs bg-input-bg border border-input-border rounded-[6px] px-2.5 py-1.5 outline-hidden text-text-heading focus:border-input-focus"
              />
            </div>
            <div>
              <label className="block text-code-xs font-bold uppercase tracking-wider text-text-caption mb-1">Product</label>
              <input
                type="text"
                required
                value={newCampaignProduct}
                onChange={e => setNewCampaignProduct(e.target.value)}
                placeholder="Hydration Hampers"
                className="w-full text-xs bg-input-bg border border-input-border rounded-[6px] px-2.5 py-1.5 outline-hidden text-text-heading focus:border-input-focus"
              />
            </div>
            <div className="flex gap-2 justify-end pt-1">
              <button
                type="button"
                onClick={() => setShowAddForm(false)}
                className="px-2.5 py-1.5 text-code-xs font-semibold text-text-caption hover:text-text-body cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-3 py-1.5 text-code-xs font-semibold bg-text-primary dark:bg-white text-white dark:text-text-primary rounded-[6px] hover:opacity-90 active:scale-95 transition-all cursor-pointer"
              >
                Create
              </button>
            </div>
          </form>
        )}

        {/* Filter buttons using FilterBar shared component */}
        <div className="px-5 py-3 border-b border-border-default overflow-x-auto no-scrollbar">
          <FilterBar filters={filterItems} active={filter} onChange={setFilter} />
        </div>

        {/* Campaign List Scrollable */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {filteredCampaigns.map(camp => (
            <button
              key={camp.id}
              onClick={() => {
                setSelectedId(camp.id);
                setGenSuccess(false);
              }}
              className={`workspace-card w-full text-left p-4 rounded-xl border transition-all cursor-pointer retina-border ${
                selectedId === camp.id
                  ? "bg-surface-elevated border-[#0080FF] shadow-sm"
                  : "bg-transparent border-transparent hover:border-border-default"
              }`}
            >
              <div className="flex justify-between items-start mb-2">
                <h3 className="text-label-ui font-semibold text-text-heading">
                  {camp.title}
                </h3>
                <StatusBadge status={camp.status.toLowerCase() as "draft" | "active" | "review"} size="sm" />
              </div>
              <div className="flex items-center gap-1.5 text-label-ui text-text-caption">
                <Globe size={12} />
                <span>{camp.market}</span>
              </div>
            </button>
          ))}
        </div>

      </div>

      {/* Right Area: Campaign Detail Scrollable */}
      <div className="details-container flex-1 min-w-0 overflow-y-auto p-8 bg-background h-1/2 lg:h-full">
        <div className="details-content max-w-3xl space-y-8">
          
          {/* Header Info */}
          <div className="flex justify-between items-start border-b border-border-subtle pb-6">
            <div className="space-y-1">
              <h2 className="text-[24px] font-bold text-text-heading">
                {selectedCampaign.title}
              </h2>
              <p className="text-label-ui text-text-caption">
                Turn trend insights into structured campaign workspaces.
              </p>
            </div>
            
            <button
              onClick={handleGenerate}
              disabled={isGenerating}
              className="flex items-center gap-2 bg-text-primary dark:bg-white text-white dark:text-text-primary font-semibold text-code-sm px-4 py-2 rounded-lg hover:bg-black/90 dark:hover:bg-white/90 active:scale-95 transition-all shadow-md disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
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

          {/* Active Generation Progress */}
          {isGenerating && (
            <div className="rounded-xl border border-blue-200 dark:border-blue-900/40 bg-blue-50/50 dark:bg-blue-950/10 p-6 space-y-4 animate-in fade-in slide-in-from-top-4 duration-300">
              <h3 className="text-[15px] font-bold text-accent-blue flex items-center gap-2">
                <Loader2 size={16} className="animate-spin" /> AI Generation in Progress
              </h3>
              <p className="text-code-sm text-text-body leading-relaxed">
                Our localized engine is currently processing your references to create platform-ready variants and compliance reports for the <strong className="text-text-heading">{selectedCampaign.market}</strong> market.
              </p>
              <div className="w-full h-1.5 bg-blue-100 dark:bg-blue-950 rounded-full overflow-hidden">
                <div className="h-full bg-blue-600 dark:bg-blue-500 rounded-full" style={{ width: "60%" }} />
              </div>
            </div>
          )}

          {/* Generation Success Panel */}
          {genSuccess && (
            <div className="rounded-xl border border-emerald-200 dark:border-emerald-900/40 bg-emerald-50/50 dark:bg-emerald-950/10 p-6 space-y-3 animate-in fade-in slide-in-from-top-4 duration-300">
              <h3 className="text-[15px] font-bold text-emerald-600 dark:text-emerald-400 flex items-center gap-2">
                <CheckCircle2 size={16} /> Ready to Ship!
              </h3>
              <p className="text-code-sm text-text-body leading-relaxed">
                Variant generation complete! 5 custom video variant drafts have been generated matching Malaysian dialect hooks and ASMR triggers. We verified compliance with Meta standards.
              </p>
              <span className="inline-block text-code-xs font-bold uppercase tracking-widest text-emerald-600 bg-emerald-100/50 dark:bg-emerald-950/30 px-2.5 py-0.5 rounded-full">
                Compliance Score: 98%
              </span>
            </div>
          )}

          {/* Info Details Section */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-surface-panel rounded-xl p-5 border border-border-default space-y-1 retina-border">
              <span className="text-code-xs font-bold uppercase tracking-widest text-text-caption">Campaign Objective</span>
              <p className="text-[15px] font-semibold text-text-heading">{selectedCampaign.objective}</p>
            </div>
            <div className="bg-surface-panel rounded-xl p-5 border border-border-default space-y-1 retina-border">
              <span className="text-code-xs font-bold uppercase tracking-widest text-text-caption">Target Product</span>
              <p className="text-[15px] font-semibold text-text-heading">{selectedCampaign.product}</p>
            </div>
          </div>

          {/* References & Insights Section */}
          <div className="space-y-6">
            <h3 className="text-body-md font-bold text-text-heading flex items-center gap-2">
              <Film size={16} className="text-accent-pink" /> Master References ({selectedCampaign.references.length})
            </h3>
            
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {selectedCampaign.references.map((ref, idx) => (
                <div key={idx} className="bg-surface-card border border-border-default rounded-xl p-4 flex flex-col justify-between aspect-video relative group overflow-hidden retina-border card-shadow cursor-pointer hover:scale-[1.02] transition-all duration-300">
                  <div className="absolute inset-0 bg-linear-to-tr from-black/40 via-transparent to-transparent pointer-events-none" />
                  
                  {/* Play circle overlay like in figma specs */}
                  <div className="absolute inset-0 flex items-center justify-center bg-black/10 group-hover:bg-black/30 transition-colors">
                    <span className="p-2.5 rounded-full bg-white/20 backdrop-blur-md text-white border border-white/20 shadow-xs z-20">
                      <PlayCircle size={18} />
                    </span>
                  </div>

                  <span className="p-1.5 rounded-full bg-white/15 backdrop-blur-md text-white w-fit z-10">
                    <Film size={14} />
                  </span>
                  <span className="text-xs font-semibold text-white truncate z-10">{ref}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Trend Insights Section */}
          <div className="space-y-4">
            <h3 className="text-body-md font-bold text-text-heading flex items-center gap-2">
              <Lightbulb size={16} className="text-text-caption" /> Selected Localized Insights
            </h3>

            <div className="space-y-3">
              {selectedCampaign.insights.map((insight, idx) => (
                <div key={idx} className="flex gap-3 bg-surface-inset border border-border-subtle p-4 rounded-xl items-start retina-border">
                  <span className="p-1 rounded-lg bg-surface-inset text-text-caption mt-1">
                    <Sparkles size={14} />
                  </span>
                  <p className="text-code-sm text-text-body leading-relaxed font-semibold">
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
