import { useState } from "react";
import { 
  ShieldCheck, 
  AlertTriangle, 
  CheckCircle, 
  Video, 
  Image as ImageIcon,
  Sparkles,
  Loader2,
  CheckCircle2
} from "lucide-react";
import { complianceService } from "../services/complianceService";
import type { ComplianceQueueItem } from "../services/complianceService";

export default function DashboardCompliance() {
  const [queue, setQueue] = useState<ComplianceQueueItem[]>(() => complianceService.getDefaultQueue());
  const [selectedId, setSelectedId] = useState<string>("ramadan_promo");
  const [fixingId, setFixingId] = useState<string | null>(null);
  const [fixedItems, setFixedItems] = useState<Record<string, boolean>>({});

  const selectedItem = queue.find(q => q.id === selectedId) || queue[0];
  const isItemFixed = fixedItems[selectedItem.id];

  const handleApplyFix = async () => {
    setFixingId(selectedItem.id);
    try {
      await complianceService.applyAutoFix(selectedItem.id);
      setFixedItems(prev => ({
        ...prev,
        [selectedItem.id]: true
      }));
      // Update item status in queue
      setQueue(prev => 
        prev.map(item => 
          item.id === selectedItem.id 
            ? { ...item, status: "Ready to Publish" } 
            : item
        )
      );
    } catch {
      // Mock error handling
    } finally {
      setFixingId(null);
    }
  };

  return (
    <div className="flex flex-col lg:flex-row h-[calc(100vh-68px)] overflow-hidden animate-in fade-in duration-300">
      
      {/* Left Column: Active Queue Listing */}
      <div className="w-full lg:w-[320px] bg-[#fafafa] dark:bg-[#111116] border-b lg:border-b-0 lg:border-r border-gray-200 dark:border-white/10 flex flex-col h-1/2 lg:h-full shrink-0">
        <div className="p-5 border-b border-gray-200 dark:border-white/10">
          <h2 className="text-[16px] font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <ShieldCheck size={16} className="text-[#0080FF]" /> Compliance Queue
          </h2>
          <p className="text-[12px] text-gray-500 mt-1">
            Review cultural & legal risks in Malaysia.
          </p>
        </div>

        {/* Stats Panel summary */}
        <div className="grid grid-cols-3 gap-2 px-5 py-4 border-b border-gray-200 dark:border-white/5 bg-gray-50 dark:bg-black/10 text-center">
          <div className="space-y-0.5">
            <span className="text-[10px] font-bold text-gray-400 block uppercase">Ready</span>
            <span className="text-[14px] font-extrabold text-emerald-500">
              {queue.filter(q => q.status === "Ready to Publish").length}
            </span>
          </div>
          <div className="space-y-0.5 border-l border-r border-gray-200 dark:border-white/5">
            <span className="text-[10px] font-bold text-gray-400 block uppercase">Attention</span>
            <span className="text-[14px] font-extrabold text-amber-500">
              {queue.filter(q => q.status === "Needing Attention").length}
            </span>
          </div>
          <div className="space-y-0.5">
            <span className="text-[10px] font-bold text-gray-400 block uppercase">Pending</span>
            <span className="text-[14px] font-extrabold text-blue-500">
              {queue.filter(q => q.status === "Checks Pending").length}
            </span>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {queue.map(item => {
            const isSelected = selectedId === item.id;
            const isItemFixedLocal = fixedItems[item.id];
            return (
              <button
                key={item.id}
                onClick={() => setSelectedId(item.id)}
                className={`w-full text-left p-4 rounded-xl border transition-all cursor-pointer ${
                  isSelected
                    ? "bg-white dark:bg-[#181822] border-[#0080FF] shadow-sm"
                    : "bg-transparent border-transparent hover:border-gray-200 dark:hover:border-white/5"
                }`}
              >
                <div className="flex items-center gap-2 mb-1.5">
                  {item.file.endsWith(".mp4") ? (
                    <Video size={14} className="text-gray-400 shrink-0" />
                  ) : (
                    <ImageIcon size={14} className="text-gray-400 shrink-0" />
                  )}
                  <h3 className="text-[14px] font-bold text-gray-900 dark:text-white truncate">
                    {item.title}
                  </h3>
                </div>
                
                <div className="flex justify-between items-center text-[12px] mt-2">
                  <span className="text-gray-400 font-mono text-[11px] truncate max-w-[140px]">{item.file}</span>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                    isItemFixedLocal || item.status === "Ready to Publish"
                      ? "bg-emerald-50 dark:bg-emerald-950/20 text-emerald-600"
                      : item.status === "Checks Pending"
                      ? "bg-blue-50 dark:bg-blue-950/20 text-blue-500"
                      : "bg-amber-50 dark:bg-amber-950/20 text-amber-600 animate-pulse"
                  }`}>
                    {isItemFixedLocal ? "Ready to Publish" : item.status}
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Center Column: Issues Queue Detail */}
      <div className="flex-1 min-w-0 overflow-y-auto p-8 bg-white dark:bg-[#0a0a0f] border-b lg:border-b-0 lg:border-r border-gray-200 dark:border-white/10 h-1/2 lg:h-full">
        <div className="max-w-2xl space-y-8">
          
          <div className="border-b border-gray-100 dark:border-white/5 pb-5">
            <span className="text-[11px] font-bold uppercase tracking-widest text-[#0080FF]">Active Compliance Report</span>
            <div className="flex items-center justify-between gap-4 mt-1">
              <div>
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{selectedItem.title}</h1>
                <p className="text-xs text-gray-400 font-mono">{selectedItem.file}</p>
              </div>

              {isItemFixed || selectedItem.issues.length === 0 ? (
                <span className="flex items-center gap-1 text-xs font-semibold text-emerald-600 bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-100 dark:border-emerald-900/40 px-3 py-1 rounded-full shrink-0">
                  <CheckCircle size={14} /> Approved for Ship
                </span>
              ) : (
                <span className="flex items-center gap-1 text-xs font-semibold text-amber-600 bg-amber-50 dark:bg-amber-950/20 border border-amber-100 dark:border-amber-900/40 px-3 py-1 rounded-full shrink-0">
                  <AlertTriangle size={14} /> Attention Needed
                </span>
              )}
            </div>
          </div>

          {/* Issues List */}
          {selectedItem.issues.length === 0 || isItemFixed ? (
            <div className="bg-emerald-50/50 dark:bg-emerald-950/10 border border-emerald-100 dark:border-emerald-900/10 rounded-2xl p-8 text-center flex flex-col items-center justify-center space-y-3">
              <CheckCircle2 size={42} className="text-emerald-500" />
              <h3 className="text-[16px] font-bold text-emerald-700 dark:text-emerald-400">All checks pass!</h3>
              <p className="text-[13px] text-emerald-600/80 dark:text-emerald-500 max-w-sm leading-relaxed">
                {isItemFixed 
                  ? "AI Auto-Fix successfully modified background symbols and increased typography contrast indexes to align with Malaysia's MCMC standards."
                  : "Creative meets all brand safety requirements. Low text ratio and ideal color contrasts verified successfully."
                }
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              {selectedItem.issues.map((issue, idx) => (
                <div key={idx} className="p-5 rounded-2xl bg-white dark:bg-[#111116] border border-gray-200 dark:border-white/10 shadow-xs space-y-4">
                  <div className="flex gap-3 items-start">
                    <span className="p-1.5 rounded-lg bg-amber-50 dark:bg-amber-950/20 text-amber-600 mt-0.5 shrink-0">
                      <AlertTriangle size={16} />
                    </span>
                    <div className="space-y-1">
                      <h4 className="text-[14px] font-bold text-gray-900 dark:text-white">{issue.type}</h4>
                      <p className="text-[13px] text-gray-500 dark:text-gray-400 leading-relaxed font-semibold">
                        {issue.description}
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-3 border-t border-gray-50 dark:border-white/5 text-[12px]">
                    <div className="space-y-1 p-3 bg-red-50/40 dark:bg-red-950/10 border border-red-100/50 dark:border-red-900/10 rounded-xl">
                      <span className="font-bold text-red-500 block">Original Hook</span>
                      <p className="text-gray-600 dark:text-gray-400 font-semibold">{issue.original}</p>
                    </div>
                    <div className="space-y-1 p-3 bg-emerald-50/40 dark:bg-emerald-950/10 border border-emerald-100/50 dark:border-emerald-900/10 rounded-xl">
                      <span className="font-bold text-emerald-600 dark:text-emerald-400 block">AI Suggestion</span>
                      <p className="text-gray-600 dark:text-gray-400 font-semibold">{issue.suggested}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

        </div>
      </div>

      {/* Right Column: Fix Panel */}
      <div className="w-full lg:w-[320px] bg-[#fafafa] dark:bg-[#111116] flex flex-col h-1/2 lg:h-full shrink-0">
        <div className="p-5 border-b border-gray-200 dark:border-white/10">
          <h2 className="text-[16px] font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <Sparkles size={16} className="text-amber-500" /> Compliance Remediation
          </h2>
          <p className="text-[12px] text-gray-500 mt-1">
            Resolve MCMC and contrast issues in 1-click.
          </p>
        </div>

        <div className="flex-1 overflow-y-auto p-6 flex flex-col justify-between">
          <div className="space-y-4">
            <div className="p-4 bg-white dark:bg-black/20 border border-gray-200 dark:border-white/10 rounded-xl space-y-3">
              <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 block">Current Action</span>
              {selectedItem.issues.length === 0 || isItemFixed ? (
                <div className="text-[13px] font-semibold text-emerald-600 flex items-center gap-1.5">
                  <CheckCircle size={15} /> Asset is completely ready
                </div>
              ) : (
                <div className="text-[13px] font-semibold text-amber-500 flex items-center gap-1.5 animate-pulse">
                  <AlertTriangle size={15} /> {selectedItem.issues.length} flagged regulations
                </div>
              )}
              <p className="text-[11px] text-gray-500 leading-relaxed">
                {selectedItem.issues.length === 0 || isItemFixed
                  ? "This asset meets all necessary guidelines. You can deploy it into your active global campaigns."
                  : "Using generative AI, we can automatically adjust visual artwork layers and text overlays to resolve MCMC Content Code Violations."
                }
              </p>
            </div>
          </div>

          {selectedItem.issues.length > 0 && !isItemFixed && (
            <div className="pt-6">
              <button
                onClick={handleApplyFix}
                disabled={fixingId !== null}
                className="w-full flex items-center justify-center gap-2 bg-[#171717] dark:bg-white text-white dark:text-[#171717] font-semibold text-[13px] py-2.5 rounded-lg hover:bg-black/90 dark:hover:bg-white/90 active:scale-[0.98] transition-all cursor-pointer shadow-xs disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {fixingId !== null ? (
                  <>
                    <Loader2 size={14} className="animate-spin" /> Remediating...
                  </>
                ) : (
                  <>
                    <Sparkles size={14} /> Apply AI Auto-Fix
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      </div>

    </div>
  );
}
