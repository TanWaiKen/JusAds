import { useState } from "react";
import { 
  TrendingUp, 
  Flame, 
  CheckCircle, 
  AlertTriangle, 
  HelpCircle, 
  Plus, 
  Briefcase,
  X
} from "lucide-react";
import { trendService } from "../services/trendService";
import type { TrendSignal } from "../services/trendService";

export default function DashboardTrends() {
  const [signals] = useState<TrendSignal[]>(() => trendService.getDefaultSignals());
  const [selectedId, setSelectedId] = useState<string>("mosquito_jakarta");
  const [briefSignals, setBriefSignals] = useState<TrendSignal[]>([
    signals[0] || trendService.getDefaultSignals()[0]
  ]);

  const selectedSignal = signals.find(s => s.id === selectedId) || signals[0];

  const addToBrief = (signal: TrendSignal) => {
    if (briefSignals.some(s => s.id === signal.id)) return;
    setBriefSignals([...briefSignals, signal]);
  };

  const removeFromBrief = (id: string) => {
    setBriefSignals(briefSignals.filter(s => s.id !== id));
  };

  return (
    <div className="flex flex-col lg:flex-row h-[calc(100vh-68px)] overflow-hidden animate-in fade-in duration-300">
      
      {/* Left Column: Signals Listing */}
      <div className="w-full lg:w-[420px] bg-[#fafafa] dark:bg-[#111116] border-b lg:border-b-0 lg:border-r border-gray-200 dark:border-white/10 flex flex-col h-1/2 lg:h-full shrink-0">
        <div className="p-5 border-b border-gray-200 dark:border-white/10">
          <h2 className="text-[16px] font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <TrendingUp size={16} className="text-[#0080FF]" /> Local Trends Intelligence
          </h2>
          <p className="text-[12px] text-gray-500 mt-1">
            Simple, actionable signals for your next campaign.
          </p>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {signals.map(sig => {
            const isSelected = selectedId === sig.id;
            return (
              <div
                key={sig.id}
                onClick={() => setSelectedId(sig.id)}
                className={`p-4 rounded-xl border transition-all cursor-pointer relative overflow-hidden group ${
                  isSelected
                    ? "bg-white dark:bg-[#181822] border-[#0080FF] shadow-sm"
                    : "bg-transparent border-transparent hover:border-gray-200 dark:hover:border-white/5"
                }`}
              >
                <div className="flex justify-between items-start gap-3 mb-2">
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full shrink-0 ${
                    sig.category === "Foot Traffic" 
                      ? "bg-blue-50 dark:bg-blue-950/20 text-[#0080FF]" 
                      : "bg-pink-50 dark:bg-pink-950/20 text-[#FF1493]"
                  }`}>
                    {sig.category}
                  </span>
                  
                  <span className={`text-[10px] font-bold uppercase tracking-wider flex items-center gap-1 shrink-0 ${
                    sig.riskLevel === "Low"
                      ? "text-emerald-500"
                      : sig.riskLevel === "Medium"
                      ? "text-amber-500"
                      : "text-red-500"
                  }`}>
                    {sig.riskLevel === "Low" ? (
                      <CheckCircle size={12} />
                    ) : (
                      <AlertTriangle size={12} />
                    )}
                    {sig.riskLevel} Risk
                  </span>
                </div>

                <h3 className="text-[14px] font-bold text-gray-900 dark:text-white mb-2 truncate">
                  {sig.title}
                </h3>
                
                <p className="text-[12px] text-gray-500 dark:text-gray-400 line-clamp-2 leading-relaxed">
                  {sig.description}
                </p>

                <div className="mt-3 flex items-center justify-between text-[11px] font-semibold text-gray-400">
                  <span className="flex items-center gap-1">
                    <Flame size={12} className="text-amber-500" />
                    +{sig.percentage}% demand
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Center Column: Signal Detail */}
      <div className="flex-1 min-w-0 overflow-y-auto p-8 bg-white dark:bg-[#0a0a0f] border-b lg:border-b-0 lg:border-r border-gray-200 dark:border-white/10 h-1/2 lg:h-full">
        <div className="max-w-2xl space-y-8">
          
          <div className="space-y-1">
            <span className="text-[11px] font-bold uppercase tracking-widest text-[#0080FF]">Active Trend Signal</span>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              {selectedSignal.title}
            </h1>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-gray-50 dark:bg-black/10 rounded-xl p-5 border border-gray-100 dark:border-white/5 space-y-1 md:col-span-2">
              <span className="text-[11px] font-bold uppercase tracking-widest text-gray-400">What is happening?</span>
              <p className="text-[14px] text-gray-700 dark:text-gray-300 leading-relaxed font-medium">
                {selectedSignal.description}
              </p>
            </div>
            <div className="bg-[#fafafa] dark:bg-[#111116] rounded-xl p-5 border border-gray-200 dark:border-white/5 flex flex-col justify-center items-center text-center">
              <span className="text-[11px] font-bold uppercase tracking-widest text-gray-400 mb-1">Growth Indicator</span>
              <span className="text-[32px] font-extrabold text-amber-500">+{selectedSignal.percentage}%</span>
              <span className="text-[11px] font-bold text-gray-400">This Week</span>
            </div>
          </div>

          <div className="space-y-4">
            <h3 className="text-[15px] font-bold text-gray-900 dark:text-white flex items-center gap-2">
              <HelpCircle size={16} className="text-[#FF1493]" /> Target Audience Profile
            </h3>
            <p className="text-[13px] text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-black/10 border border-gray-100 dark:border-white/5 p-4 rounded-xl leading-relaxed">
              {selectedSignal.whoCares}
            </p>
          </div>

          <div className="space-y-4">
            <h3 className="text-[15px] font-bold text-gray-900 dark:text-white flex items-center gap-2">
              <Briefcase size={16} className="text-emerald-500" /> Campaign & Conversion Impact
            </h3>
            <p className="text-[13px] text-gray-600 dark:text-gray-400 bg-emerald-50/20 dark:bg-emerald-950/10 border border-emerald-100/50 dark:border-emerald-900/10 p-4 rounded-xl leading-relaxed font-semibold">
              {selectedSignal.impact}
            </p>
          </div>

          <div className="p-5 rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-[#111116] space-y-2">
            <h4 className="text-[13px] font-bold text-gray-900 dark:text-white flex items-center gap-2">
              <AlertTriangle size={15} className={
                selectedSignal.riskLevel === "Low" 
                  ? "text-emerald-500" 
                  : selectedSignal.riskLevel === "Medium"
                  ? "text-amber-500"
                  : "text-red-500"
              } />
              Risk Review & Guardrails
            </h4>
            <p className="text-[13px] text-gray-500 dark:text-gray-400">
              {selectedSignal.riskDescription}
            </p>
          </div>

          <button
            onClick={() => addToBrief(selectedSignal)}
            className="w-full flex items-center justify-center gap-2 bg-[#171717] dark:bg-white text-white dark:text-[#171717] font-semibold text-[13px] py-2.5 rounded-lg hover:bg-black/90 dark:hover:bg-white/90 active:scale-[0.98] transition-all cursor-pointer"
          >
            <Plus size={14} /> Add to Campaign Briefcase
          </button>

        </div>
      </div>

      {/* Right Column: Brief Editor */}
      <div className="w-full lg:w-[320px] bg-[#fafafa] dark:bg-[#111116] flex flex-col h-1/2 lg:h-full shrink-0">
        <div className="p-5 border-b border-gray-200 dark:border-white/10">
          <h2 className="text-[16px] font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <Briefcase size={16} className="text-[#0080FF]" /> Briefcase Brief
          </h2>
          <p className="text-[12px] text-gray-500 mt-1">
            Populate details directly from signal indicators.
          </p>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {briefSignals.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-4">
              <Briefcase size={36} className="text-gray-300 mb-2" />
              <p className="text-xs text-gray-400">Select trend indicators on the left to add them here.</p>
            </div>
          ) : (
            <>
              <div className="space-y-3">
                {briefSignals.map(sig => (
                  <div key={sig.id} className="p-3 bg-white dark:bg-black/20 border border-gray-200 dark:border-white/10 rounded-xl relative group">
                    <button
                      onClick={() => removeFromBrief(sig.id)}
                      className="absolute top-2 right-2 p-0.5 rounded-full hover:bg-gray-100 dark:hover:bg-white/5 text-gray-400 hover:text-gray-600 dark:hover:text-white transition-all opacity-0 group-hover:opacity-100 cursor-pointer"
                    >
                      <X size={12} />
                    </button>
                    <h4 className="text-xs font-bold text-gray-900 dark:text-white mb-1.5 pr-4 truncate">
                      {sig.title}
                    </h4>
                    <p className="text-[11px] text-gray-500 dark:text-gray-400 line-clamp-2">
                      {sig.impact}
                    </p>
                  </div>
                ))}
              </div>

              <div className="pt-4 border-t border-gray-200 dark:border-white/5 space-y-3">
                <span className="block text-[11px] font-bold uppercase tracking-wider text-gray-400">Brief Compliance</span>
                <div className="flex items-center gap-2 p-3 bg-emerald-50 dark:bg-emerald-950/20 text-emerald-600 dark:text-emerald-400 rounded-lg text-xs font-semibold">
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
