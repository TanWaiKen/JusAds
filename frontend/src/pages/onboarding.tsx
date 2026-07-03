/**
 * Onboarding Page — Mandatory business profile setup.
 * Users must complete this before accessing compliance or generation features.
 */

import { useState, useRef } from "react";
import { useNavigate } from "react-router";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { Building2, Package, Globe, MonitorPlay, ArrowRight } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/hooks/useAuth";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

gsap.registerPlugin(useGSAP);

const PRODUCT_CATEGORIES = [
  "Skincare & Beauty",
  "Fashion & Apparel",
  "Food & Beverage",
  "Health & Wellness",
  "Technology & Electronics",
  "Education & Learning",
  "Kids & Parenting",
  "Automotive",
  "Finance & Insurance",
  "Real Estate",
  "Travel & Tourism",
  "Entertainment",
  "Other",
];

const PLATFORMS = [
  "TikTok",
  "Instagram",
  "Meta (Facebook)",
  "YouTube",
  "Shopee",
  "X (Twitter)",
  "TV / Broadcast",
  "Government / Official",
  "Print Media",
];

const MARKETS = [
  { code: "MY", label: "Malaysia" },
  { code: "SG", label: "Singapore" },
  { code: "ID", label: "Indonesia" },
  { code: "TH", label: "Thailand" },
];

