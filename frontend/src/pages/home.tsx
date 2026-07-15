import { useRef, useState, useEffect } from "react";
import { useAuth } from "@/hooks/useAuth";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { PromptRecommendations } from "@/components/prompt-search/PromptRecommendations";
import { toast } from "sonner";
import {
  Sparkles,
  Layers,
  Eye,
  Send,
  TrendingUp,
  Clock,
  Coins,
  Zap,
} from "lucide-react";

gsap.registerPlugin(useGSAP);

export default function DashboardHome() {
  const { user } = useAuth();
  const displayName = user?.profile.name ?? user?.profile.email ?? "Creative Lead";
  const containerRef = useRef<HTMLDivElement>(null);

  const [profile, setProfile] = useState<any>({});

  useEffect(() => {
    const email = user?.profile?.email;
    if (!email) return;

    fetch(`${import.meta.env.VITE_API_BASE || "http://localhost:8000"}/api/profile/${email}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) {
          setProfile({
            productName: data.company_name,
            productCategory: data.product_category,
            userEmail: email,
          });
        } else {
          setProfile({ userEmail: email });
        }
      })
      .catch(() => setProfile({ userEmail: email }));
  }, [user]);

  // Stats data
  const stats = [
    {
      label: "Develop",
      value: 124,
      sub: "Draft Assets",
      icon: Layers,
      gradient: "from-[#0080FF]/10",
      iconBg: "bg-blue-50 dark:bg-blue-950/30 text-[#0080FF]",
    },
    {
      label: "Preview",
      value: 42,
      sub: "In Review",
      icon: Eye,
      gradient: "from-[#FF1493]/10",
      iconBg: "bg-pink-50 dark:bg-pink-950/30 text-[#FF1493]",
    },
    {
      label: "Ship",
      value: 89,
      sub: "Active Global",
      icon: Send,
      gradient: "from-[#00FFFF]/10",
      iconBg: "bg-cyan-50 dark:bg-cyan-950/30 text-cyan-500",
    },
  ];

  // Recent activity data
  const activities = [
    {
      title: "Bangkok Launch Ready",
      description: "Campaign localized to Thai",
      time: "2m ago",
      color: "text-emerald-500 bg-emerald-50 dark:bg-emerald-950/20",
    },
    {
      title: "New Asset Draft",
      description: "Video variant #14 generated",
      time: "14m ago",
      color: "text-[#0080FF] bg-blue-50 dark:bg-blue-950/20",
    },
    {
      title: "Policy Audit Passed",
      description: "Meta compliance verified",
      time: "1h ago",
      color: "text-purple-500 bg-purple-50 dark:bg-purple-950/20",
    },
  ];

  useGSAP(
    () => {
      // Master timeline for orchestrated entrance
      const tl = gsap.timeline({ defaults: { duration: 0.6, ease: "power3.out" } });

      // Header entrance
      tl.fromTo(".dash-header", { y: -20, opacity: 0 }, { y: 0, opacity: 1, clearProps: "all" })
        .fromTo(".dash-header-sub", { y: 10, opacity: 0 }, { y: 0, opacity: 1, duration: 0.4, clearProps: "all" }, "<0.15");

      // Stats cards stagger in with scale
      tl.fromTo(".stat-card", {
        y: 40,
        opacity: 0,
        scale: 0.95,
      }, {
        y: 0,
        opacity: 1,
        scale: 1,
        stagger: 0.12,
        duration: 0.5,
        ease: "back.out(1.4)",
        clearProps: "all",
      }, "-=0.3");

      // Animate stat numbers counting up
      const statNumbers = containerRef.current?.querySelectorAll(".stat-number");
      statNumbers?.forEach((el) => {
        const target = parseInt(el.getAttribute("data-value") || "0", 10);
        const obj = { val: 0 };
        gsap.to(obj, {
          val: target,
          duration: 1.2,
          delay: 0.6,
          ease: "power2.out",
          onUpdate: () => {
            el.textContent = Math.round(obj.val).toString();
          },
        });
      });

      // Promo card slides in
      tl.fromTo(".promo-card", {
        y: 30,
        opacity: 0,
      }, {
        y: 0,
        opacity: 1,
        duration: 0.7,
        ease: "power2.out",
        clearProps: "all",
      }, "-=0.2");

      // Credit bar animates width
      tl.from(".credit-bar-fill", {
        scaleX: 0,
        transformOrigin: "left center",
        duration: 1,
        ease: "power2.inOut",
        clearProps: "transform",
      }, "-=0.4");

      // Market sentiment panel
      tl.fromTo(".sentiment-panel", {
        y: 20,
        opacity: 0,
      }, {
        y: 0,
        opacity: 1,
        duration: 0.5,
        clearProps: "all",
      }, "-=0.6");

      // Activity items stagger from right
      tl.fromTo(".activity-item", {
        x: 30,
        opacity: 0,
      }, {
        x: 0,
        opacity: 1,
        stagger: 0.1,
        duration: 0.4,
        ease: "power2.out",
        clearProps: "all",
      }, "-=0.5");

      // Removed gradient orb animations
    },
    { scope: containerRef }
  );

  return (
    <div
      ref={containerRef}
      className="flex flex-col gap-2 pt-4 px-8 pb-8 max-w-5xl mx-auto w-full font-hanken"
    >
      {/* Welcome Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div className="space-y-1">
          <h2 className="dash-header text-[24px] font-bold tracking-[-0.04em] text-text-heading flex items-center">
            Welcome, {displayName}
          </h2>
          <p className="dash-header-sub text-body-md text-text-caption font-medium tracking-tight">
            Your global advertising engine is ready. Localize your campaigns across SEA with precision AI.
          </p>
        </div>
        <div className="dash-header-sub flex items-center gap-3">
          <div className="flex items-center px-4 py-2 rounded-full border border-border-default">
            <Zap size={14} className="text-text-caption" />
            <span className="text-label-ui font-semibold text-text-body">
              AI Engine Active
            </span>
          </div>
        </div>
      </div>

      {/* Grid Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {stats.map((stat, idx) => {
          const Icon = stat.icon;
          return (
            <div
              key={idx}
              className="stat-card bg-surface-card border border-border-default p-6 rounded-2xl retina-border card-shadow hover:-translate-y-1 transition-all duration-300 relative overflow-hidden group cursor-default"
            >
              <div className="flex items-center justify-between mb-4">
                <span className="text-label-ui font-semibold text-text-caption">
                  {stat.label}
                </span>
                <span className={`p-2 rounded-lg ${stat.iconBg}`}>
                  <Icon size={18} />
                </span>
              </div>
              <div
                className="stat-number text-[36px] font-bold tracking-tight text-text-heading"
                data-value={stat.value}
              >
                0
              </div>
              <div className="text-label-ui font-medium text-text-caption mt-1">
                {stat.sub}
              </div>
            </div>
          );
        })}
      </div>

      {/* Main Grid: Description, Trend Sentiment & Activities */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Engine Info & Trends */}
        <div className="lg:col-span-2 space-y-6">
          <div className="promo-card rounded-2xl border border-border-default overflow-hidden shadow-sm hover:shadow-md transition-shadow duration-500">
            <div className="bg-surface-card p-8 h-full flex flex-col justify-between relative overflow-hidden">
              <div className="space-y-4 relative z-10">
                <h3 className="text-[24px] font-semibold tracking-tight text-text-heading flex items-center gap-2">
                  <span className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-blue-600 dark:bg-blue-500">
                    <Zap size={16} className="text-white" />
                  </span>
                  AI Compliance Engine
                </h3>
                <p className="text-[15px] text-text-body leading-relaxed">
                  JusAds leverages state-of-the-art LLMs specifically tuned for linguistic nuances and cultural context in SEA markets. Our platform automates the transformation of master creatives into hyper-localized assets for Meta, Google, and TikTok.
                </p>
              </div>

              {/* Credits usage meter */}
              <div className="mt-8 pt-6 border-t border-border-subtle space-y-2 relative z-10">
                <div className="flex justify-between items-center text-code-sm font-semibold">
                  <span className="text-text-caption flex items-center gap-1.5">
                    <Coins size={15} /> Workspace Usage Credits
                  </span>
                  <span className="text-text-heading">14,240 / 50,000</span>
                </div>
                <div className="w-full h-2.5 bg-surface-inset rounded-full overflow-hidden">
                  <div
                    className="credit-bar-fill h-full bg-blue-600 dark:bg-blue-500 rounded-full"
                    style={{ width: "28.5%" }}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Prompt Recommendations Feed */}
          <div className="sentiment-panel bg-surface-card border border-border-default p-6 rounded-2xl shadow-sm hover:shadow-md transition-shadow duration-300">
            <PromptRecommendations
              profile={profile}
              onUse={(prompt) => {
                navigator.clipboard.writeText(prompt);
                toast.success("Prompt copied to clipboard! Go to Create to start generating.");
              }}
              maxCards={3}
            />
          </div>
        </div>

        {/* Right 1 Col: Recent Activities */}
        <div className="bg-surface-card border border-border-default p-6 rounded-2xl shadow-sm">
          <h3 className="text-body-md font-bold text-text-heading mb-6 flex items-center gap-2">
            <Clock size={16} className="text-[#FF1493]" /> Recent Activity
          </h3>
          <div className="space-y-6">
            {activities.map((item, idx) => (
              <div
                key={idx}
                className="activity-item flex gap-4 items-start group cursor-default"
              >
                <div
                  className={`p-2 rounded-lg shrink-0 ${item.color} mt-2 group-hover:scale-110 transition-transform duration-200`}
                >
                  <Sparkles size={14} className="stroke-[2.5]" />
                </div>
                <div className="gap-2 flex flex-col flex-1 min-w-0">
                  <h4 className="text-label-ui font-semibold text-text-heading group-hover:text-[#0080FF] transition-colors truncate">
                    {item.title}
                  </h4>
                  <p className="text-label-ui text-text-caption truncate">
                    {item.description}
                  </p>
                  <span className="text-code-xs font-bold text-text-caption uppercase tracking-wider block pt-1">
                    {item.time}
                  </span>
                </div>
              </div>
            ))}
          </div>

          {/* Quick action */}
          <div className="mt-6 pt-4 border-t border-border-subtle">
            <button className="w-full py-2.5 px-4 rounded-xl text-code-sm font-semibold text-[#0080FF] bg-[#0080FF]/5 hover:bg-[#0080FF]/10 transition-colors duration-200 flex items-center justify-center gap-2">
              <Sparkles size={14} />
              View All Activity
            </button>
          </div>
        </div>
      </div>

    </div>
  );
}
