import { useState, useRef } from "react";
import { ImagePlus, Languages, Lightbulb, PlayCircle, ShieldCheck } from "lucide-react";
import { useNavigate } from "react-router";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import type { AuthAction } from "./Header";

gsap.registerPlugin(useGSAP, ScrollTrigger);

// ─── Static Data ──────────────────────────────────────────────────────────────

const STEPS = [
  { step: "STEP 1", title: "Choose an idea.", desc: "Start with your own poster or pick a local content idea that suits your customers.", code: "Idea selected" },
  { step: "STEP 2", title: "Create local versions.", desc: "Choose who you want to reach. JusAds prepares captions, images, and videos for them.", code: "Malaysian versions ready" },
  { step: "STEP 3", title: "Check and download.", desc: "Review the wording and design, run a safety check, then download only what you approve.", code: "Checked and ready" },
] as const;

const TREND_TAGS = ["#RayaPrep", "#LocalCoffee"] as const;

const WAVEFORM_HEIGHTS = [3, 6, 10, 5, 12, 8, 0, 8, 12, 5, 10, 6, 3] as const;

// ─── Features Component ───────────────────────────────────────────────────────

export default function Features({ onAuthAction }: { onAuthAction: AuthAction }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [nation, setNation] = useState<"MY" | "SG">("MY");
  const navigate = useNavigate();

  const openTask = (path: string) => {
    if (onAuthAction.isAuthenticated) navigate(path);
    else onAuthAction.onOpenLogin();
  };


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
      <section className="mx-auto mt-[96px] max-w-max-content-width px-6 lg:px-12" aria-labelledby="task-heading">
        <div className="mb-10 text-center">
          <p id="task-heading" className="text-2xl md:text-3xl font-semibold tracking-tight text-foreground">What would you like to do?</p>
          <p className="mx-auto mt-3 max-w-[650px] text-body-lg text-text-body">Choose a task. JusAds will guide you one step at a time.</p>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { icon: ImagePlus, title: "Create a local ad", desc: "Start from a product photo or idea.", path: "/dashboard/new" },
            { icon: Languages, title: "Adapt an existing ad", desc: "Make an English ad feel Malaysian.", path: "/dashboard/new" },
            { icon: Lightbulb, title: "See trending ideas", desc: "Find timely content ideas for your brand.", path: "/dashboard/trends" },
            { icon: ShieldCheck, title: "Check an ad", desc: "Review wording and safety before publishing.", path: "/dashboard/compliance" },
          ].map(({ icon: Icon, title, desc, path }) => (
            <button key={title} type="button" onClick={() => openTask(path)} className="group rounded-xl border border-border-default bg-surface-card p-5 text-left shadow-sm transition-all hover:-translate-y-0.5 hover:border-blue-300 hover:shadow-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600">
              <span className="mb-4 inline-flex h-11 w-11 items-center justify-center rounded-lg bg-blue-50 text-blue-700 dark:bg-blue-400/10 dark:text-blue-300">
                <Icon className="h-5 w-5" aria-hidden="true" />
              </span>
              <p className="text-lg font-semibold text-foreground">{title}</p>
              <p className="mt-2 text-sm leading-relaxed text-text-body">{desc}</p>
              <span className="mt-4 inline-flex text-sm font-semibold text-blue-700 dark:text-blue-300">Start this task</span>
            </button>
          ))}
        </div>
      </section>

      <section id="how-it-works" className="max-w-max-content-width mx-auto px-6 lg:px-12 mt-[120px] mb-[80px]">
        <div className="text-center mb-12">
          <p className="text-headline-lg md:text-[64px] font-semibold tracking-tight text-foreground mb-2 leading-tight">
            From poster to local ad in three steps
          </p>
          <p className="text-body-lg text-text-body leading-relaxed">
            No marketing terms to learn. You stay in control from start to finish.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {STEPS.map(({ step, title, desc, code }) => (
            <div key={step} className="flex flex-col gap-4 py-8 border-t border-border-default">
              <div className="flex flex-col gap-1">
                <span className="text-[12px] uppercase tracking-widest font-medium text-text-caption">{step}</span>
                <p className="text-headline-sm font-semibold text-foreground leading-snug">{title}</p>
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
          <p className="text-2xl md:text-3xl font-semibold tracking-tight text-foreground mb-2 leading-tight">
            Practical tools for everyday advertising
          </p>
          <p className="text-[20px] text-text-body leading-relaxed">
            Create faster, spend less on production, and speak more naturally to local customers.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Brand-Safe Trend Intelligence */}
          <div className="feature-card md:col-span-2 bg-surface-card rounded-[12px] p-10 flex flex-col md:flex-row items-center gap-10 shadow-[rgba(0,0,0,0.08)_0px_0px_0px_1px] border border-border-default">
            <div className="flex-1">
              <p className="text-headline-sm font-semibold text-foreground mb-4 leading-snug">Local content ideas you can use.</p>
              <p className="text-body-md text-text-body leading-relaxed">
                See timely TikTok and YouTube ideas, with sensitive topics filtered out before they reach you.
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
              <p className="text-headline-sm font-semibold text-foreground mb-2 leading-snug">Adapt an ad for local customers.</p>
              <p className="text-body-md text-text-body leading-relaxed">Change the language and tone while keeping your brand recognizable.</p>
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
              <p className="text-headline-sm font-semibold text-foreground mb-2 leading-snug">Create images and short videos.</p>
              <p className="text-body-md text-text-body leading-relaxed">Prepare polished social content without learning complicated editing software.</p>
            </div>
            <div className="mt-auto relative flex items-center justify-center bg-surface-inset rounded-lg h-[180px] overflow-hidden border border-border-default">
              <div className="absolute inset-0 flex items-center justify-center gap-[6px] opacity-40 z-10">
                {WAVEFORM_HEIGHTS.map((h, i) => (
                  <div key={i} className={`w-1.5 bg-gray-400 dark:bg-gray-500 rounded-full ${h === 0 ? "w-margin-page" : ""}`} style={{ height: h ? `${h * 4}px` : undefined }} />
                ))}
              </div>
              <PlayCircle className="relative z-10 text-text-caption w-12 h-12 hover:scale-110 transition-transform cursor-pointer" aria-label="Preview a sample video" />
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
