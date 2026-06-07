import { useState, useRef } from "react";
import { PlayCircle } from "lucide-react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(useGSAP, ScrollTrigger);

// ─── Static Data ──────────────────────────────────────────────────────────────

const STEPS = [
  { step: "1 / TRENDING", title: "Find what works.", desc: "Discover localized social media trends and identify high-performing content formats for your specific target market.", code: "> Fetching trending topics... [Done]" },
  { step: "2 / UPLOAD THEN GENERATE", title: "Upload and transform.", desc: "Upload your base marketing assets and instantly generate culturally adapted variations tailored to local demographics.", code: "> Generating localized variants... [Done]" },
  { step: "3 / VALIDATE", title: "Review and approve.", desc: "Ensure brand safety and cultural accuracy through our automated resonance checks before you deploy.", code: "> Running cultural resonance validation... Ready." },
] as const;

const TREND_TAGS = ["#RayaPrep", "#LocalCoffee"] as const;

const WAVEFORM_HEIGHTS = [3, 6, 10, 5, 12, 8, 0, 8, 12, 5, 10, 6, 3] as const;

// ─── Features Component ───────────────────────────────────────────────────────

export default function Features() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [nation, setNation] = useState<"MY" | "SG">("MY");

  useGSAP(() => {
    gsap.fromTo(".feature-card",
      { y: 30, autoAlpha: 0 },
      {
        y: 0,
        autoAlpha: 1,
        stagger: 0.1,
        duration: 0.7,
        ease: "power3.out",
        scrollTrigger: {
          trigger: "#features",
          start: "top 80%",
        }
      }
    );
  }, { scope: containerRef });

  return (
    <div ref={containerRef}>
      <section id="how-it-works" className="max-w-max-content-width mx-auto px-6 lg:px-12 mt-[120px] mb-[80px]">
        <div className="text-center mb-12">
          <h2 className="text-headline-lg md:text-[64px] font-semibold tracking-tight text-foreground mb-2 leading-tight">
            Your localization pipeline. Simplified.
          </h2>
          <p className="text-body-lg text-text-body leading-relaxed">
            From viral trend to localized, platform-ready ad in three steps.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {STEPS.map(({ step, title, desc, code }) => (
            <div key={step} className="flex flex-col gap-4 py-8 border-t border-border-default">
              <div className="flex flex-col gap-1">
                <span className="text-[12px] uppercase tracking-widest font-medium text-text-caption">{step}</span>
                <h3 className="text-headline-sm font-semibold text-foreground leading-snug">{title}</h3>
              </div>
              <p className="text-text-body text-body-md leading-relaxed">{desc}</p>
              <div className="mt-auto pt-4">
                <div className="bg-surface-inset p-4 rounded text-[12px] font-mono text-text-body border border-border-subtle">
                  <code>{code}</code>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section id="features" className="max-w-max-content-width mx-auto px-6 lg:px-12 mt-[120px] mb-[120px]">
        <div className="text-center mb-12">
          <h2 className="font-semibold tracking-tight text-foreground mb-2 leading-tight">
            Everything you need to localize at scale.
          </h2>
          <p className="text-[20px] text-text-body leading-relaxed">
            Enterprise-grade AI tools built specifically for the SEA market.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Brand-Safe Trend Intelligence */}
          <div className="feature-card md:col-span-2 bg-surface-card rounded-[12px] p-10 flex flex-col md:flex-row items-center gap-10 shadow-[rgba(0,0,0,0.08)_0px_0px_0px_1px] border border-border-default">
            <div className="flex-1">
              <h3 className="text-headline-sm font-semibold text-foreground mb-4 leading-snug">Brand-Safe Trend Intelligence.</h3>
              <p className="text-body-md text-text-body leading-relaxed">
                Monitor local TikTok and YouTube trends filtered securely for brand safety. Capitalize on viral moments without risking your brand's reputation in sensitive markets.
              </p>
            </div>
            <div className="flex-1 w-full bg-surface-inset rounded-lg p-8 flex flex-col gap-4 font-mono">
              {TREND_TAGS.map(tag => (
                <div key={tag} className="flex justify-between items-center p-3 bg-surface-card border border-border-subtle rounded shadow-sm">
                  <span className="text-foreground text-label-ui">{tag}</span>
                  <span className="bg-[#0080FF]/10 text-[#0080FF] px-2 py-1 rounded text-[10px] uppercase font-bold">Safe</span>
                </div>
              ))}
            </div>
          </div>

          {/* Nation Support Engine */}
          <div className="feature-card bg-surface-card rounded-[12px] p-8 flex flex-col gap-8 shadow-[rgba(0,0,0,0.08)_0px_0px_0px_1px] border border-border-default">
            <div>
              <h3 className="text-headline-sm font-semibold text-foreground mb-2 leading-snug">Nation Support Engine.</h3>
              <p className="text-body-md text-text-body leading-relaxed">Instantly adapt branding, video assets, and context for local audiences.</p>
            </div>
            <div className="mt-auto">
              <div className="flex bg-surface-inset p-1 rounded-full w-full mb-4 relative">
                <div className="absolute top-1 bottom-1 w-[calc(50%-4px)] rounded-full bg-[#0080FF] transition-all duration-300 shadow-sm" style={{ left: nation === "MY" ? "4px" : "calc(50%)" }} />
                <button onClick={() => setNation("MY")} className={`flex-1 text-xs py-2 rounded-full font-bold transition-all relative z-10 ${nation === "MY" ? "text-white" : "text-text-caption hover:text-foreground"}`}>Malaysia</button>
                <button onClick={() => setNation("SG")} className={`flex-1 text-xs py-2 rounded-full font-bold transition-all relative z-10 ${nation === "SG" ? "text-white" : "text-text-caption hover:text-foreground"}`}>Singapore</button>
              </div>
              <div className="p-4 bg-surface-inset rounded border border-border-subtle text-sm mb-2 text-text-body">
                "The ultimate refreshing drink for a hot day."
              </div>
              <div className={`p-4 rounded border text-sm font-medium transition-colors duration-500 ${nation === "MY" ? "bg-blue-50 dark:bg-[#0080FF]/10 border-blue-200 dark:border-[#0080FF]/20 text-blue-700 dark:text-[#0080FF]" : "bg-orange-50 dark:bg-orange-500/10 border-orange-200 dark:border-orange-500/20 text-orange-700 dark:text-orange-400"}`}>
                {nation === "MY" ? '"Minuman paling ngam waktu panas lit lit."' : '"The perfect thirst-quencher for this blazing heat, lah."'}
              </div>
            </div>
          </div>

          {/* High-Fidelity Gen AI */}
          <div className="feature-card bg-surface-card rounded-[12px] p-8 flex flex-col gap-8 shadow-[rgba(0,0,0,0.08)_0px_0px_0px_1px] border border-border-default">
            <div>
              <h3 className="text-headline-sm font-semibold text-foreground mb-2 leading-snug">High-Fidelity Gen AI.</h3>
              <p className="text-body-md text-text-body leading-relaxed">Generate stunning, culturally aligned visuals that feel truly authentic to the local market.</p>
            </div>
            <div className="mt-auto relative flex items-center justify-center bg-surface-inset rounded-lg h-[180px] overflow-hidden border border-border-default">
              <div className="absolute inset-0 flex items-center justify-center gap-[6px] opacity-40 z-10">
                {WAVEFORM_HEIGHTS.map((h, i) => (
                  <div key={i} className={`w-1.5 bg-gray-400 dark:bg-gray-500 rounded-full ${h === 0 ? "w-margin-page" : ""}`} style={{ height: h ? `${h * 4}px` : undefined }} />
                ))}
              </div>
              <PlayCircle className="relative z-10 text-text-caption w-12 h-12 hover:scale-110 transition-transform cursor-pointer" />
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
