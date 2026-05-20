import { useAuth } from "../hooks/useAuth";
import { 
  Sparkles, 
  Layers, 
  Eye, 
  Send, 
  TrendingUp, 
  Clock, 
  Coins 
} from "lucide-react";

export default function DashboardHome() {
  const { user } = useAuth();
  const displayName = user?.profile.name ?? user?.profile.email ?? "Creative Lead";

  // Recent activity data
  const activities = [
    {
      title: "Bangkok Launch Ready",
      description: "Campaign localized to Thai",
      time: "2m ago",
      color: "text-emerald-500 bg-emerald-50 dark:bg-emerald-950/20"
    },
    {
      title: "New Asset Draft",
      description: "Video variant #14 generated",
      time: "14m ago",
      color: "text-[#0080FF] bg-blue-50 dark:bg-blue-950/20"
    },
    {
      title: "Policy Audit Passed",
      description: "Meta compliance verified",
      time: "1h ago",
      color: "text-purple-500 bg-purple-50 dark:bg-purple-950/20"
    }
  ];

  return (
    <div className="flex-1 overflow-y-auto flex flex-col gap-8 p-8 max-w-5xl mx-auto w-full animate-in fade-in slide-in-from-bottom-4 duration-700 ease-out">
      {/* Welcome Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div className="space-y-1">
          <h1 className="text-[32px] font-bold tracking-[-0.04em] text-[#171717] dark:text-white flex items-center gap-2">
            Welcome, {displayName} <Sparkles size={24} className="text-amber-500 animate-pulse" />
          </h1>
          <p className="text-[16px] text-gray-500 dark:text-gray-400 font-medium tracking-tight">
            Your global advertising engine is ready. Localize your campaigns across SEA with precision AI.
          </p>
        </div>
      </div>

      {/* Grid Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Develop Stats */}
        <div className="bg-white dark:bg-[#111116] border border-gray-200 dark:border-white/10 p-6 rounded-2xl shadow-sm hover:shadow-md transition-all duration-300 relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-linear-to-br from-[#0080FF]/10 to-transparent rounded-bl-full pointer-events-none group-hover:scale-110 transition-transform duration-500" />
          <div className="flex items-center justify-between mb-4">
            <span className="text-[14px] font-semibold text-gray-500 dark:text-gray-400">Develop</span>
            <span className="p-2 rounded-lg bg-blue-50 dark:bg-blue-950/30 text-[#0080FF]">
              <Layers size={18} />
            </span>
          </div>
          <div className="text-[36px] font-bold tracking-tight text-gray-900 dark:text-white">124</div>
          <div className="text-[13px] font-medium text-gray-500 dark:text-gray-400 mt-1">Draft Assets</div>
        </div>

        {/* Preview Stats */}
        <div className="bg-white dark:bg-[#111116] border border-gray-200 dark:border-white/10 p-6 rounded-2xl shadow-sm hover:shadow-md transition-all duration-300 relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-linear-to-br from-[#FF1493]/10 to-transparent rounded-bl-full pointer-events-none group-hover:scale-110 transition-transform duration-500" />
          <div className="flex items-center justify-between mb-4">
            <span className="text-[14px] font-semibold text-gray-500 dark:text-gray-400">Preview</span>
            <span className="p-2 rounded-lg bg-pink-50 dark:bg-pink-950/30 text-[#FF1493]">
              <Eye size={18} />
            </span>
          </div>
          <div className="text-[36px] font-bold tracking-tight text-gray-900 dark:text-white">42</div>
          <div className="text-[13px] font-medium text-gray-500 dark:text-gray-400 mt-1">In Review</div>
        </div>

        {/* Ship Stats */}
        <div className="bg-white dark:bg-[#111116] border border-gray-200 dark:border-white/10 p-6 rounded-2xl shadow-sm hover:shadow-md transition-all duration-300 relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-linear-to-br from-[#00FFFF]/10 to-transparent rounded-bl-full pointer-events-none group-hover:scale-110 transition-transform duration-500" />
          <div className="flex items-center justify-between mb-4">
            <span className="text-[14px] font-semibold text-gray-500 dark:text-gray-400">Ship</span>
            <span className="p-2 rounded-lg bg-cyan-50 dark:bg-cyan-950/30 text-cyan-500">
              <Send size={18} />
            </span>
          </div>
          <div className="text-[36px] font-bold tracking-tight text-gray-900 dark:text-white">89</div>
          <div className="text-[13px] font-medium text-gray-500 dark:text-gray-400 mt-1">Active Global</div>
        </div>
      </div>

      {/* Main Grid: Description, Trend Sentiment & Activities */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left 2 Cols: Engine Info & Trends */}
        <div className="lg:col-span-2 space-y-6">
          {/* Subtle Gradient Promo Card */}
          <div className="rounded-2xl p-px bg-linear-to-br from-[#0080FF]/30 via-[#FF1493]/30 to-[#00FFFF]/30 overflow-hidden shadow-sm">
            <div className="bg-white dark:bg-[#111116] p-8 rounded-[15px] h-full flex flex-col justify-between">
              <div className="space-y-4">
                <h2 className="text-[20px] font-semibold tracking-tight text-gray-900 dark:text-white flex items-center gap-2">
                  Dashboard Initialization
                </h2>
                <p className="text-[15px] text-gray-600 dark:text-gray-400 leading-relaxed">
                  JusAds leverages state-of-the-art LLMs specifically tuned for linguistic nuances and cultural context in SEA markets. Our platform automates the transformation of master creatives into hyper-localized assets for Meta, Google, and TikTok.
                </p>
              </div>
              
              {/* Credits usage meter */}
              <div className="mt-8 pt-6 border-t border-gray-100 dark:border-white/5 space-y-2">
                <div className="flex justify-between items-center text-[13px] font-semibold">
                  <span className="text-gray-500 dark:text-gray-400 flex items-center gap-1.5">
                    <Coins size={15} /> Workspace Usage Credits
                  </span>
                  <span className="text-gray-900 dark:text-white">14,240 / 50,000 credits</span>
                </div>
                <div className="w-full h-2 bg-gray-100 dark:bg-white/5 rounded-full overflow-hidden">
                  <div className="h-full bg-linear-to-r from-[#0080FF] to-[#FF1493] rounded-full" style={{ width: "28.5%" }} />
                </div>
              </div>
            </div>
          </div>

          {/* Market Sentiment Mini Panel */}
          <div className="bg-white dark:bg-[#111116] border border-gray-200 dark:border-white/10 p-6 rounded-2xl shadow-sm">
            <h3 className="text-[16px] font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
              <TrendingUp size={16} className="text-[#0080FF]" /> Market Sentiment & Trends
            </h3>
            <div className="p-4 bg-gray-50 dark:bg-black/20 rounded-xl border border-gray-100 dark:border-white/5 text-[14px] text-gray-600 dark:text-gray-400 leading-relaxed">
              Family-focused protective hooks and mid-evening shopping surges represent the highest converting localized opportunities in Singapore and Malaysia this week. Go to the <strong className="text-gray-950 dark:text-white">Trends tab</strong> to select signals.
            </div>
          </div>
        </div>

        {/* Right 1 Col: Recent Activities */}
        <div className="bg-white dark:bg-[#111116] border border-gray-200 dark:border-white/10 p-6 rounded-2xl shadow-sm">
          <h3 className="text-[16px] font-bold text-gray-900 dark:text-white mb-6 flex items-center gap-2">
            <Clock size={16} className="text-[#FF1493]" /> Recent Activity
          </h3>
          <div className="space-y-6">
            {activities.map((item, idx) => (
              <div key={idx} className="flex gap-4 items-start group">
                <div className={`p-2 rounded-lg shrink-0 ${item.color} mt-0.5`}>
                  <Sparkles size={14} className="stroke-[2.5]" />
                </div>
                <div className="space-y-0.5 flex-1 min-w-0">
                  <h4 className="text-[14px] font-semibold text-gray-900 dark:text-white group-hover:text-[#0080FF] transition-colors truncate">
                    {item.title}
                  </h4>
                  <p className="text-[12px] text-gray-500 dark:text-gray-400 truncate">
                    {item.description}
                  </p>
                  <span className="text-[10px] font-bold text-gray-400 dark:text-gray-500 uppercase tracking-wider block pt-1">
                    {item.time}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

      </div>
    </div>
  );
}
