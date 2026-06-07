import { useState, useRef } from "react";
import { 
  TrendingUp, 
  Flame, 
  CheckCircle, 
  AlertTriangle, 
  Plus, 
  Briefcase,
  X,
  Sparkles,
  HelpCircle
} from "lucide-react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { trendService } from "../services/trendService";
import type { TrendSignal } from "../services/trendService";
import { FilterBar, StatusBadge } from "@/components/layout";

gsap.registerPlugin(useGSAP);

export default function DashboardTrends() {
  const [signals] = useState<TrendSignal[]>(() => trendService.getDefaultSignals());
  const [selectedId, setSelectedId] = useState<string>("mosquito_jakarta");
  const [categoryFilter, setCategoryFilter] = useState<string>("All");
  const [briefSignals, setBriefSignals] = useState<TrendSignal[]>([
    signals[0] || trendService.getDefaultSignals()[0]
  ]);

  const containerRef = useRef<HTMLDivElement>(null);

  const selectedSignal = signals.find(s => s.id === selectedId) || signals[0];

  const filteredSignals = signals.filter(sig => {
    if (categoryFilter === "All") return true;
    return sig.category === categoryFilter;
  });

  const addToBrief = (signal: TrendSignal) => {
    if (briefSignals.some(s => s.id === signal.id)) return;
    setBriefSignals([...briefSignals, signal]);
  };

  const removeFromBrief = (id: string) => {
    setBriefSignals(briefSignals.filter(s => s.id !== id));
  };

  // Filter items for FilterBar component
  const categoryFilters = [
    { label: "All", value: "All" },
    { label: "Foot Traffic", value: "Foot Traffic" },
    { label: "Social Buzz", value: "Social Buzz" },
  ];

  // Map risk level to StatusBadge status
  const riskToBadgeStatus = (risk: string): "passed" | "warning" | "error" => {
    switch (risk) {
      case "Low": return "passed";
      case "Medium": return "warning";
      case "High":
      case "Critical":
      default: return "error";
    }
  };

  // GSAP animation on mount
  useGSAP(() => {
    const tl = gsap.timeline({ defaults: { duration: 0.5, ease: "power3.out" } });

    // Stagger signal cards entrance
    tl.from(".signal-card", {
      x: -30,
      autoAlpha: 0,
      stagger: 0.08,
      duration: 0.6
    });

    // Animate central details panel
    tl.from(".trends-details", {
      y: 20,
      autoAlpha: 0,
      duration: 0.6
    }, "-=0.35");

    // Animate briefcase sidebar panel
    tl.from(".briefcase-panel", {
      x: 30,
      autoAlpha: 0,
      duration: 0.6
    }, "-=0.4");
  }, { scope: containerRef });

  // GSAP transition when active signal changes
  useGSAP(() => {
    if (!selectedId) return;
    gsap.fromTo(".signal-content-pane", 
      { autoAlpha: 0, y: 15 },
      { autoAlpha: 1, y: 0, duration: 0.45, ease: "power2.out" }
    );
  }, { scope: containerRef, dependencies: [selectedId] });

  return (
    <div ref={containerRef} className="flex flex-col lg:flex-row h-[calc(100vh-68px)] overflow-hidden font-hanken">
      
      {/* Left Column: Signals Listing */}
      <div className="w-full lg:basis-[300px] lg:shrink-0 bg-surface-panel border-b lg:border-b-0 lg:border-r border-border-default flex flex-col h-1/2 lg:h-full">
        
        {/* Signals Header */}
        <div className="p-5 border-b border-border-default">
          <h3 className="text-[24px] font-bold text-text-heading flex items-center gap-2">
            <TrendingUp size={16} className="text-accent-blue" /> Local Trends Intelligence
          </h3>
          <p className="text-label-ui text-text-caption mt-1">
            Real-time engagement signals tailored to your profile.
          </p>
        </div>

        {/* Category Filters */}
        <div className="px-5 py-3 border-b border-border-default flex items-center gap-1.5 overflow-x-auto no-scrollbar">
          <FilterBar
            filters={categoryFilters}
            active={categoryFilter}
            onChange={setCategoryFilter}
          />
        </div>

        {/* Signals Cards Scrollable List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {filteredSignals.map(sig => {
            const isSelected = selectedId === sig.id;
            return (
              <div
                key={sig.id}
                onClick={() => setSelectedId(sig.id)}
                className={`signal-card p-4 rounded-xl border transition-all cursor-pointer relative overflow-hidden group retina-border ${
                  isSelected
                    ? "bg-surface-elevated border-[#0080FF] shadow-sm"
                    : "bg-transparent border-transparent hover:border-border-default"
                }`}
              >
                <div className="flex justify-between items-start gap-3 mb-2">
                  <span className={`text-code-xs font-bold px-2 py-0.5 rounded-full shrink-0 ${
                    sig.category === "Foot Traffic" 
                      ? "bg-blue-50 dark:bg-blue-950/20 text-accent-blue" 
                      : "bg-pink-50 dark:bg-pink-950/20 text-accent-pink"
                  }`}>
                    {sig.category}
                  </span>
                  
                  <StatusBadge status={riskToBadgeStatus(sig.riskLevel)} size="sm" />
                </div>

                <h3 className="text-label-ui font-bold text-text-heading mb-2 truncate">
                  {sig.title}
                </h3>
                
                <p className="text-label-ui text-text-body leading-relaxed">
                  {sig.description}
                </p>

                <div className="mt-3 flex items-center justify-between text-code-xs font-semibold text-text-caption">
                  <span className="flex items-center gap-1 font-bold">
                    <Flame size={12} className="text-text-caption" />
                    +{sig.percentage}% demand
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Center Column: Signal Detail Canvas */}
      <div className="trends-details flex-1 min-w-0 overflow-y-auto p-8 bg-background border-b lg:border-b-0 lg:border-r border-border-default h-1/2 lg:h-full">
        <div className="max-w-2xl space-y-8">
          
          {/* Onboarding State Top Banner from Figma spec */}
          <section className="p-6 bg-surface-panel border-l-4 border-[#0057c0] rounded-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4 retina-border shadow-xs">
            <div className="flex-1">
              <h3 className="text-[24px] font-bold text-text-heading mb-1">Personalize Your Trends</h3>
              <p className="text-label-ui text-text-caption leading-relaxed">
                Describe your brand architecture and product vertical to filter for high-conversion social video signals.
              </p>
            </div>
            <button className="bg-text-primary dark:bg-white text-white dark:text-text-primary font-semibold text-code-xs px-4 py-2 rounded-lg hover:opacity-90 active:scale-95 transition-all flex items-center gap-1.5 shrink-0 cursor-pointer">
              Describe Business
            </button>
          </section>

          {/* Active Signal Details Content Pane */}
          <div className="signal-content-pane space-y-8">
            <div className="space-y-1">
              <span className="text-code-xs font-bold uppercase tracking-widest text-accent-blue flex items-center gap-1">
                <Sparkles size={12} /> Active Trend Signal
              </span>
              <h2 className="text-[24px] font-bold text-text-heading">
                {selectedSignal.title}
              </h2>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="bg-surface-inset rounded-xl p-5 border border-border-subtle space-y-1 md:col-span-2 retina-border">
                <span className="text-code-xs font-bold uppercase tracking-widest text-text-caption">What is happening?</span>
                <p className="text-label-ui text-text-body leading-relaxed font-semibold">
                  {selectedSignal.description}
                </p>
              </div>
              <div className="bg-surface-panel rounded-xl p-5 border border-border-default flex flex-col justify-center items-center text-center retina-border card-shadow">
                <span className="text-code-xs font-bold uppercase tracking-widest text-text-caption mb-1">Growth Index</span>
                <span className="text-headline-md font-extrabold text-blue-600 dark:text-blue-500">+{selectedSignal.percentage}%</span>
                <span className="text-code-xs font-bold text-text-caption">This Week</span>
              </div>
            </div>

            <div className="space-y-4">
              <h3 className="text-[15px] font-bold text-text-heading flex items-center gap-2">
                <HelpCircle size={16} className="text-accent-pink" /> Target Audience Profile
              </h3>
              <p className="text-code-sm text-text-body bg-surface-inset border border-border-subtle p-4 rounded-xl leading-relaxed retina-border font-medium">
                {selectedSignal.whoCares}
              </p>
            </div>

            <div className="space-y-4">
              <h3 className="text-[15px] font-bold text-text-heading flex items-center gap-2">
                <Briefcase size={16} className="text-emerald-500" /> Campaign & Conversion Impact
              </h3>
              <p className="text-code-sm text-emerald-700 dark:text-emerald-400 bg-emerald-50/20 dark:bg-emerald-950/10 border border-emerald-100/50 dark:border-emerald-900/10 p-4 rounded-xl leading-relaxed font-semibold retina-border">
                {selectedSignal.impact}
              </p>
            </div>

            <div className="p-5 rounded-xl border border-border-default bg-surface-card space-y-2 retina-border card-shadow">
              <h4 className="text-code-sm font-bold text-text-heading flex items-center gap-2">
                <AlertTriangle size={15} className={
                  selectedSignal.riskLevel === "Low" 
                    ? "text-emerald-500" 
                    : selectedSignal.riskLevel === "Medium"
                    ? "text-amber-500"
                    : "text-red-500"
                } />
                Risk Review & Guardrails
              </h4>
              <p className="text-code-sm text-text-body leading-relaxed font-medium">
                {selectedSignal.riskDescription}
              </p>
            </div>

            <button
              onClick={() => addToBrief(selectedSignal)}
              className="w-full flex items-center justify-center gap-2 bg-text-primary dark:bg-white text-white dark:text-text-primary font-semibold text-code-sm py-3 rounded-lg hover:opacity-90 active:scale-[0.98] transition-all cursor-pointer shadow-md"
            >
              <Plus size={14} /> Add to Campaign Briefcase
            </button>
          </div>

        </div>
      </div>

      {/* Right Column: Briefcase Panel Sidebar */}
      <div className="briefcase-panel w-full lg:basis-[280px] lg:shrink-0 bg-surface-panel flex flex-col h-1/2 lg:h-full">
        
        {/* Sidebar Header */}
        <div className="p-5 border-b border-border-default">
          <h3 className="text-[24px] font-bold text-text-heading flex items-center gap-2">
            <Briefcase size={16} className="text-accent-blue" /> Briefcase Brief
          </h3>
          <p className="text-label-ui text-text-caption mt-1">
            Populate details directly from trend metrics.
          </p>
        </div>

        {/* Selected Signals Briefs List */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {briefSignals.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-4">
              <Briefcase size={36} className="text-gray-300 dark:text-white/10 mb-2" />
              <p className="text-xs text-text-caption">Select signals on the left, then click add to briefcase.</p>
            </div>
          ) : (
            <>
              <div className="space-y-3">
                {briefSignals.map(sig => (
                  <div key={sig.id} className="p-4 bg-surface-elevated border border-border-default rounded-xl relative group retina-border shadow-xs">
                    <button
                      onClick={() => removeFromBrief(sig.id)}
                      className="absolute top-3 right-3 p-0.5 rounded-full hover:bg-surface-inset text-text-caption hover:text-text-heading transition-all opacity-0 group-hover:opacity-100 cursor-pointer"
                    >
                      <X size={12} />
                    </button>
                    <h4 className="text-xs font-bold text-text-heading mb-1.5 pr-4 truncate">
                      {sig.title}
                    </h4>
                    <p className="text-code-xs text-text-body leading-relaxed">
                      {sig.impact}
                    </p>
                  </div>
                ))}
              </div>

              <div className="pt-4 border-t border-border-subtle space-y-3">
                <span className="block text-code-xs font-bold uppercase tracking-wider text-text-caption">Brief Compliance</span>
                <div className="flex items-center gap-2 p-3 bg-emerald-50 dark:bg-emerald-950/20 text-emerald-600 dark:text-emerald-400 rounded-lg text-xs font-semibold retina-border">
                  <CheckCircle size={14} /> Checked & Guardrails Passed
                </div>
              </div>
            </>
          )}
        </div>

      </div>

    </div>
  );
}
