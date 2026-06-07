import { useRef } from "react";
import { CheckCircle2 } from "lucide-react";
import { useNavigate } from "react-router";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import type { AuthAction } from "./Header";

gsap.registerPlugin(useGSAP, ScrollTrigger);

// ─── Static Data ──────────────────────────────────────────────────────────────

const HOBBY_FEATURES = [
  "5 AI transcreations per month",
  "Standard 720p export",
  "Community support",
] as const;

const PRO_FEATURES = [
  "Unlimited AI transcreations",
  "4K raw export quality",
  "Priority 24/7 support",
  "Custom brand voice guidelines",
] as const;

// ─── Pricing Component ────────────────────────────────────────────────────────

export default function Pricing({ onAuthAction }: { onAuthAction: AuthAction }) {
  const containerRef = useRef<HTMLElement>(null);
  const navigate = useNavigate();
  const { isAuthenticated, onOpenLogin, status } = onAuthAction;
  const isLoading = status === "loading";

  function handleCTA() {
    if (isAuthenticated) navigate("/dashboard");
    else onOpenLogin();
  }

  useGSAP(() => {
    gsap.fromTo(".pricing-card",
      { y: 30, autoAlpha: 0 },
      {
        y: 0,
        autoAlpha: 1,
        stagger: 0.15,
        duration: 0.7,
        ease: "power3.out",
        scrollTrigger: {
          trigger: "#pricing",
          start: "top 75%",
        }
      }
    );
  }, { scope: containerRef });

  return (
    <section ref={containerRef} id="pricing" className="max-w-max-content-width mx-auto px-6 lg:px-12 mt-[120px] mb-[120px]">
      <div className="text-center mb-16">
        <h2 className="font-semibold tracking-tight text-foreground mb-4 leading-tight">Simple, transparent pricing</h2>
        <p className="text-[20px] text-text-body mx-auto leading-relaxed">Start for free, upgrade when you need to localize at scale.</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-[900px] mx-auto">
        {/* Hobby */}
        <div className="pricing-card bg-surface-card rounded-[12px] p-8 flex flex-col shadow-[rgba(0,0,0,0.08)_0px_0px_0px_1px] border border-border-default">
          <div className="mb-8">
            <h3 className="text-[20px] font-semibold text-foreground mb-2">Hobby</h3>
            <p className="text-label-ui text-text-body h-10">Perfect for experimenting with AI localization.</p>
            <div className="mt-6 flex items-baseline gap-1">
              <span className="text-headline-lg font-bold text-foreground tracking-tight">$0</span>
              <span className="text-body-md text-text-caption font-medium">/month</span>
            </div>
          </div>
          <button onClick={handleCTA} disabled={isLoading} className="w-full inline-flex items-center justify-center bg-white hover:bg-[#f6f6f5] active:scale-[0.98] text-black border-[1.5px] border-black dark:border-white dark:bg-white/10 dark:text-white dark:hover:bg-white/15 px-4 md:px-5 py-3 rounded-[6px] text-xs font-bold uppercase tracking-wider transition-premium brutalist-shadow-black dark:shadow-none mb-8 disabled:opacity-50 cursor-pointer">
            Start Deploying
          </button>
          <div className="flex flex-col gap-4 mt-auto">
            {HOBBY_FEATURES.map(f => (
              <div key={f} className="flex items-center gap-3">
                <CheckCircle2 className="w-5 h-5 text-foreground shrink-0" />
                <span className="text-label-ui text-text-body">{f}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Pro */}
        <div className="pricing-card bg-surface-card rounded-[12px] p-8 flex flex-col border-2 border-[#0a72ef] relative">
          <div className="absolute top-[-14px] left-1/2 -translate-x-1/2 bg-[#0a72ef] text-white px-3 py-1 rounded-full text-[12px] font-bold tracking-widest uppercase">Most Popular</div>
          <div className="mb-8 mt-2">
            <h3 className="text-[20px] font-semibold text-foreground mb-2">Pro</h3>
            <p className="text-label-ui text-text-body h-10">For marketers who need to localize at scale.</p>
            <div className="mt-6 flex items-baseline gap-1">
              <span className="text-headline-lg font-bold text-foreground tracking-tight">$29</span>
              <span className="text-body-md text-text-caption font-medium">/month</span>
            </div>
          </div>
          <button onClick={handleCTA} disabled={isLoading} className="w-full inline-flex items-center justify-center bg-black hover:bg-neutral-900 active:scale-[0.98] text-white border-[1.5px] border-black dark:bg-white dark:text-black dark:border-white dark:hover:bg-gray-100 px-4 md:px-5 py-3 rounded-[6px] text-xs font-bold uppercase tracking-wider transition-premium brutalist-shadow-subtle dark:shadow-none mb-8 disabled:opacity-50 cursor-pointer">
            Upgrade to Pro
          </button>
          <div className="flex flex-col gap-4 mt-auto">
            {PRO_FEATURES.map(f => (
              <div key={f} className="flex items-center gap-3">
                <CheckCircle2 className="w-5 h-5 text-[#0a72ef] shrink-0" />
                <span className="text-label-ui text-text-body">{f}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