export default function OnboardingPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const containerRef = useRef<HTMLDivElement>(null);

  const [companyName, setCompanyName] = useState("");
  const [productCategory, setProductCategory] = useState("");
  const [productDescription, setProductDescription] = useState("");
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>([]);
  const [selectedMarkets, setSelectedMarkets] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useGSAP(() => {
    gsap.from(".onboard-card", {
      y: 35,
      autoAlpha: 0,
      stagger: 0.08,
      duration: 0.6,
      ease: "power3.out",
    });
  }, { scope: containerRef });

  const togglePlatform = (platform: string) => {
    setSelectedPlatforms((prev) =>
      prev.includes(platform) ? prev.filter((p) => p !== platform) : [...prev, platform]
    );
  };

  const toggleMarket = (code: string) => {
    setSelectedMarkets((prev) =>
      prev.includes(code) ? prev.filter((m) => m !== code) : [...prev, code]
    );
  };

  const handleSubmit = async () => {
    if (!companyName.trim() || !productCategory || selectedPlatforms.length === 0 || selectedMarkets.length === 0) {
      toast.error("Please fill in all required fields");
      return;
    }

    setIsSubmitting(true);
    const email = user?.profile?.email ?? "anonymous";

    try {
      const res = await fetch(`${API_BASE}/api/profile`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          owner_email: email,
          company_name: companyName.trim(),
          product_category: productCategory,
          product_description: productDescription.trim(),
          target_platforms: selectedPlatforms,
          target_markets: selectedMarkets,
        }),
      });

      if (!res.ok) throw new Error("Failed to save profile");

      toast.success("Profile saved! Welcome to JusAds.");
      // Redirect to dashboard home which will trigger status refresh
      navigate("/dashboard");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save profile");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      ref={containerRef}
      className="min-h-screen relative flex items-center justify-center p-6 bg-gradient-to-tr from-blue-50/50 via-background to-pink-50/50 dark:from-blue-950/20 dark:via-background dark:to-pink-950/20 font-hanken overflow-x-hidden"
    >
      {/* Paper Grain Texture Layer */}
      <svg className="absolute inset-0 w-full h-full pointer-events-none z-30 opacity-[0.04] mix-blend-overlay" xmlns="http://www.w3.org/2000/svg">
        <filter id="paperEmboss">
          <feTurbulence type="fractalNoise" baseFrequency="0.04" numOctaves="3" result="noise" />
          <feDiffuseLighting in="noise" lightingColor="#ffffff" surfaceScale="2">
            <feDistantLight azimuth="45" elevation="60" />
          </feDiffuseLighting>
          <feBlend mode="multiply" in="SourceGraphic" in2="noise" />
        </filter>
        <rect width="100%" height="100%" filter="url(#paperEmboss)" />
      </svg>

      <div className="w-full max-w-2xl relative z-10 space-y-6">
        
        {/* Main Onboarding Wrapper Card */}
        <div className="onboard-card relative bg-surface-card border border-border-default rounded-2xl p-8 shadow-xl overflow-hidden retina-border">
          {/* Top visual glow bar from landing page Hero style */}
          <div className="absolute top-0 left-0 right-0 h-1.5 bg-gradient-to-r from-blue-600 via-pink-500 to-cyan-400" />
          
          {/* Header */}
          <div className="text-center mb-8 mt-2">
            <h2 className="text-3xl font-bold tracking-tight text-text-heading mb-2">
              Set up your business profile
            </h2>
            <p className="text-sm font-medium text-text-caption">
              This helps our AI understand your product context for smarter compliance checking and ad generation.
            </p>
          </div>

          <div className="space-y-6">
            {/* Company Name */}
            <div className="space-y-3">
              <label className="flex items-center gap-2 text-sm font-semibold text-text-heading">
                <Building2 size={16} className="text-[#0080FF]" />
                Company Name *
              </label>
              <input
                type="text"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="e.g., GlowSkin Malaysia"
                className="w-full rounded-lg border border-border-default bg-background px-4 py-2.5 text-sm text-text-heading placeholder:text-text-caption focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Product Category */}
            <div className="space-y-3">
              <label className="flex items-center gap-2 text-sm font-semibold text-text-heading">
                <Package size={16} className="text-[#FF1493]" />
                Product Category *
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {PRODUCT_CATEGORIES.map((cat) => (
                  <button
                    key={cat}
                    type="button"
                    onClick={() => setProductCategory(cat)}
                    className={`px-3 py-2 rounded-lg text-xs font-semibold tracking-tight transition-all border cursor-pointer ${
                      productCategory === cat
                        ? "bg-[#0080FF] text-white border-[#0080FF] shadow-sm"
                        : "bg-surface-inset text-text-body hover:bg-surface-inset/80 border-border-subtle hover:text-text-heading"
                    }`}
                  >
                    {cat}
                  </button>
                ))}
              </div>
              <textarea
                value={productDescription}
                onChange={(e) => setProductDescription(e.target.value)}
                placeholder="Briefly describe what you sell (optional — helps AI understand context better)"
                rows={2}
                className="w-full rounded-lg border border-border-default bg-background px-4 py-2.5 text-sm text-text-heading placeholder:text-text-caption focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              />
            </div>

            {/* Target Platforms */}
            <div className="space-y-3">
              <label className="flex items-center gap-2 text-sm font-semibold text-text-heading">
                <MonitorPlay size={16} className="text-[#00FFFF]" />
                Where do you advertise? *
              </label>
              <p className="text-xs text-text-caption">
                Select all platforms you use. This affects how strictly content is evaluated (TV/Official = strictest, TikTok = most relaxed).
              </p>
              <div className="flex flex-wrap gap-2">
                {PLATFORMS.map((platform) => {
                  const isSelected = selectedPlatforms.includes(platform);
                  return (
                    <button
                      key={platform}
                      type="button"
                      onClick={() => togglePlatform(platform)}
                      className={`px-3 py-2 rounded-lg text-xs font-semibold transition-all border cursor-pointer ${
                        isSelected
                          ? "bg-black dark:bg-white text-white dark:text-black border-black dark:border-white shadow-sm"
                          : "bg-surface-inset text-text-body hover:bg-surface-inset/80 border-border-subtle hover:text-text-heading"
                      }`}
                    >
                      {platform}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Target Markets */}
            <div className="space-y-3">
              <label className="flex items-center gap-2 text-sm font-semibold text-text-heading">
                <Globe size={16} className="text-emerald-500" />
                Target Markets *
              </label>
              <div className="flex flex-wrap gap-2">
                {MARKETS.map((market) => {
                  const isSelected = selectedMarkets.includes(market.code);
                  return (
                    <button
                      key={market.code}
                      type="button"
                      onClick={() => toggleMarket(market.code)}
                      className={`px-4 py-2 rounded-lg text-xs font-semibold tracking-wider uppercase transition-all border cursor-pointer ${
                        isSelected
                          ? "bg-gradient-to-r from-blue-600 to-pink-500 text-white border-transparent shadow-sm"
                          : "bg-surface-inset text-text-body hover:bg-surface-inset/80 border-border-subtle hover:text-text-heading"
                      }`}
                    >
                      {market.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Submit */}
            <div className="flex justify-end pt-4 border-t border-border-default/60">
              <button
                type="button"
                onClick={handleSubmit}
                disabled={isSubmitting}
                className="inline-flex items-center gap-2 bg-black hover:bg-neutral-900 active:scale-[0.98] text-white border-[1.5px] border-black dark:bg-white dark:text-black dark:border-white dark:hover:bg-gray-100 px-5 py-3 rounded-[6px] text-xs font-bold uppercase tracking-wider transition-premium brutalist-shadow-black dark:shadow-none disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
              >
                {isSubmitting ? "Saving Profile..." : "Complete Setup"}
                <ArrowRight size={14} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
